"""
run_equiflow.py - evaluate the EquiFlow controller in SUMO, in the same format as run_sim.py.

Every signalised junction is driven by the backend's IntersectionController (base controller +
ambulance preemption + green corridor + fair recovery), fed by a virtual camera per approach that
applies the same K-of-M voting rule as the vision pipeline. Results go to
results/summary_by_class.csv next to the fixed / actuated (+preempt) rows from run_sim.py:

  controller "equiflow"        adaptive base controller
  controller "equiflow-marl"   trained multi-agent RL base controller (marl/train_marl.py)

  python run_equiflow.py --intersection cross_signal --scenario high
  python run_equiflow.py --all --seeds 1 2 3            # every signalised network x scenario x seed
  python run_equiflow.py --all --base marl --seeds 1 2 3
  python run_equiflow.py --all --no-corridor --label equiflow-nocorridor   # ablation
"""
import argparse
import csv
import hashlib
import itertools
import json
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from app.bus import EventBus  # noqa: E402
from app.config import load_config  # noqa: E402
from app.eventlog import EventLogger, episodes, read_log, write_episodes  # noqa: E402
from app.sumo_live import SumoLive, build_geometry  # noqa: E402

SIGNALISED = ["cross_signal", "t_signal", "five_way_signal", "six_way", "sector_grid", "diamond"]
SCENS = ["low", "medium", "high", "asymmetric"]
STRESS = ["emergency"]          # heavy traffic + ~3x the ambulances (fair-recovery stress test); not in the main matrix
ALL_SCENS = SCENS + STRESS
CLASSES = ["car", "motorcycle", "bus", "truck", "ambulance"]


