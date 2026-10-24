"""Runtime: owns the intersections. For each one it wires
   sources (live or simulated) -> FrameResult -> controller -> events.

The same entry points (`on_frame`, `ingest`) are used by in-process cameras and
by external producers (POST /api/ambulances/events, later MQTT), so Phase 6
integration does not need a different code path."""
from __future__ import annotations

import logging
import os
import threading
import time

from .bus import EventBus
from .config import AppConfig, IntersectionCfg
from .controllers import APPROACHES, IntersectionController, create_base
from .controllers.types import PreemptConfig, Timing
from .vision.sim import SimSource
from .vision.types import AmbDet, BaseSource, FrameResult

log = logging.getLogger("equiflow")
TICK_S = 0.1
POSITION_EVERY_S = 1.0


def _live_available(cfg: AppConfig) -> tuple[bool, str]:
    if cfg.mode == "sim":
        return False, "mode=sim in config"
    try:
        import ultralytics  # noqa: F401
    except Exception:  # noqa: BLE001
        return False, "ultralytics is not installed"
    if not cfg.vision.cls_weights or not os.path.exists(cfg.vision.cls_weights):
        return False, f"classifier weights not found: '{cfg.vision.cls_weights}'"
    return True, "ok"


class IntersectionRuntime:
    def __init__(self, cfg: AppConfig, icfg: IntersectionCfg, bus: EventBus, live_ok: bool, classifier):
        self.cfg, self.icfg, self.bus = cfg, icfg, bus
        self.id = icfg.id
        self.lock = threading.RLock()
        timing = Timing(**cfg.timing.model_dump())
        base = create_base(cfg.controller, timing, cfg.controller_params)
        self.controller = IntersectionController(
            icfg.id, base, timing, PreemptConfig(**cfg.preempt.model_dump()),
            emit=lambda type, **kw: bus.publish(type, intersection_id=icfg.id, **kw), now=time.monotonic())
        self.sources: dict[str, BaseSource] = {}
        self.fps = {a: 0.0 for a in APPROACHES}
        self.registry: dict[tuple[str, int], dict] = {}
        self.last_position_ts: dict[tuple[str, int], float] = {}
        self.detections_total = 0
        self.live_ok, self.classifier = live_ok, classifier
        self._running = False
        self._build_sources()

    # ------------------------------------------------------------ sources
    def _build_sources(self) -> None:
        for a in APPROACHES:
            spec = self.icfg.sources.get(a, "sim")
            v = self.cfg.vision
            if spec != "sim" and self.live_ok:
                from .vision.live import DirectionTracker, LiveSource
                self.sources[a] = LiveSource(a, spec, DirectionTracker(v, self.classifier), v, self.on_frame)
            else:
                self.sources[a] = SimSource(a, self.cfg.sim, self.on_frame, v.stream_width, v.jpeg_quality)

    def start(self) -> None:
        self._running = True
        for s in self.sources.values():
            s.start()
        threading.Thread(target=self._ticker, daemon=True, name=f"tick-{self.id}").start()

    def stop(self) -> None:
        self._running = False
        for s in self.sources.values():
            s.stop()

    def _ticker(self) -> None:
        while self._running:
            with self.lock:
                self.controller.tick(time.monotonic())
            time.sleep(TICK_S)

    # ------------------------------------------------------------- inputs
    def on_frame(self, approach: str, res: FrameResult, fps: float) -> None:
        self.fps[approach] = fps
        self._record(approach, res.ambulances, res.new_confirmed, vehicles=res.vehicles)

    def ingest(self, approach: str, present: bool, track_id: int | None, confidence: float,
               cx: float | None, cy: float | None) -> None:
        """External producer (another process / MQTT bridge / SUMO ground truth)."""
        dets, new = [], []
        if present:
            tid = track_id if track_id is not None else -1
            det = AmbDet(tid, confidence, cx if cx is not None else 0.5, cy if cy is not None else 0.5, (0, 0, 0, 0))
            dets = [det]
            rec = self.registry.get((approach, tid))
            if rec is None or time.time() - rec["last_seen"] > self.cfg.preempt.clear_hold_s:
                new = [det]
        self._record(approach, dets, new, vehicles=None)

    def _record(self, approach: str, ambs: list[AmbDet], new: list[AmbDet], vehicles: int | None) -> None:
        now_m, now_w = time.monotonic(), time.time()
        with self.lock:
            for d in new:
                self.detections_total += 1
                self.registry[(approach, d.track_id)] = {
                    "id": f"{self.id}-{approach}-{d.track_id}", "intersection_id": self.id, "approach": approach,
                    "track_id": d.track_id, "confidence": round(d.confidence, 3), "first_seen": now_w,
                    "last_seen": now_w, "cx": d.cx, "cy": d.cy, "status": "active"}
                self.bus.publish("ambulance_detected", intersection_id=self.id, approach=approach,
                                 track_id=d.track_id, confidence=round(d.confidence, 3))
            for d in ambs:
                rec = self.registry.get((approach, d.track_id))
                if rec is None:
                    continue
                rec.update(last_seen=now_w, cx=d.cx, cy=d.cy, confidence=round(d.confidence, 3), status="active")
                key = (approach, d.track_id)
                if now_m - self.last_position_ts.get(key, 0) >= POSITION_EVERY_S:
                    self.last_position_ts[key] = now_m
                    self.bus.publish("ambulance_position", intersection_id=self.id, approach=approach,
                                     track_id=d.track_id, ambulance_id=rec["id"], cx=d.cx, cy=d.cy,
                                     confidence=round(d.confidence, 3))
            self.controller.observe(approach, bool(ambs), now_m, vehicles=vehicles)

    def manual_preempt(self, approach: str, duration_s: float) -> None:
        with self.lock:
            self.controller.inject(approach, duration_s, time.monotonic())
        src = self.sources.get(approach)
        if isinstance(src, SimSource):
            src.trigger(duration_s)
        self.bus.publish("manual_preempt", intersection_id=self.id, approach=approach, duration_s=duration_s)

    def cancel_preempt(self, approach: str) -> None:
        with self.lock:
            self.controller.cancel(approach)
        self.bus.publish("manual_preempt_cancelled", intersection_id=self.id, approach=approach)

    # ----------------------------------------------------------- snapshot
    def ambulances(self) -> list[dict]:
        now_w = time.time()
        clear = self.cfg.preempt.clear_hold_s
        out = []
        for rec in self.registry.values():
            r = dict(rec)
            r["status"] = "active" if now_w - rec["last_seen"] <= clear else "cleared"
            out.append(r)
        out.sort(key=lambda r: -r["last_seen"])
        # forget very old records
        for k in [k for k, r in self.registry.items() if now_w - r["last_seen"] > 600]:
            self.registry.pop(k, None)
        return out[:30]

    def snapshot(self) -> dict:
        with self.lock:
            snap = self.controller.snapshot(time.monotonic())
        snap.update(
            name=self.icfg.name or self.id, lat=self.icfg.lat, lng=self.icfg.lng,
            detections_total=self.detections_total,
            sources={a: s.info() for a, s in self.sources.items()})
        return snap


