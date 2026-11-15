"""SUMO live view for the dashboard.

Runs one of the networks built by sumo/build_islamabad.py through TraCI and streams it to the
dashboard (vehicles, signal states, per-approach virtual cameras, decisions, metrics).

Controllers:
  equiflow  every signalised junction is driven by the same IntersectionController that drives the
            camera junction (base controller + ambulance preemption + fair recovery). Each approach
            has a virtual camera that applies the same K-of-M voting rule as the live vision
            pipeline, so an ambulance must be "confirmed" before it gets priority.
  fixed     SUMO's static signal plan (baseline)
  actuated  SUMO's detector-actuated plan (baseline)

TraCI is not thread-safe, so everything that talks to SUMO runs in one worker thread; the API
only queues commands for it."""
from __future__ import annotations

import csv
import logging
import math
import os
import queue
import random
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

from .bus import EventBus
from .config import AppConfig
from .controllers import IntersectionController, create_base
from .controllers.types import PreemptConfig, Timing

log = logging.getLogger("equiflow.sumo")

SUMO_DIR = Path(__file__).resolve().parents[2] / "sumo"
SCENARIOS = ("low", "medium", "high", "asymmetric")
CONTROLLERS = ("equiflow", "fixed", "actuated")
BASES = ("adaptive", "marl", "fixed_time")   # what EquiFlow uses under the priority/safety layer
VTYPES = ("car", "motorcycle", "bus", "truck", "ambulance")
COMPASS = ("North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West")
FRAME_EVERY_S = 0.15          # real seconds between frames sent to the dashboard
SIM_END_S = 3600.0

NETWORK_INFO = {
    "cross_signal": ("4-arm signalised crossing", "Jinnah Ave / Constitution Ave style at-grade junction"),
    "t_signal": ("Signalised T-junction", "Sector service road meeting an avenue"),
    "t_priority": ("Give-way T-junction (no signal)", "Quiet sector street"),
    "y_junction": ("Y-junction (no signal)", "Merging arterials"),
    "five_way_signal": ("5-arm signalised chowk", "Complex multi-road chowk"),
    "six_way": ("6-arm signalised chowk", "Six-road junction"),
    "roundabout": ("Roundabout (no signal)", "Chowk roundabout, clockwise (left-hand traffic)"),
    "sector_grid": ("Sector grid, 3x3 blocks", "G/F/I sector-style grid with five signals"),
    "diamond": ("Diamond interchange", "Zero Point / Faizabad style, two signalised ramp terminals"),
}


# --------------------------------------------------------------------------- SUMO discovery
def sumo_home() -> Path | None:
    h = os.environ.get("SUMO_HOME")
    if h and Path(h).is_dir():
        return Path(h)
    try:
        import sumo  # pip install eclipse-sumo
        return Path(sumo.SUMO_HOME)
    except Exception:  # noqa: BLE001
        pass
    for p in (r"C:\Program Files (x86)\Eclipse\Sumo", r"C:\Program Files\Eclipse\Sumo", r"C:\Program Files (x86)\SUMO"):
        if Path(p).is_dir():
            return Path(p)
    return None


def _import_sumo_tools(home: Path | None):
    if home is not None and str(home / "tools") not in sys.path:
        sys.path.append(str(home / "tools"))
    import sumolib  # noqa: F401
    import traci  # noqa: F401
    import traci.constants  # noqa: F401
    return traci


def _exe(home: Path | None, name: str) -> str:
    e = name + (".exe" if os.name == "nt" else "")
    if home is not None and (home / "bin" / e).is_file():
        return str(home / "bin" / e)
    found = shutil.which(e)
    if not found:
        raise RuntimeError(f"cannot find {e}; set SUMO_HOME")
    return found


# --------------------------------------------------------------------------- catalogue
def list_networks() -> list[dict]:
    out = []
    for p in sorted((SUMO_DIR / "networks").glob("*_fixed.net.xml")):
        name = p.name[: -len("_fixed.net.xml")]
        scen = [s for s in SCENARIOS if (SUMO_DIR / "routes" / f"{name}_{s}.rou.xml").is_file()]
        title, desc = NETWORK_INFO.get(name, (name.replace("_", " ").title(), ""))
        out.append({"id": name, "title": title, "description": desc, "scenarios": scen,
                    "actuated": (SUMO_DIR / "networks" / f"{name}_actuated.net.xml").is_file()})
    return out


def _read_csv(f: Path, numeric: tuple[str, ...]) -> list[dict]:
    if not f.is_file():
        return []
    rows = []
    with f.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            row = dict(r)
            for k in numeric:
                try:
                    row[k] = float(r[k]) if r.get(k, "") != "" else None
                except (ValueError, TypeError):
                    row[k] = None
            rows.append(row)
    return rows


def read_robustness() -> list[dict]:
    return _read_csv(SUMO_DIR / "results" / "robustness.csv",
                     ("miss_prob", "fp_prob", "ambulance_wait_s", "car_wait_s", "priority_runs",
                      "false_confirmations", "detection_to_green_s", "corridor_requests"))


