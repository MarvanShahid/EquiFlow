"""
run_robustness.py - how much do camera errors hurt? Sweeps the virtual cameras' per-frame miss
rate (the detector loses the vehicle in that frame) and false-alarm rate (a non-ambulance is scored
like an ambulance in that frame), with the EquiFlow controller, and writes results/robustness.csv.

  python run_robustness.py                     # default grid, 2 parallel runs, the config's vote (5 of 8)
  python run_robustness.py --miss 0 0.5 --fp 0 0.05 --networks cross_signal
  python run_robustness.py --k 3 --mean-min 0.70   # the live camera vote re-tuned for cls_v5_img128

Rows are keyed by network, scenario, seed, miss, false-alarm rate and vote, so sweeps with different votes
sit side by side in the same file.
"""
import argparse
import csv
import itertools
from multiprocessing import Pool
from pathlib import Path

from run_equiflow import simulate  # also puts backend/ on sys.path
from app.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent


def one(job):
    net, scen, miss, fp, seed, vote = job
    rows, st = simulate(net, scen, seed, miss=miss, fp=fp, label=f"robust-m{miss}-f{fp}-k{vote['k']}", quiet=True,
                        trip_dir=ROOT / "results" / "robustness_tripinfo", vision=vote)
    by = {r["vehicle_type"]: r for r in rows}
    return {"network": net, "scenario": scen, "seed": seed, "miss_prob": miss, "fp_prob": fp,
            "vote": f"{vote['k']}/{vote['m']} mean>={vote['mean_min']}",
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
    ap.add_argument("--k", type=int, help="votes needed (default: the config's vision.k)")
    ap.add_argument("--m", type=int, help="vote window in frames (default: vision.m)")
    ap.add_argument("--mean-min", type=float, help="minimum mean score (default: vision.mean_min)")
    ap.add_argument("--th-frame", type=float, help="per-frame score threshold (default: vision.th_frame)")
    a = ap.parse_args()
    v = load_config().vision
    vote = {"k": a.k or v.k, "m": a.m or v.m, "mean_min": a.mean_min if a.mean_min is not None else v.mean_min,
            "th_frame": a.th_frame if a.th_frame is not None else v.th_frame}
    (ROOT / "results" / "robustness_tripinfo").mkdir(parents=True, exist_ok=True)
    jobs = [(n, a.scenario, m, f, a.seed, vote) for n, m, f in itertools.product(a.networks, a.miss, a.fp)]
    with Pool(a.jobs) as p:
        out = p.map(one, jobs)
    f = ROOT / "results" / "robustness.csv"
    default_vote = f"{v.k}/{v.m} mean>={v.mean_min}"      # rows written before the vote column existed

    def key(r):
        return (r["network"], r["scenario"], str(r["seed"]), str(float(r["miss_prob"])), str(float(r["fp_prob"])),
                r.get("vote") or default_vote)
    new = {key(r) for r in out}
    old = [r for r in csv.DictReader(f.open(newline=""))] if f.exists() else []
    for r in old:
        r.setdefault("vote", default_vote)
        r["vote"] = r["vote"] or default_vote
    with f.open("w", newline="") as fh:        # earlier rows for other settings are kept
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows([r for r in old if key(r) not in new] + out)
    for r in out:
        print(r)
    print("Saved:", f)