class Runtime:
    def __init__(self, cfg: AppConfig, bus: EventBus):
        self.cfg, self.bus = cfg, bus
        self.started_at = time.time()
        self.live_ok, self.mode_reason = _live_available(cfg)
        classifier = None
        if self.live_ok:
            try:
                from .vision.live import SharedClassifier
                classifier = SharedClassifier(cfg.vision)
            except Exception as e:  # noqa: BLE001
                self.live_ok, self.mode_reason = False, f"could not load classifier: {e}"
        if not self.live_ok:
            log.warning("running in SIMULATION mode (%s)", self.mode_reason)
        self.intersections = {i.id: IntersectionRuntime(cfg, i, bus, self.live_ok, classifier)
                              for i in cfg.intersections}

    def start(self) -> None:
        for i in self.intersections.values():
            i.start()
        self.bus.publish("system_started", mode=self.mode, controller=self.cfg.controller)

    def stop(self) -> None:
        for i in self.intersections.values():
            i.stop()

    @property
    def mode(self) -> str:
        live = any(s.kind == "live" for i in self.intersections.values() for s in i.sources.values())
        return "live" if live else "sim"

    def get(self, iid: str) -> IntersectionRuntime:
        if iid not in self.intersections:
            raise KeyError(iid)
        return self.intersections[iid]

    def metrics(self, sigs: list[dict] | None = None) -> dict:
        sigs = sigs if sigs is not None else [i.snapshot() for i in self.intersections.values()]
        lat = [l for i in self.intersections.values() for l in i.controller.stats.latencies_s]
        return {
            "uptime_s": round(time.time() - self.started_at),
            "mode": self.mode,
            "mode_reason": self.mode_reason,
            "controller": self.cfg.controller,
            "intersections": len(sigs),
            "ambulance_detections": sum(s["detections_total"] for s in sigs),
            "preemptions": sum(s["stats"]["preemptions"] for s in sigs),
            "active_preemptions": sum(1 for s in sigs if s["active_preempt"]),
            "preempt_latency_avg_s": round(sum(lat) / len(lat), 2) if lat else None,
            "preempt_latency_last_s": round(lat[-1], 2) if lat else None,
            "preempt_latency_max_s": round(max(lat), 2) if lat else None,
            "total_vehicles": sum(sum(s["vehicles"].values()) for s in sigs),
            "max_wait_s": max((max(s["waiting_s"].values()) for s in sigs), default=0),
        }

    def snapshot(self) -> dict:
        ambs = [a for i in self.intersections.values() for a in i.ambulances()]
        ambs.sort(key=lambda r: -r["last_seen"])
        sigs = [i.snapshot() for i in self.intersections.values()]
        return {
            "ts": round(time.time(), 3),
            "mode": self.mode,
            "intersections": sigs,
            "ambulances": ambs[:30],
            "metrics": self.metrics(sigs),
        }