def simulate(inter, scen, seed, step=1.0, base="adaptive", label=None, corridor=None, miss=None, fp=None,
             quiet=False, controller="equiflow", trip_dir=None, event_log=None, recovery=None, gap_out=None,
             end_s=None, preempt=None, sumo=None, vision=None):
    """Run one hour; return (rows for summary_by_class.csv, extra stats).
    preempt / sumo / vision: overrides for those config sections, e.g. sumo={"corridor_mode": "eta"},
    vision={"k": 3, "mean_min": 0.70}."""
    cfg = load_config()
    for k, v in (sumo or {}).items():
        setattr(cfg.sumo, k, v)
    for k, v in (vision or {}).items():
        setattr(cfg.vision, k, v)
    if corridor is not None:
        cfg.sumo.corridor = corridor
    if miss is not None:
        cfg.sumo.camera_miss_prob = miss
    if fp is not None:
        cfg.sumo.camera_fp_prob = fp
    if recovery is not None:
        cfg.preempt.recovery = recovery
    if gap_out is not None:
        cfg.preempt.gap_out = gap_out
    for k, v in (preempt or {}).items():          # any other PreemptCfg field, e.g. {"recovery_mode": "fixed"}
        setattr(cfg.preempt, k, v)
    if controller != "equiflow":
        label = label or controller
    label = label or ("equiflow" if base == "adaptive" else f"equiflow-{base}")
    bus = EventBus(history=50)
    ev_rows = []                       # in memory, for the recovery-interval metric

    def _keep(e):
        if e.get("type") in ("preempt_started", "preempt_switched", "preempt_green", "preempt_ended",
                             "preempt_timeout", "recovery_planned", "phase_changed", "mode_changed",
                             "ambulance_detected", "corridor_request", "manual_preempt", "green_ended_early"):
            ev_rows.append({"ts": e["ts"], "t": e.get("sim_time", 0.0), "type": e["type"],
                            "intersection_id": e.get("intersection_id") or "", "approach": e.get("approach") or "",
                            "data": e})
    bus.add_listener(_keep)
    elog = None
    if event_log:                      # CSV of every controller event (sim_time column = SUMO seconds)
        d = Path(event_log)
        elog = EventLogger(d, filename=f"events_{inter}_{label}_{scen}_s{seed}.csv")
        if elog.rows == 0 and elog.path.stat().st_size > 0:   # rerun: start the file again
            elog.close()
            elog.path.unlink()
            elog = EventLogger(d, filename=f"events_{inter}_{label}_{scen}_s{seed}.csv")
        bus.add_listener(elog)
    sim = SumoLive(cfg, bus)
    if not sim.available:
        sys.exit(sim.reason)
    net = ROOT / "networks" / f"{inter}_{'actuated' if controller == 'actuated' else 'fixed'}.net.xml"
    rou = ROOT / "routes" / f"{inter}_{scen}.rou.xml"
    if not (net.is_file() and rou.is_file()):
        sys.exit("Missing network/routes - run: python build_islamabad.py")
    tripinfo = Path(trip_dir or ROOT / "results") / f"tripinfo_{inter}_{label}_{scen}_s{seed}.xml"
    sim.headless, sim.tripinfo, sim.step_override = True, tripinfo, step
    if end_s:
        sim.end_s = float(end_s)
    t_wall = time.perf_counter()
    sim.run = {"network": inter, "scenario": scen, "controller": controller, "seed": seed, "speed": 1.0, "base": base}
    sim._worker(net, rou, build_geometry(net), dict(sim.run), sim._stop)   # runs to the end in this thread
    if elog is not None:
        elog.close()
        eps = episodes(read_log(elog.path))
        write_episodes(eps, elog.path.with_name(elog.path.name.replace("events_", "episodes_", 1)))
        if not quiet:
            done = [e for e in eps if e["completed"]]
            rec = [e for e in done if e["recovery_greens"]]
            print(f"  event log: {len(eps)} preemptions, {len(done)} completed, {len(rec)} followed by recovery")
    if sim.state == "error":
        sys.exit(f"simulation failed: {sim.error}")

    per = defaultdict(list)
    for t in ET.parse(tripinfo).getroot().findall("tripinfo"):
        per[t.get("vType")].append((float(t.get("duration")), float(t.get("waitingTime")), float(t.get("timeLoss"))))
    rows = []
    for vtype in CLASSES:
        d = per.get(vtype, [])
        n = len(d)
        avg = lambda i: round(sum(x[i] for x in d) / n, 2) if n else ""  # noqa: E731
        rows.append({"intersection": inter, "controller": label, "scenario": scen, "seed": seed,
                     "vehicle_type": vtype, "completed": n, "mean_travel_time_s": avg(0),
                     "mean_waiting_s": avg(1), "mean_time_loss_s": avg(2),
                     "mean_stopped_vehicles": round(sim.stopped_by_class[vtype] / max(sim.steps, 1), 2)})
    ctrls = getattr(sim, "_ctrls", {})
    lat = [x for c in ctrls.values() for x in c.stats.latencies_s]
    all_waits = [x[1] for v in per.values() for x in v]
    stats = {"priority_runs": sum(c.stats.preemptions for c in ctrls.values()),
             "latency_avg_s": round(sum(lat) / len(lat), 2) if lat else None,
             "false_confirms": sum(c.false_confirms for c in getattr(sim, "_cams", {}).values()),
             "corridor_requests": getattr(sim, "corridor_requests", 0),
             "max_wait_s": round(max(all_waits), 1) if all_waits else None}
    stats["wall_s"] = round(time.perf_counter() - t_wall, 2)
    stats["sim_steps"] = getattr(sim, "steps", None)
    eps = episodes(ev_rows) if ev_rows else []
    rec = [e["recovery_s"] for e in eps if e.get("recovery_s") is not None]
    stats["recovery_s_mean"] = round(sum(rec) / len(rec), 1) if rec else None
    stats["gap_outs"] = sum(1 for r in ev_rows if r["type"] == "green_ended_early")
    fair = fairness(tripinfo, getattr(sim, "amb_affected", set()))
    stats["fairness"] = fair
    stats["extensions"] = sum(c.stats.extensions for c in ctrls.values())
    stats["run"] = {"intersection": inter, "controller": label, "scenario": scen, "seed": seed}
    stats["config"] = {"preempt": cfg.preempt.model_dump(), "timing": cfg.timing.model_dump(),
                       "corridor": cfg.sumo.corridor, "camera_miss_prob": cfg.sumo.camera_miss_prob,
                       "camera_fp_prob": cfg.sumo.camera_fp_prob, "base": base, "step_s": step,
                       "corridor_mode": cfg.sumo.corridor_mode,
                       "vote": {"k": cfg.vision.k, "m": cfg.vision.m, "th_frame": cfg.vision.th_frame,
                                "mean_min": cfg.vision.mean_min},
                       "end_s": sim.end_s, "controller_params": cfg.sumo.controller_params}
    if not quiet:
        print(f"  priority runs {stats['priority_runs']}, corridor requests {stats['corridor_requests']}, "
              f"detection to green avg {stats['latency_avg_s']} s, false confirmations {stats['false_confirms']}")
        print(f"  fairness: p95 wait {fair['p95_wait_s']} s, max wait {fair['max_wait_s']} s, "
              f"Jain {fair['jain_approach_wait']}, recovery {stats['recovery_s_mean']} s, gap-outs {stats['gap_outs']}")
    return rows, stats