def read_training() -> list[dict]:
    return _read_csv(SUMO_DIR.parent / "marl" / "training_log.csv",
                     ("episode", "epsilon", "mean_wait_s", "ambulance_wait_s", "trips", "updates", "loss"))


def read_results() -> list[dict]:
    # the held-out matrix (run_matrix.py, seeds 6-10, all controllers) when it exists, else the older runs
    f = SUMO_DIR / "results" / "heldout" / "summary_by_class.csv"
    if not f.is_file():
        f = SUMO_DIR / "results" / "summary_by_class.csv"
    if not f.is_file():
        return []
    rows = []
    with f.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            row = dict(r)
            for k in ("completed", "mean_travel_time_s", "mean_waiting_s", "mean_time_loss_s", "mean_stopped_vehicles"):
                try:
                    row[k] = float(r[k]) if r.get(k, "") != "" else None
                except ValueError:
                    row[k] = None
            rows.append(row)
    return rows


# --------------------------------------------------------------------------- geometry
def _r(p) -> list[float]:
    return [round(p[0], 2), round(p[1], 2)]


def _compass(deg: float) -> str:
    return COMPASS[int(((deg + 22.5) % 360) // 45)]


def build_geometry(net_path: Path) -> dict:
    import sumolib
    net = sumolib.net.readNet(str(net_path), withInternal=True)
    xmin, ymin, xmax, ymax = net.getBoundary()
    lanes, lane_len = [], {}
    for e in net.getEdges(withInternal=True):
        internal = e.getFunction() == "internal"
        for ln in e.getLanes():
            lane_len[ln.getID()] = ln.getLength()
            lanes.append({"id": ln.getID(), "edge": e.getID(), "internal": internal,
                          "width": round(ln.getWidth(), 2), "shape": [_r(p) for p in ln.getShape()]})
    junctions = []
    for n in net.getNodes():
        if n.getType() == "internal":
            continue
        shp = n.getShape()
        if shp:
            junctions.append({"id": n.getID(), "type": n.getType(), "shape": [_r(p) for p in shp],
                              "x": round(n.getCoord()[0], 2), "y": round(n.getCoord()[1], 2)})
    tls = []
    for t in net.getTrafficLights():
        groups: dict[str, dict] = defaultdict(lambda: {"links": set(), "lanes": set(), "lane_links": set()})
        n_links = 0
        for in_lane, _out, idx in t.getConnections():
            g = groups[in_lane.getEdge().getID()]
            g["links"].add(idx)
            g["lanes"].add(in_lane.getID())
            g["lane_links"].add((in_lane.getID(), idx))
            n_links = max(n_links, idx + 1)
        approaches = []
        for eid, g in groups.items():
            edge = net.getEdge(eid)
            shp = edge.getLanes()[0].getShape()
            (x1, y1), (x2, y2) = shp[-2], shp[-1]
            heading = (math.degrees(math.atan2(x2 - x1, y2 - y1)) + 360) % 360   # direction of travel
            from_deg = (heading + 180) % 360                                      # where traffic comes from
            stops = [net.getLane(lid).getShape()[-1] for lid in g["lanes"]]
            approaches.append({"edge": eid, "from_deg": round(from_deg, 1), "heading": round(heading, 1),
                               "links": sorted(g["links"]), "lanes": sorted(g["lanes"]),
                               "lane_links": sorted(g["lane_links"]),
                               "length": round(edge.getLength(), 1),
                               "stop": _r((sum(p[0] for p in stops) / len(stops), sum(p[1] for p in stops) / len(stops)))})
        approaches.sort(key=lambda a: a["from_deg"])
        labels = [_compass(a["from_deg"]) for a in approaches]
        dup = Counter(labels)
        for a, lab in zip(approaches, labels):
            a["id"] = lab if dup[lab] == 1 else f"{lab} ({a['edge']})"
        cx = sum(a["stop"][0] for a in approaches) / len(approaches)
        cy = sum(a["stop"][1] for a in approaches) / len(approaches)
        tls.append({"id": t.getID(), "x": round(cx, 2), "y": round(cy, 2), "n_links": n_links,
                    "approaches": approaches})
    tls.sort(key=lambda t: t["id"])
    return {"boundary": [round(xmin, 2), round(ymin, 2), round(xmax, 2), round(ymax, 2)],
            "lanes": lanes, "junctions": junctions, "tls": tls, "_lane_len": lane_len, "_net_path": Path(net_path)}


# --------------------------------------------------------------------------- signal groups
def _green_phases(net_path: Path) -> dict[str, list[str]]:
    """Green phase states of each traffic light's static program in the .net.xml (no yellows)."""
    import xml.etree.ElementTree as ET
    out: dict[str, list[str]] = {}
    for tl in ET.parse(net_path).getroot().iter("tlLogic"):
        states = []
        for ph in tl.iter("phase"):
            s = ph.get("state", "")
            if s and "y" not in s.lower() and any(ch in "Gg" for ch in s) and s not in states:
                states.append(s)
        out.setdefault(tl.get("id"), states)
    return out


def _control_groups(t: dict, green_states: list[str], phasing: str) -> tuple[list[dict], dict[str, str]]:
    """What the controller switches between at one junction.

    phasing="phases"   the green phases of the junction's signal plan (e.g. North+South together,
                       then East+West). Same capacity as the SUMO baselines; an ambulance gets the
                       phase that gives its approach a protected green.
    phasing="approach" one approach at a time (like the four-camera junction)."""
    appr = t["approaches"]
    n = t["n_links"]
    if phasing == "phases" and green_states:
        groups = []
        for k, s in enumerate(green_states):
            s = s.ljust(n, "r")
            strong = [a["id"] for a in appr if any(s[i] == "G" for i in a["links"])]
            weak = [a["id"] for a in appr if any(s[i] in "Gg" for i in a["links"])]
            served = strong or weak
            lanes = sorted({ln for a in appr for ln, i in _lane_links(a) if s[i] in "Gg"})
            groups.append({"id": " + ".join(served) or f"Phase {k + 1}", "state": s, "approaches": weak, "lanes": lanes,
                           "green": frozenset(i for i, ch in enumerate(s) if ch in "Gg")})
        # a short turn phase whose movements are all allowed (at least permissively) in a main phase only
        # adds clearance time when served on its own, so it is folded into that main phase
        groups = [g for g in groups if not any(g["green"] < h["green"] for h in groups)]
        seen = Counter(g["id"] for g in groups)
        idx: Counter = Counter()
        for g in groups:
            if seen[g["id"]] > 1:
                idx[g["id"]] += 1
                g["id"] = f"{g['id']} ({'main' if idx[g['id']] == 1 else 'turns'})" if seen[g["id"]] == 2 \
                    else f"{g['id']} #{idx[g['id']]}"
        best: dict[str, str] = {}
        for a in appr:
            def score(g, a=a):
                return sum(2 if g["state"][i] == "G" else 1 if g["state"][i] == "g" else 0 for i in a["links"])
            top = max(groups, key=score)
            if score(top) > 0:
                best[a["id"]] = top["id"]
        return groups, best
    groups = []
    for a in appr:
        s = ["r"] * n
        for i in a["links"]:
            s[i] = "G"
        groups.append({"id": a["id"], "state": "".join(s), "approaches": [a["id"]], "lanes": list(a["lanes"])})
    return groups, {a["id"]: a["id"] for a in appr}


def _lane_links(a: dict):
    """(lane, link index) pairs of an approach."""
    return a.get("lane_links", [])


# --------------------------------------------------------------------------- virtual camera
class _Track:
    __slots__ = ("votes", "probs", "active", "announced", "p")

    def __init__(self, m: int):
        self.votes: deque = deque(maxlen=m)
        self.probs: deque = deque(maxlen=m)
        self.active = False
        self.announced = False
        self.p = 0.0


class VirtualCamera:
    """Stands in for detector + classifier on a SUMO approach. The classifier output is simulated
    (ambulances score high, other vehicles low, both with noise), but the decision rule is the real
    one from the vision config: an ambulance is confirmed when K of the last M frames vote
    ambulance and the mean probability is high enough; it is released when votes drop to `release`."""

    def __init__(self, cfg, rng: random.Random, frames_per_step: int, miss_prob: float = 0.0,
                 fp_prob: float = 0.0):
        self.v, self.rng, self.fps_step = cfg, rng, frames_per_step
        self.miss_prob = miss_prob    # detector misses the vehicle in a frame (no vote that frame)
        self.fp_prob = fp_prob        # classifier scores a non-ambulance like an ambulance in a frame
        self.tracks: dict[str, _Track] = {}
        self.false_confirms = 0       # non-ambulances that got confirmed (false priority requests)

    def _p(self, vtype: str) -> float:
        if vtype == "ambulance" or (self.fp_prob and self.rng.random() < self.fp_prob):
            return self.rng.betavariate(9.0, 1.6)      # mean about 0.85
        return self.rng.betavariate(1.2, 14.0)         # mean about 0.08

    def observe(self, vid: str, vtype: str) -> _Track:
        v = self.v
        t = self.tracks.get(vid)
        if t is None:
            t = self.tracks[vid] = _Track(v.m)
        for _ in range(self.fps_step):
            if self.miss_prob and self.rng.random() < self.miss_prob:
                continue
            p = self._p(vtype)
            t.probs.append(p)
            t.votes.append(int(p >= v.th_frame))
        if not t.probs:
            return t
        t.p = t.probs[-1]
        n = sum(t.votes)
        mean = sum(t.probs) / len(t.probs)
        if not t.active and n >= v.k and mean >= v.mean_min:
            t.active = True
            if vtype != "ambulance" and not t.announced:
                self.false_confirms += 1
        elif t.active and n <= v.release:
            t.active = False
        return t

    def forget(self, vid: str) -> None:
        self.tracks.pop(vid, None)


# --------------------------------------------------------------------------- live runner
class SumoLive:
    def __init__(self, cfg: AppConfig, bus: EventBus):
        self.cfg, self.bus = cfg, bus
        self.home = sumo_home()
        self.available, self.reason = self._check()
        self.state = "idle"            # idle | starting | running | paused | finished | error
        self.error: str | None = None
        self.run: dict | None = None
        self.run_id = 0
        self.geometry: dict | None = None
        self.frame: dict | None = None
        self.frame_seq = 0
        self.events: deque = deque(maxlen=120)
        self._cmds: queue.Queue = queue.Queue()
        # headless batch evaluation (sumo/run_equiflow.py): no pacing, no frames, tripinfo written
        self.headless = False
        self.marl_extra: dict = {}      # extra MarlController params (the trainer passes its learner here)
        self.tripinfo: Path | None = None
        self.step_override: float | None = None
        self.end_s = SIM_END_S
        self.stopped_by_class: dict[str, int] = defaultdict(int)
        self.steps = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._start_lock = threading.Lock()

    def _check(self) -> tuple[bool, str]:
        try:
            _import_sumo_tools(self.home)
            _exe(self.home, "sumo")
        except Exception as e:  # noqa: BLE001
            return False, f"SUMO not available: {e}. Install SUMO (or pip install eclipse-sumo) and set SUMO_HOME."
        if not (SUMO_DIR / "networks").is_dir():
            return False, f"no networks in {SUMO_DIR / 'networks'}; run sumo/build_islamabad.py"
        return True, "ok"

    # ---------------------------------------------------------------- public API (any thread)
    def status(self) -> dict:
        return {"available": self.available, "reason": self.reason, "state": self.state, "error": self.error,
                "run": self.run, "run_id": self.run_id,
                "sumo_home": str(self.home) if self.home else None}

    def public_geometry(self) -> dict | None:
        if self.geometry is None:
            return None
        return {k: v for k, v in self.geometry.items() if not k.startswith("_")} | {"run_id": self.run_id}

    def start(self, network: str, scenario: str = "medium", controller: str = "equiflow",
              speed: float | None = None, seed: int = 1, base: str | None = None) -> dict:
        if not self.available:
            raise RuntimeError(self.reason)
        if controller not in CONTROLLERS:
            raise ValueError(f"controller must be one of {CONTROLLERS}")
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {SCENARIOS}")
        ctrl_net = "actuated" if controller == "actuated" else "fixed"
        net = SUMO_DIR / "networks" / f"{network}_{ctrl_net}.net.xml"
        rou = SUMO_DIR / "routes" / f"{network}_{scenario}.rou.xml"
        if not net.is_file() or not rou.is_file():
            raise FileNotFoundError(f"missing {net.name} or {rou.name}; run sumo/build_islamabad.py")
        with self._start_lock:
            self.stop()
            self.state, self.error = "starting", None
            geo = build_geometry(net)
            self.run_id += 1
            self.geometry = geo
            self.frame = None
            self.events.clear()
            base = base or self.cfg.sumo.base_controller or self.cfg.controller
            if controller == "equiflow" and base not in BASES:
                raise ValueError(f"base controller must be one of {BASES}")
            self.run = {"network": network, "scenario": scenario, "controller": controller, "seed": seed,
                        "speed": float(speed or self.cfg.sumo.speed), "base": base,
                        "title": NETWORK_INFO.get(network, (network, ""))[0]}
            self._stop = threading.Event()
            self._cmds = queue.Queue()
            self._thread = threading.Thread(target=self._worker, args=(net, rou, geo, dict(self.run), self._stop),
                                            daemon=True, name="sumo-live")
            self._thread.start()
        self._event(None, "sumo_started", **{k: self.run[k] for k in ("network", "scenario", "controller", "base")})
        return self.status()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=10)
        self._thread = None
        if self.state in ("running", "starting", "paused"):
            self.state = "idle"

    def set_speed(self, speed: float) -> None:
        if self.run:
            self.run["speed"] = max(0.1, min(50.0, float(speed)))
            self._cmds.put(("speed", self.run["speed"]))

    def pause(self, paused: bool) -> None:
        self._cmds.put(("pause", bool(paused)))

    def dispatch_ambulance(self, tls: str | None = None, approach: str | None = None) -> None:
        if self.state not in ("running", "paused"):
            raise RuntimeError("the simulation is not running")
        self._cmds.put(("ambulance", tls, approach))

    def preempt(self, tls: str, approach: str, duration_s: float) -> None:
        if not self.run or self.run["controller"] != "equiflow":
            raise RuntimeError("manual priority needs the EquiFlow controller")
        self._cmds.put(("preempt", tls, approach, float(duration_s)))

    # ---------------------------------------------------------------- helpers
    def _event(self, tls: str | None, type: str, **data) -> None:
        sim_t = self.frame["t"] if self.frame else 0.0
        e = self.bus.publish(type, origin="sumo", intersection_id=f"sumo/{tls}" if tls else None,
                             tls=tls, sim_time=round(data.pop("sim_time", sim_t), 1), **data)
        self.events.appendleft(e)

    # ---------------------------------------------------------------- worker thread
    def _worker(self, net: Path, rou: Path, geo: dict, run: dict, stop: threading.Event) -> None:
        traci = _import_sumo_tools(self.home)
        tc = traci.constants
        sc = self.cfg.sumo
        label = f"equiflow-live-{self.run_id}"
        cmd = [_exe(self.home, "sumo"), "-n", str(net), "-r", str(rou),
               "--step-length", str(self.step_override or sc.step_s),
               "--begin", "0", "--end", str(int(self.end_s)), "--seed", str(run["seed"]),
               "--no-step-log", "true", "--no-warnings", "true", "--time-to-teleport", "-1",
               "--waiting-time-memory", "10000", "--collision.action", "warn"]
        if self.tripinfo is not None:
            cmd += ["--tripinfo-output", str(self.tripinfo)]
        try:
            traci.start(cmd, label=label)
            conn = traci.getConnection(label)
        except Exception as e:  # noqa: BLE001
            self.state, self.error = "error", f"could not start SUMO: {e}"
            log.exception("could not start SUMO")
            return
        try:
            self._loop(conn, tc, geo, run, stop)
        except Exception as e:  # noqa: BLE001
            if not stop.is_set():
                self.state, self.error = "error", str(e)
                log.exception("SUMO live run failed")
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _loop(self, conn, tc, geo: dict, run: dict, stop: threading.Event) -> None:
        sc, vcfg = self.cfg.sumo, self.cfg.vision
        rng = random.Random(run["seed"])
        step = self.step_override or sc.step_s
        fps_step = max(1, round(sc.camera_fps * step))
        mode = run["controller"]
        lane_len = geo["_lane_len"]
        tls_list = geo["tls"]

        # lane -> (tls id, approach id) for the virtual cameras
        lane_owner: dict[str, tuple[str, str]] = {}
        for t in tls_list:
            for a in t["approaches"]:
                for ln in a["lanes"]:
                    lane_owner[ln] = (t["id"], a["id"])

        cams = {t["id"]: VirtualCamera(vcfg, rng, fps_step, sc.camera_miss_prob, sc.camera_fp_prob) for t in tls_list}
        self._cams = cams
        link_appr = {t["id"]: {i: a["id"] for a in t["approaches"] for i in a["links"]} for t in tls_list}
        corridor_amb: set[str] = set()          # vehicles a camera confirmed as ambulances
        corridor_sent: set[tuple[str, str]] = set()
        self.corridor_requests = 0
        ctrls: dict[str, IntersectionController] = {}
        decisions: dict[str, deque] = {t["id"]: deque(maxlen=8) for t in tls_list}
        last_green_end: dict[str, dict[str, float]] = {t["id"]: {a["id"]: 0.0 for a in t["approaches"]} for t in tls_list}
        prev_lamps: dict[str, dict[str, str]] = {}
        sim_now = [0.0]

        phases: dict[str, list[dict]] = {}
        amb_phase: dict[str, dict[str, str]] = {}
        if mode == "equiflow":
            timing = Timing(**self.cfg.timing.model_dump())
            pcfg = PreemptConfig(**self.cfg.preempt.model_dump())
            programs = _green_phases(geo["_net_path"])
            for t in tls_list:
                tid = t["id"]
                phases[tid], amb_phase[tid] = _control_groups(t, programs.get(tid, []), sc.phasing)
                groups = tuple(p["id"] for p in phases[tid])

                def emit(type, _tid=tid, **kw):
                    if type == "phase_changed":
                        c = ctrls.get(_tid)
                        a = kw.get("approach")
                        if c is not None and a is not None:
                            waited = max(0.0, sim_now[0] - c.last_green_end.get(a, sim_now[0]))
                            kw["vehicles"] = c.vehicles.get(a, 0)
                            kw["waited_s"] = round(waited, 1)
                        decisions[_tid].appendleft({"t": round(sim_now[0], 1), **kw})
                    self._event(_tid, type, sim_time=sim_now[0], **kw)

                base_name = run.get("base") or sc.base_controller or self.cfg.controller
                if base_name == "marl":
                    params = {**sc.marl_params, **self.marl_extra}
                else:
                    params = sc.controller_params or self.cfg.controller_params
                base = create_base(base_name, timing, params)
                ctrls[tid] = IntersectionController(tid, base, timing, pcfg, approaches=groups, emit=emit, now=0.0)
        self._phases = phases
        self._appr_view: dict[str, dict] = {}

        sub_vars = [tc.VAR_POSITION, tc.VAR_ANGLE, tc.VAR_TYPE, tc.VAR_SPEED, tc.VAR_LANE_ID,
                    tc.VAR_LANEPOSITION, tc.VAR_ACCUMULATED_WAITING_TIME, tc.VAR_TIMELOSS]
        depart: dict[str, float] = {}
        last: dict[str, dict] = {}
        done = {v: {"n": 0, "travel": 0.0, "wait": 0.0, "loss": 0.0} for v in VTYPES}
        amb_count = 0
        paused = False
        speed = run["speed"]
        self._seen = {}
        self.state = "running"
        next_wall = time.monotonic()

        while not stop.is_set():
            # ---------------- commands
            while True:
                try:
                    c = self._cmds.get_nowait()
                except queue.Empty:
                    break
                if c[0] == "speed":
                    speed = c[1]
                elif c[0] == "pause":
                    paused = c[1]
                    self.state = "paused" if paused else "running"
                elif c[0] == "ambulance":
                    amb_count += 1
                    self._dispatch(conn, geo, rng, c[1], c[2], amb_count, sim_now[0])
                elif c[0] == "preempt" and c[1] in ctrls:
                    group = amb_phase.get(c[1], {}).get(c[2], c[2])
                    if group in ctrls[c[1]].approaches:
                        ctrls[c[1]].inject(group, c[3], sim_now[0])
                    self._event(c[1], "manual_preempt", approach=c[2], duration_s=c[3], sim_time=sim_now[0])
            if paused:
                self._publish_frame(conn, geo, run, sim_now[0], last, cams, ctrls, decisions, last_green_end,
                                    done, mode, force=False)
                stop.wait(0.1)
                next_wall = time.monotonic()
                continue

            # ---------------- one simulation step
            conn.simulationStep()
            now = conn.simulation.getTime()
            sim_now[0] = now
            for vid in conn.simulation.getDepartedIDList():
                conn.vehicle.subscribe(vid, sub_vars)
                depart[vid] = now
            for vid in conn.simulation.getArrivedIDList():
                d = last.pop(vid, None)
                t0 = depart.pop(vid, None)
                for cam in cams.values():
                    cam.forget(vid)
                if d is not None and t0 is not None and d["type"] in done:
                    s = done[d["type"]]
                    s["n"] += 1
                    s["travel"] += now - t0
                    s["wait"] += d["wait"]
                    s["loss"] += d["loss"]
            res = conn.vehicle.getAllSubscriptionResults()
            for vid, r in res.items():
                x, y = r[tc.VAR_POSITION]
                last[vid] = {"x": x, "y": y, "a": r[tc.VAR_ANGLE], "type": r[tc.VAR_TYPE], "v": r[tc.VAR_SPEED],
                             "lane": r[tc.VAR_LANE_ID], "pos": r[tc.VAR_LANEPOSITION],
                             "wait": r[tc.VAR_ACCUMULATED_WAITING_TIME], "loss": r[tc.VAR_TIMELOSS]}

            # ---------------- virtual cameras -> controllers
            seen: dict[str, dict[str, list]] = {t["id"]: {a["id"]: [] for a in t["approaches"]} for t in tls_list}
            for vid, d in last.items():
                owner = lane_owner.get(d["lane"])
                if owner is None:
                    continue
                dist = lane_len.get(d["lane"], 0.0) - d["pos"]
                if dist > sc.camera_range_m:
                    continue
                tid, aid = owner
                tr = cams[tid].observe(vid, d["type"])
                seen[tid][aid].append((vid, d, tr, dist))
                if tr.active:
                    corridor_amb.add(vid)
                if tr.active and not tr.announced:
                    tr.announced = True
                    self._event(tid, "ambulance_detected", approach=aid, track_id=vid,
                                confidence=round(sum(tr.probs) / len(tr.probs), 3), distance_m=round(dist, 1),
                                sim_time=now)
            # ---------------- green corridor: signals further along a confirmed ambulance's route start
            # clearing before it reaches their own cameras (route-aware preemption)
            if mode == "equiflow" and sc.corridor:
                for vid in list(corridor_amb):
                    d = last.get(vid)
                    if d is None:
                        corridor_amb.discard(vid)
                        continue
                    try:
                        upcoming = conn.vehicle.getNextTLS(vid)
                    except Exception:  # noqa: BLE001
                        continue
                    v = max(d["v"], 5.0)
                    for tls_id, link, dist, _state in upcoming:
                        if dist > sc.corridor_range_m or dist / v > sc.corridor_eta_s:
                            break
                        if tls_id not in ctrls or dist <= sc.camera_range_m:
                            continue          # out of our control, or its own camera already sees it
                        aid = link_appr[tls_id].get(link)
                        group = amb_phase[tls_id].get(aid) if aid else None
                        if group is None:
                            continue
                        ctrls[tls_id].inject(group, step * 2 + 0.5, now)   # refreshed every step while it applies
                        if (vid, tls_id) not in corridor_sent:
                            corridor_sent.add((vid, tls_id))
                            self.corridor_requests += 1
                            self._event(tls_id, "corridor_request", approach=aid, vehicle=vid,
                                        distance_m=round(dist, 1), eta_s=round(dist / v, 1), sim_time=now)

            for t in tls_list:
                tid = t["id"]
                amb_appr = {aid: any(tr.active for *_, tr, _ in items) for aid, items in seen[tid].items()}
                if mode == "equiflow":
                    c = ctrls[tid]
                    per_lane: Counter = Counter(d["lane"] for items in seen[tid].values() for _, d, _, _ in items)
                    for p in phases[tid]:
                        present = any(amb_appr.get(aid) and amb_phase[tid].get(aid) == p["id"] for aid in amb_appr)
                        c.observe(p["id"], present, now, vehicles=sum(per_lane[ln] for ln in p["lanes"]))
                    if hasattr(c.base, "accumulate"):     # learning controller: cost since its last decision
                        halting = sum(1 for items in seen[tid].values() for _, d, _, _ in items if d["v"] < 0.1)
                        c.base.accumulate(halting, max(c._waiting(p, now) for p in c.approaches), step)
                    c.tick(now)
                    glamps = c.lamps()
                    state = "r" * t["n_links"]
                    for p in phases[tid]:
                        if glamps[p["id"]] == "green":
                            state = p["state"]
                        elif glamps[p["id"]] == "yellow":
                            state = "".join("y" if ch in "Gg" else "r" for ch in p["state"])
                    conn.trafficlight.setRedYellowGreenState(tid, state)
                else:
                    state = conn.trafficlight.getRedYellowGreenState(tid)
                lamps = {}
                for a in t["approaches"]:
                    cs = [state[i] for i in a["links"] if i < len(state)]
                    lamps[a["id"]] = "green" if any(ch in "Gg" for ch in cs) else \
                        "yellow" if any(ch in "yY" for ch in cs) else "red"
                pl = prev_lamps.get(tid, {})
                for aid, lamp in lamps.items():
                    if mode != "equiflow" and lamp == "green" and pl.get(aid) != "green":
                        decisions[tid].appendleft({"t": round(now, 1), "approach": aid, "source": mode,
                                                   "vehicles": len(seen[tid][aid]),
                                                   "waited_s": round(now - last_green_end[tid][aid], 1)})
                    if lamp != "green" and pl.get(aid) == "green":
                        last_green_end[tid][aid] = now
                prev_lamps[tid] = lamps
                self._appr_view[tid] = {
                    "state": state, "lamps": lamps, "ambulance": amb_appr,
                    "vehicles": {aid: len(items) for aid, items in seen[tid].items()},
                    "waiting_s": {aid: 0.0 if lamps[aid] != "red" else round(now - last_green_end[tid][aid], 1)
                                  for aid in lamps}}
            self._seen = seen

            if self.headless:
                self.steps += 1
                for d in last.values():
                    if d["v"] < 0.1:
                        self.stopped_by_class[d["type"]] += 1
                self._ctrls = ctrls
            else:
                # ---------------- frame for the dashboard
                self._publish_frame(conn, geo, run, now, last, cams, ctrls, decisions, last_green_end, done, mode,
                                    force=False)

            if now >= self.end_s or conn.simulation.getMinExpectedNumber() == 0:
                if self.headless:
                    self.state = "finished"
                    return
                self._publish_frame(conn, geo, run, now, last, cams, ctrls, decisions, last_green_end, done, mode,
                                    force=True)
                self.state = "finished"
                self._event(None, "sumo_finished", sim_time=now)
                return

            # ---------------- pacing (speed = simulated seconds per real second)
            if self.headless:
                continue
            next_wall += step / max(0.1, speed)
            lag = next_wall - time.monotonic()
            if lag > 0:
                stop.wait(lag)
            elif lag < -1.0:
                next_wall = time.monotonic()   # running flat out; don't try to catch up

    def _dispatch(self, conn, geo, rng, tls_id, approach_id, n, now) -> None:
        """Insert an ambulance. With a junction (and optionally an approach) it starts on that approach,
        otherwise on a random signalised approach, and drives to a random reachable edge."""
        cands = []
        for t in geo["tls"]:
            if tls_id and t["id"] != tls_id:
                continue
            for a in t["approaches"]:
                if approach_id and a["id"] != approach_id:
                    continue
                cands.append((t["id"], a["id"], a["edge"]))
        if not cands:
            edges = sorted({ln["edge"] for ln in geo["lanes"] if not ln["internal"]})
            cands = [(None, None, e) for e in edges]
        all_edges = sorted({ln["edge"] for ln in geo["lanes"] if not ln["internal"]})
        for _ in range(60):
            tid, aid, src = rng.choice(cands)
            dst = rng.choice(all_edges)
            if dst == src:
                continue
            try:
                route = conn.simulation.findRoute(src, dst, vType="ambulance")
            except Exception:  # noqa: BLE001
                continue
            if len(route.edges) < 2:
                continue
            vid, rid = f"ambulance_live{n}", f"r_ambulance_live{n}"
            conn.route.add(rid, list(route.edges))
            conn.vehicle.add(vid, rid, typeID="ambulance", departLane="best", departSpeed="max")
            self._event(tid, "ambulance_dispatched", approach=aid, vehicle=vid, sim_time=now,
                        route=list(route.edges))
            return
        self._event(None, "ambulance_dispatch_failed", sim_time=now)

    def _publish_frame(self, conn, geo, run, now, last, cams, ctrls, decisions, last_green_end, done, mode,
                       force: bool) -> None:
        wall = time.monotonic()
        if not force and wall - getattr(self, "_last_frame_wall", 0.0) < FRAME_EVERY_S:
            return
        self._last_frame_wall = wall
        seen = getattr(self, "_seen", {})
        vtype_idx = {v: i for i, v in enumerate(VTYPES)}
        vehicles = [[vid, round(d["x"], 1), round(d["y"], 1), round(d["a"]), vtype_idx.get(d["type"], 0),
                     round(d["v"], 1)] for vid, d in last.items()]
        halting = sum(1 for d in last.values() if d["v"] < 0.1)

        junctions = []
        for t in geo["tls"]:
            tid = t["id"]
            view = getattr(self, "_appr_view", {}).get(tid)
            if view is None:
                view = {"state": "", "lamps": {a["id"]: "red" for a in t["approaches"]},
                        "ambulance": {a["id"]: False for a in t["approaches"]},
                        "vehicles": {a["id"]: 0 for a in t["approaches"]},
                        "waiting_s": {a["id"]: 0.0 for a in t["approaches"]}}
            lamps = view["lamps"]
            if mode == "equiflow":
                snap = ctrls[tid].snapshot(now)
                snap["phase_vehicles"] = snap.pop("vehicles")
                snap.pop("lamps")
                snap.pop("ambulance")
                snap.pop("waiting_s")
                snap["phases"] = [{"id": p["id"], "approaches": p["approaches"]} for p in self._phases.get(tid, [])]
            else:
                try:
                    remaining = max(0.0, conn.trafficlight.getNextSwitch(tid) - now)
                except Exception:  # noqa: BLE001
                    remaining = None
                cur = next((a for a, lamp in lamps.items() if lamp == "green"), None) or \
                    next((a for a, lamp in lamps.items() if lamp == "yellow"), None)
                stage = "GREEN" if any(v == "green" for v in lamps.values()) else \
                    "YELLOW" if any(v == "yellow" for v in lamps.values()) else "ALL_RED"
                snap = {"id": tid, "controller": mode, "mode": "NORMAL", "stage": stage, "current": cur,
                        "active_preempt": None, "stage_remaining_s": None if remaining is None else round(remaining, 1),
                        "recovery_plan": [], "phases": [],
                        "stats": {"preemptions": 0, "latency_avg_s": None, "latency_last_s": None,
                                  "latency_max_s": None, "total_preempt_s": 0.0}}
            snap.update(lamps=lamps, ambulance=view["ambulance"], vehicles=view["vehicles"],
                        waiting_s=view["waiting_s"], signal_state=view["state"])
            cams_out = {}
            for a in t["approaches"]:
                items = seen.get(tid, {}).get(a["id"], [])
                cams_out[a["id"]] = [[vid, vtype_idx.get(d["type"], 0), round(tr.p, 2), sum(tr.votes), tr.active,
                                      round(dist, 1)] for vid, d, tr, dist in sorted(items, key=lambda i: i[3])]
            snap["cameras"] = cams_out
            snap["decisions"] = list(decisions[tid])
            junctions.append(snap)

        per_class = {}
        for v, s in done.items():
            n = s["n"]
            per_class[v] = {"completed": n,
                            "mean_travel_time_s": round(s["travel"] / n, 1) if n else None,
                            "mean_waiting_s": round(s["wait"] / n, 1) if n else None,
                            "mean_time_loss_s": round(s["loss"] / n, 1) if n else None}
        lat = [x for c in ctrls.values() for x in c.stats.latencies_s]
        self.frame = {
            "run_id": self.run_id, "t": round(now, 1), "state": self.state, "vehicles": vehicles,
            "junctions": junctions,
            "metrics": {"in_network": len(last), "halting": halting,
                        "arrived": sum(s["n"] for s in done.values()),
                        "preemptions": sum(c.stats.preemptions for c in ctrls.values()),
                        "latency_avg_s": round(sum(lat) / len(lat), 2) if lat else None,
                        "latency_max_s": round(max(lat), 2) if lat else None,
                        "ambulances_in_network": sum(1 for d in last.values() if d["type"] == "ambulance"),
                        "per_class": per_class},
            "events": list(self.events)[:40],
        }
        self.frame_seq += 1
