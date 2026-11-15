"""Scripted ambulance scenario: the Iteration 2 exit test.

Runs the real backend runtime (simulated cameras, adaptive controller, preemption, fair recovery)
on one junction and plays a fixed script through the same ingest path an external vision service
uses (POST /api/ambulances/events):

  t =  4 s  ambulance appears on West
  t = 30 s  ambulances on East and North at once (served first come, first served)

An ambulance stays in view until its approach has been green long enough for it to drive through
(PASS_S), like a real one waiting at a red light, then leaves.

Every event goes to a CSV log; the script then groups it into preemption episodes and checks that
each one was triggered by a detection, got a green, ended, and was followed by recovery greens.

    cd backend
    python scripts/scripted_scenario.py                  # -> logs/scenario_events.csv, logs/scenario_episodes.csv
    python scripts/scripted_scenario.py --fast           # shorter timings (about 45 s instead of 70 s)

Exit code 0 = every episode completed with recovery.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.bus import EventBus  # noqa: E402
from app.config import AppConfig, IntersectionCfg, SimCfg  # noqa: E402
from app.eventlog import EventLogger, episodes, read_log, write_episodes  # noqa: E402
from app.runtime import Runtime  # noqa: E402

# (start_s, approach, track_id)
SCRIPT = [(4, "West", 101), (30, "East", 102), (30.5, "North", 103)]
PASS_S = 4.0          # seconds of green an ambulance needs to clear the junction


def run(out_dir: Path, fast: bool = False, quiet: bool = False) -> tuple[list[dict], Path]:
    cfg = AppConfig(mode="sim", controller="adaptive", sim=SimCfg(auto_ambulance=False),
                    intersections=[IntersectionCfg(id="J1", name="Scripted junction")])
    if fast:
        cfg.timing.green_s, cfg.timing.yellow_s, cfg.timing.all_red_s = 6, 1, 1
        cfg.preempt.min_green_s, cfg.preempt.clear_hold_s = 1, 2
        cfg.preempt.recovery_max_s = 6
        cfg.controller_params = {"min_green_s": 3, "max_green_s": 8}
    scale = 0.6 if fast else 1.0
    pass_s = PASS_S * (0.75 if fast else 1.0)
    script = [(st * scale, a, tid) for st, a, tid in SCRIPT]
    end_s = script[-1][0] + (45 if fast else 80)
    state = {tid: {"green_for": 0.0, "gone_at": None} for _, _, tid in script}

    bus = EventBus(history=5000)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "scenario_events.csv"
    if log_path.exists():
        log_path.unlink()
    log = EventLogger(out_dir, filename=log_path.name)
    bus.add_listener(log)
    rt = Runtime(cfg, bus)
    rt.start()
    j = rt.get("J1")
    t0 = time.monotonic()
    try:
        last_print, prev = -1, 0.0
        while (el := time.monotonic() - t0) < end_s:
            lamps = j.snapshot()["lamps"]
            for start, appr, tid in script:
                st = state[tid]
                if el < start or st["gone_at"] is not None:
                    continue
                st["green_for"] = st["green_for"] + (el - prev) if lamps[appr] == "green" else 0.0
                if st["green_for"] >= pass_s:      # drove through: stops being seen
                    st["gone_at"] = el
                else:                              # heartbeat about 5 times a second while visible
                    j.ingest(appr, True, tid, 0.9, 0.5, 0.5)
            prev = el
            if not quiet and int(el) != last_print and int(el) % 5 == 0:
                last_print = int(el)
                s = j.snapshot()
                lit = [f"{a}:{l}" for a, l in s["lamps"].items() if l != "red"] or ["all red"]
                print(f"  t={el:5.1f}s  mode={s['mode']:<9} {' '.join(lit)}")
            time.sleep(0.2)
    finally:
        rt.stop()
        log.close()
    eps = episodes(read_log(log_path))
    ep_path = out_dir / "scenario_episodes.csv"
    write_episodes(eps, ep_path)
    missed = [a for _, a, tid in script if state[tid]["gone_at"] is None]
    if missed:                                     # an ambulance still waiting when the script ended
        eps.append({"trigger": "camera", "completed": False, "ended_reason": None, "recovery_greens": 0,
                    "green_ts": None, "ended_ts": None, "served": None, "approach": " ".join(missed),
                    "unserved": True})
    return eps, log_path


def check(eps: list[dict]) -> list[str]:
    problems = [f"ambulance on {e['approach']} never got through" for e in eps if e.get("unserved")]
    eps = [e for e in eps if not e.get("unserved")]
    served = {a for e in eps for a in (e["served"] or "").split("; ") if a}
    for a in ("West", "East", "North"):
        if a not in served:
            problems.append(f"no preemption served the ambulance on {a}")
    if len(eps) < 2:
        problems.append(f"expected at least 2 preemption episodes, got {len(eps)}")
    for i, e in enumerate(eps, 1):
        if e["trigger"] != "camera":
            problems.append(f"episode {i}: trigger {e['trigger']}, expected a camera detection")
        if not e["completed"]:
            problems.append(f"episode {i}: did not complete (green {e['green_ts']}, end {e['ended_ts']})")
        if e["ended_reason"] != "cleared":
            problems.append(f"episode {i}: ended by {e['ended_reason']}")
        if not e["recovery_greens"]:
            problems.append(f"episode {i}: no recovery green after the ambulance passed")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(BACKEND / "logs"))
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    print("Running the scripted ambulance scenario ...")
    eps, log_path = run(Path(a.out), fast=a.fast)
    print(f"\nEvent log: {log_path}\nEpisodes:  {Path(a.out) / 'scenario_episodes.csv'}\n")
    for i, e in enumerate(e for e in eps if not e.get("unserved")):
        i += 1
        print(f"  #{i} served {e['served'] or e['approach']:<11} trigger={e['trigger']:<7} detection->green={e['detection_to_green_s']} s  "
              f"held {e['preempt_duration_s']} s  ended={e['ended_reason']}  "
              f"recovery: {e['recovery_plan'] or '-'} ({e['recovery_greens']} greens)")
    problems = check(eps)
    print("\nPASS: every preemption was triggered by a detection, completed and followed by recovery"
          if not problems else "\nFAIL:\n  " + "\n  ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