def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f, c = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 2)


def fairness(tripinfo, affected=frozenset()):
    """Waiting-time distribution of ordinary (non-ambulance) vehicles and how evenly the approaches
    are served. Approach = the edge a vehicle entered on. Jain's index over the per-approach mean
    waits: 1 = every approach waits the same, 1/n = one approach carries all the waiting.
    `affected`: ordinary vehicles that were stopped at a junction while an ambulance was on another of its
    approaches (sumo_live.amb_affected) - the vehicles ambulance priority can delay."""
    waits, per_appr, aff = [], defaultdict(list), []
    for t in ET.parse(tripinfo).getroot().findall("tripinfo"):
        if t.get("vType") == "ambulance":
            continue
        w = float(t.get("waitingTime"))
        waits.append(w)
        per_appr[t.get("departLane", "").rsplit("_", 1)[0]].append(w)
        if t.get("id") in affected:
            aff.append(w)
    means = [sum(v) / len(v) for v in per_appr.values() if v]
    jain = (sum(means) ** 2 / (len(means) * sum(m * m for m in means))) if means and any(means) else 1.0
    return {"vehicles": len(waits), "mean_wait_s": round(sum(waits) / len(waits), 2) if waits else None,
            "p50_wait_s": _pct(waits, 0.5), "p95_wait_s": _pct(waits, 0.95), "p99_wait_s": _pct(waits, 0.99),
            "max_wait_s": round(max(waits), 1) if waits else None,
            "share_wait_over_60s": round(sum(w > 60 for w in waits) / len(waits), 4) if waits else None,
            "worst_approach_mean_wait_s": round(max(means), 2) if means else None,
            "jain_approach_wait": round(jain, 4), "approaches": len(means),
            "affected_vehicles": len(aff),
            "affected_mean_wait_s": round(sum(aff) / len(aff), 2) if aff else None,
            "affected_p95_wait_s": _pct(aff, 0.95), "affected_max_wait_s": round(max(aff), 1) if aff else None}


FAIR_FIELDS = ["intersection", "controller", "scenario", "seed", "vehicles", "mean_wait_s", "p50_wait_s",
               "p95_wait_s", "p99_wait_s", "max_wait_s", "share_wait_over_60s", "worst_approach_mean_wait_s",
               "jain_approach_wait", "approaches", "affected_vehicles", "affected_mean_wait_s",
               "affected_p95_wait_s", "affected_max_wait_s", "ambulance_wait_s", "ambulance_travel_s",
               "priority_runs", "detection_to_green_s", "recovery_s_mean", "gap_outs", "extensions",
               "corridor_requests", "false_confirms", "wall_s"]


def save_fairness(rows, stats, f):
    amb = next((r for r in rows if r["vehicle_type"] == "ambulance"), {})
    row = {**stats["run"], **stats["fairness"], "ambulance_wait_s": amb.get("mean_waiting_s", ""),
           "ambulance_travel_s": amb.get("mean_travel_time_s", ""), "priority_runs": stats["priority_runs"],
           "detection_to_green_s": stats["latency_avg_s"], "recovery_s_mean": stats["recovery_s_mean"],
           "gap_outs": stats["gap_outs"], "extensions": stats.get("extensions", 0),
           "corridor_requests": stats["corridor_requests"],
           "false_confirms": stats["false_confirms"], "wall_s": stats["wall_s"]}
    _upsert(Path(f), [row], FAIR_FIELDS, key=("intersection", "controller", "scenario", "seed"))


