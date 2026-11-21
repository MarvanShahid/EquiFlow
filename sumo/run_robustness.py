"""
run_robustness.py - how much do camera errors hurt? Sweeps the virtual cameras' per-frame miss
rate (the detector loses the vehicle in that frame) and false-alarm rate (a non-ambulance is scored
like an ambulance in that frame), with the EquiFlow controller, and writes results/robustness.csv.

  python run_robustness.py                     # default grid, 2 parallel runs
  python run_robustness.py --miss 0 0.5 --fp 0 0.05 --networks cross_signal
"""
import argparse
import csv
import itertools
from multiprocessing import Pool
from pathlib import Path

from run_equiflow import simulate

ROOT = Path(__file__).resolve().parent


def one(job):
    net, scen, miss, fp, seed = job
    rows, st = simulate(net, scen, seed, miss=miss, fp=fp, label=f"robust-m{miss}-f{fp}", quiet=True,
                        trip_dir=ROOT / "results" / "robustness_tripinfo")
    by = {r["vehicle_type"]: r for r in rows}
    return {"network": net, "scenario": scen, "seed": seed, "miss_prob": miss, "fp_prob": fp,
            "ambulance_wait_s": by["ambulance"]["mean_waiting_s"], "car_wait_s": by["car"]["mean_waiting_s"],
            "priority_runs": st["priority_runs"], "false_confirmations": st["false_confirms"],
            "detection_to_green_s": st["latency_avg_s"], "corridor_requests": st["corridor_requests"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--networks", nargs="+", default=["cross_signal", "sector_grid"])
    ap.add_argument("--scenario", default="high")
    ap.add_argument("--miss", type=float, nargs="+", default=[0.0, 0.3, 0.6, 0.85])
    ap.add_argument("--fp", type=float, nargs="+", default=[0.0, 0.05, 0.2, 0.4])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    (ROOT / "results" / "robustness_tripinfo").mkdir(parents=True, exist_ok=True)
    jobs = [(n, a.scenario, m, f, a.seed) for n, m, f in itertools.product(a.networks, a.miss, a.fp)]
    with Pool(a.jobs) as p:
        out = p.map(one, jobs)
    f = ROOT / "results" / "robustness.csv"
    key = lambda r: (r["network"], r["scenario"], str(r["seed"]), str(float(r["miss_prob"])), str(float(r["fp_prob"])))  # noqa: E731
    new = {key(r) for r in out}
    old = [r for r in csv.DictReader(f.open(newline=""))] if f.exists() else []
    with f.open("w", newline="") as fh:        # earlier rows for other settings are kept
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows([r for r in old if key(r) not in new] + out)
    for r in out:
        print(r)
    print("Saved:", f)
