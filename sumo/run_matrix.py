"""run_matrix.py - the full evaluation: every controller x network x demand level x seed, in parallel.

Seeds 6-10 by default: the MARL controller was trained on seeds 1-5 (marl/train_marl.py), so these
runs are held out from its training (mid-report Section 7.5). All controllers use the same seeds,
networks and demand, through the same harness (run_equiflow.simulate), so every row is comparable.

Controllers (equiflow = the recommended configuration since Iteration 2b: recovery and corridor off)
  fixed                     SUMO's fixed-time plan
  actuated                  SUMO's actuated plan (gap-based, the strong adaptive baseline)
  fixed+preempt             fixed-time + ambulance priority, no recovery, no gap-out, no extension (emergency-only)
  equiflow                  adaptive (wait weight 0.3) + priority + gap-out + green extension (wait cap 30 s)
  equiflow-marl             same, with the MARL base controller
  equiflow-nogapout         ablation: gap-out off
  equiflow-noextend         ablation: green extension off
  equiflow-tail-v1          ablation: the first tail settings (adaptive wait weight 0.1, extension wait cap 40 s)
  equiflow-recovery         variant: + fair recovery, queue-sized greens (the Iteration 2 default)
  equiflow-recovery-order   variant: + fair recovery that only re-orders the delayed approaches
  equiflow-recovery-v1      variant: + the first recovery rule (fixed green + extra for every delayed approach)
  equiflow-corridor         variant: + just-in-time green corridor (multi-junction networks only)
  equiflow-corridor-v1      variant: + the Iteration 2 corridor rule, 25 s ETA (multi-junction networks only)

Stress test for fair recovery (heavy traffic, ~40 ambulances per hour):
    python run_matrix.py --scenarios emergency --out results/stress --controllers equiflow equiflow-recovery \
        equiflow-recovery-order equiflow-recovery-v1 fixed+preempt actuated

    python run_matrix.py                          # everything -> results/heldout/
    python run_matrix.py --seeds 6 7 --controllers equiflow actuated --jobs 4
    python run_matrix.py --resume                 # skip runs already in fairness_by_run.csv

Outputs (results/heldout/): summary_by_class.csv, fairness_by_run.csv, run_manifest.csv.
Then: python aggregate.py
"""
from __future__ import annotations

import argparse
import csv
import itertools
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import run_equiflow as rq  # noqa: E402

CONTROLLERS = {
    "fixed": dict(controller="fixed"),
    "actuated": dict(controller="actuated"),
    "fixed+preempt": dict(controller="equiflow", base="fixed_time", recovery=False, gap_out=False,
                          preempt={"extend": False}),
    "equiflow": dict(controller="equiflow", base="adaptive"),
    "equiflow-marl": dict(controller="equiflow", base="marl"),
    "equiflow-nogapout": dict(controller="equiflow", base="adaptive", gap_out=False),
    "equiflow-noextend": dict(controller="equiflow", base="adaptive", preempt={"extend": False}),
    "equiflow-tail-v1": dict(controller="equiflow", base="adaptive", preempt={"extend_wait_cap_s": 40},
                             sumo={"controller_params": {"min_green_s": 6, "max_green_s": 30, "per_vehicle_s": 1.0,
                                                         "wait_weight": 0.1}}),
    "equiflow-recovery": dict(controller="equiflow", base="adaptive", recovery=True,
                              preempt={"recovery_mode": "queue"}),
    "equiflow-recovery-order": dict(controller="equiflow", base="adaptive", recovery=True,
                                    preempt={"recovery_mode": "order"}),
    "equiflow-recovery-v1": dict(controller="equiflow", base="adaptive", recovery=True,
                                 preempt={"recovery_mode": "fixed"}),
    "equiflow-corridor": dict(controller="equiflow", base="adaptive", corridor=True,
                              sumo={"corridor_mode": "just_in_time"}),
    "equiflow-corridor-v1": dict(controller="equiflow", base="adaptive", corridor=True, sumo={"corridor_mode": "eta"}),
}
MULTI_JUNCTION = ["sector_grid", "diamond"]


def one(job):
    label, inter, scen, seed, trip_dir = job
    kw = dict(CONTROLLERS[label])
    rows, st = rq.simulate(inter, scen, seed, 1.0, kw.pop("base", "adaptive"), label, quiet=True,
                           trip_dir=trip_dir, **kw)
    return label, inter, scen, seed, rows, st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--controllers", nargs="+", choices=list(CONTROLLERS), default=list(CONTROLLERS))
    ap.add_argument("--networks", nargs="+", choices=rq.SIGNALISED, default=rq.SIGNALISED)
    ap.add_argument("--scenarios", nargs="+", choices=rq.ALL_SCENS, default=rq.SCENS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[6, 7, 8, 9, 10])
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--out", default=str(ROOT / "results" / "heldout"))
    ap.add_argument("--keep-tripinfo", action="store_true", help="keep the tripinfo XML files (large)")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trip_dir = str(out / "tripinfo") if a.keep_tripinfo else tempfile.mkdtemp(prefix="equiflow_trips_")
    Path(trip_dir).mkdir(parents=True, exist_ok=True)
    done = set()
    fair_f = out / "fairness_by_run.csv"
    if a.resume and fair_f.exists():
        done = {(r["controller"], r["intersection"], r["scenario"], int(r["seed"])) for r in csv.DictReader(fair_f.open())}
    jobs = []
    for label, inter, scen, seed in itertools.product(a.controllers, a.networks, a.scenarios, a.seeds):
        if label in ("equiflow-corridor", "equiflow-corridor-v1") and inter not in MULTI_JUNCTION:
            continue
        if (label, inter, scen, seed) in done:
            continue
        jobs.append((label, inter, scen, seed, trip_dir))
    print(f"{len(jobs)} runs, {a.jobs} in parallel -> {out}")
    versions = rq._versions()
    t0 = time.time()
    n = 0
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(one, j) for j in jobs]
        for fut in as_completed(futs):
            try:
                label, inter, scen, seed, rows, st = fut.result()
            except BaseException as e:  # noqa: BLE001 - one failed run must not stop the matrix
                print("  run failed:", e)
                continue
            rq.save(rows, out / "summary_by_class.csv")          # saved by the parent only: no write races
            rq.save_fairness(rows, st, fair_f)
            rq.save_manifest(st, out / "run_manifest.csv", versions)
            n += 1
            el = time.time() - t0
            print(f"  [{n}/{len(jobs)}] {label:20s} {inter:16s} {scen:10s} s{seed}  "
                  f"p95 {st['fairness']['p95_wait_s']:>5} s  ({el / n * (len(jobs) - n) / 60:.0f} min left)", flush=True)
            if not a.keep_tripinfo:
                for f in Path(trip_dir).glob(f"tripinfo_{inter}_{label}_{scen}_s{seed}.xml"):
                    f.unlink(missing_ok=True)
    print(f"done: {n} runs in {(time.time() - t0) / 60:.1f} min. Next: python aggregate.py")


if __name__ == "__main__":
    main()