def _versions():
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for mod in ("sumo", "traci", "numpy", "pydantic"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", None) or getattr(m, "VERSION", None) or "?"
        except Exception:  # noqa: BLE001
            out[mod] = None
    try:
        out["git_commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                           text=True, timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001
        out["git_commit"] = None
    w = ROOT.parent / "marl" / "weights" / "marl_policy.npz"
    out["marl_weights_sha1"] = hashlib.sha1(w.read_bytes()).hexdigest()[:12] if w.exists() else None
    return out


MANIFEST_FIELDS = ["intersection", "controller", "scenario", "seed", "finished", "config_json", "versions_json"]


def save_manifest(stats, f, versions):
    """FR-12: the full configuration and software versions behind every result row."""
    row = {**stats["run"], "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
           "config_json": json.dumps(stats["config"], sort_keys=True), "versions_json": json.dumps(versions)}
    _upsert(Path(f), [row], MANIFEST_FIELDS, key=("intersection", "controller", "scenario", "seed"))


def _upsert(f, rows, fields, key):
    try:
        import fcntl
        lock = open(str(f) + ".lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
    except (ImportError, OSError):
        lock = None
    try:
        old = list(csv.DictReader(f.open(newline=""))) if f.exists() else []
        k = lambda r: tuple(str(r[x]) for x in key)  # noqa: E731
        new = {k(r) for r in rows}
        allrows = [r for r in old if k(r) not in new] + rows
        with f.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(allrows)
    finally:
        if lock is not None:
            lock.close()


def save(rows, f=None):
    f = Path(f or ROOT / "results" / "summary_by_class.csv")
    try:                                  # several runs in parallel may write the same file (Linux/macOS)
        import fcntl
        lock = open(str(f) + ".lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
    except (ImportError, OSError):
        lock = None
    try:
        return _save(rows, f)
    finally:
        if lock is not None:
            lock.close()


def _save(rows, f):
    old = list(csv.DictReader(f.open(newline=""))) if f.exists() else []
    key = lambda r: (r["intersection"], r["controller"], r["scenario"], str(r["seed"]), r["vehicle_type"])  # noqa: E731
    new = {key(r) for r in rows}
    allrows = [r for r in old if key(r) not in new] + rows
    with f.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(allrows)
    return f


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--intersection", choices=SIGNALISED, default="cross_signal")
    ap.add_argument("--scenario", choices=ALL_SCENS, default="medium")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--base", choices=["adaptive", "marl", "fixed_time"], default="adaptive")
    ap.add_argument("--controller", choices=["equiflow", "fixed", "actuated"], default="equiflow",
                    help="fixed / actuated run SUMO's own plans through the same harness (baselines)")
    ap.add_argument("--networks", nargs="+", choices=SIGNALISED, help="with --all: only these networks")
    ap.add_argument("--out", help="write to this CSV instead of results/summary_by_class.csv")
    ap.add_argument("--trip-dir", help="folder for the tripinfo files (default results/)")
    ap.add_argument("--label", help="controller name in the results (default equiflow / equiflow-<base>)")
    ap.add_argument("--no-corridor", action="store_true", help="switch the green corridor off (ablation)")
    ap.add_argument("--step", type=float, default=1.0, help="SUMO step length (run_sim.py uses 1 s)")
    ap.add_argument("--event-log", help="folder for per-run event logs + preemption episode tables")
    ap.add_argument("--no-recovery", action="store_true", help="switch fair recovery off (ablation)")
    ap.add_argument("--no-gap-out", action="store_true", help="never end an empty green early (ablation)")
    ap.add_argument("--fairness-out", help="per-run fairness CSV (default results/fairness_by_run.csv)")
    ap.add_argument("--manifest", help="per-run config + versions CSV (default results/run_manifest.csv)")
    ap.add_argument("--end", type=float, help="stop the simulation at this time (default 3600 s)")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    versions = _versions()
    jobs = list(itertools.product(a.networks or SIGNALISED, SCENS, a.seeds)) if a.all else \
        [(a.intersection, a.scenario, s) for s in a.seeds]
    for inter, scen, seed in jobs:
        print(f"Running {inter} / {a.label or (a.base if a.controller == 'equiflow' else a.controller)} / {scen} / seed {seed} ...")
        rows, st = simulate(inter, scen, seed, a.step, a.base, a.label, corridor=False if a.no_corridor else None,
                            controller=a.controller, trip_dir=a.trip_dir, event_log=a.event_log,
                            recovery=False if a.no_recovery else None, gap_out=False if a.no_gap_out else None,
                            end_s=a.end)
        f = save(rows, a.out)
        res_dir = Path(a.out).parent if a.out else ROOT / "results"
        save_fairness(rows, st, a.fairness_out or res_dir / "fairness_by_run.csv")
        save_manifest(st, a.manifest or res_dir / "run_manifest.csv", versions)
        for r in rows:
            print(f"  {r['vehicle_type']:<11} n={r['completed']:<5} travel={r['mean_travel_time_s']:<7} "
                  f"wait={r['mean_waiting_s']:<6} loss={r['mean_time_loss_s']}")
    print("Saved:", f)
