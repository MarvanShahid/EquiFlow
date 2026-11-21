"""Event log: writes every bus event to a CSV file so runs can be analysed afterwards.

One row per event: ts (unix seconds), iso time, type, intersection_id, approach, origin and the
remaining fields as JSON. High-rate events (ambulance positions) are skipped by default.

    log: {enabled: true, dir: logs, exclude: [ambulance_position]}

A new file is started per backend run (events_YYYYmmdd_HHMMSS.csv). `episodes()` turns a log into one
row per preemption: detection -> green -> end -> recovery, which is the evidence for the
"logged preemption with recovery" exit criterion. See scripts/preempt_report.py.
"""
from __future__ import annotations

import csv
import json
import threading
import time
from datetime import datetime
from pathlib import Path

FIELDS = ["ts", "time", "sim_time", "type", "intersection_id", "approach", "origin", "data"]
_FIXED = {"id", "ts", "type", "intersection_id", "approach", "origin", "sim_time"}


class EventLogger:
    def __init__(self, directory: str | Path, exclude: tuple[str, ...] = ("ambulance_position",),
                 filename: str | None = None):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / (filename or f"events_{datetime.now():%Y%m%d_%H%M%S}.csv")
        self.exclude = set(exclude)
        self._lock = threading.Lock()
        new = not self.path.exists()
        self._f = open(self.path, "a", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=FIELDS)
        if new:
            self._w.writeheader()
            self._f.flush()
        self.rows = 0

    def __call__(self, event: dict) -> None:
        """Bus listener. Never raises into the publisher (the bus also guards this)."""
        if event.get("type") in self.exclude or self._f.closed:
            return
        ts = event.get("ts", time.time())
        row = {
            "ts": ts,
            "time": datetime.fromtimestamp(ts).isoformat(timespec="milliseconds"),
            "sim_time": event.get("sim_time", ""),
            "type": event.get("type"),
            "intersection_id": event.get("intersection_id") or "",
            "approach": event.get("approach") or "",
            "origin": event.get("origin") or "",
            "data": json.dumps({k: v for k, v in event.items() if k not in _FIXED}, default=str),
        }
        with self._lock:
            self._w.writerow(row)
            self._f.flush()          # so a crash or Ctrl+C keeps what happened
            self.rows += 1

    def close(self) -> None:
        with self._lock:
            if not self._f.closed:
                self._f.close()


def read_log(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["ts"] = float(r["ts"])
        r["data"] = json.loads(r["data"] or "{}")
        # SUMO events carry simulated time; headless runs are much faster than real time, so use it
        r["t"] = float(r["sim_time"]) if r.get("sim_time") not in (None, "") else r["ts"]
    return rows


EPISODE_FIELDS = ["intersection_id", "approach", "trigger", "detected_ts", "started_ts", "green_ts",
                  "ended_ts", "served", "detection_to_green_s", "green_latency_s", "preempt_duration_s",
                  "ended_reason", "recovery_plan", "recovery_greens", "recovery_end_ts", "recovery_s", "completed"]


def episodes(rows: list[dict]) -> list[dict]:
    """Group a log into preemption episodes, per intersection, in time order.

    An episode opens at preempt_started and closes at preempt_ended or preempt_timeout. The most
    recent ambulance_detected / manual_preempt on that approach before it is the trigger. Recovery
    greens are the phase_changed events with source 'recovery' after the episode ended and before the
    next episode on that intersection starts."""
    out: list[dict] = []
    open_ep: dict[str, dict] = {}
    last_trigger: dict[tuple[str, str], tuple[str, float]] = {}
    kinds = {"ambulance_detected": "camera", "manual_preempt": "manual", "corridor_request": "corridor"}
    for r in sorted(rows, key=lambda r: r.get("t", r["ts"])):
        iid, a, t, d = r["intersection_id"], r["approach"], r["type"], r["data"]
        now = r.get("t", r["ts"])
        if t in kinds:
            last_trigger[(iid, a)] = last_trigger[(iid, "*")] = (kinds[t], now)
        elif t == "preempt_started":
            # SUMO controllers serve signal groups, cameras report approaches: fall back to the
            # latest trigger at that junction
            trig, det_ts = last_trigger.get((iid, a)) or last_trigger.get((iid, "*"), ("unknown", None))
            ep = {f: None for f in EPISODE_FIELDS}
            ep.update(intersection_id=iid, approach=a, trigger=trig, detected_ts=det_ts,
                      started_ts=now, recovery_greens=0, completed=False)
            out.append(ep)
            open_ep[iid] = ep
        elif t == "preempt_switched" and iid in open_ep:
            open_ep[iid]["approach"] = a
        elif t == "preempt_green" and iid in open_ep and open_ep[iid]["green_ts"] is None:
            ep = open_ep[iid]
            ep["green_ts"] = now
            ep["green_latency_s"] = d.get("latency_s")
            if ep["detected_ts"] is not None:
                ep["detection_to_green_s"] = round(now - ep["detected_ts"], 2)
        elif t in ("preempt_ended", "preempt_timeout") and iid in open_ep:
            ep = open_ep[iid]
            if ep["ended_ts"] is None:
                ep["ended_ts"] = now
                ep["ended_reason"] = "timeout" if t == "preempt_timeout" else "cleared"
                ep["preempt_duration_s"] = d.get("duration_s") or round(now - ep["started_ts"], 1)
                ep["served"] = "; ".join(d.get("served") or [])
        elif t == "recovery_planned" and iid in open_ep:
            open_ep[iid]["recovery_plan"] = "; ".join(d.get("plan") or [])
        elif t == "phase_changed" and iid in open_ep and open_ep[iid]["ended_ts"] is not None:
            if d.get("source") == "recovery":
                open_ep[iid]["recovery_greens"] += 1
        elif t == "mode_changed" and iid in open_ep and open_ep[iid]["ended_ts"] is not None:
            ep = open_ep[iid]
            if d.get("to_mode") == "NORMAL" and ep["recovery_end_ts"] is None:
                ep["recovery_end_ts"] = now          # recovery interval: priority end -> back to normal
                ep["recovery_s"] = round(now - ep["ended_ts"], 1)
    for ep in out:
        ep["completed"] = ep["green_ts"] is not None and ep["ended_ts"] is not None
    return out


def write_episodes(eps: list[dict], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EPISODE_FIELDS)
        w.writeheader()
        w.writerows(eps)
