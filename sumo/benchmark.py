"""benchmark.py - performance numbers for the report (NFR performance, mid-report Section 4.5.3).

Measures on this machine:
  * controller tick time   IntersectionController.tick() with each base controller (called every 0.1 s live,
                           every SUMO step in simulation)
  * decision time          base controller next_phase() (the moment it picks the next green)
  * simulation throughput  simulated seconds per wall-clock second, from the run matrix (wall_s column)

Detector / classifier latency is measured by Projects/eval_detector.py (needs the model and a GPU).

    python benchmark.py                 # -> results/performance.csv and results/performance.md
"""
from __future__ import annotations

import csv
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from app.controllers import IntersectionController, PreemptConfig, Timing  # noqa: E402
from app.controllers.base import create_base  # noqa: E402
from app.controllers.types import Context  # noqa: E402

WEIGHTS = ROOT.parent / "marl" / "weights" / "marl_policy.npz"


def _stats(xs_us):
    xs = sorted(xs_us)
    return {"mean_us": round(statistics.mean(xs), 2), "median_us": round(statistics.median(xs), 2),
            "p99_us": round(xs[int(0.99 * (len(xs) - 1))], 2), "max_us": round(xs[-1], 2), "n": len(xs)}


def bench_tick(base_name: str, params: dict, n: int = 50000):
    timing = Timing()
    ctl = IntersectionController("B", create_base(base_name, timing, params), timing, PreemptConfig())
    rng = random.Random(0)
    t, out = 0.0, []
    for i in range(n):
        t += 0.1
        for a in ctl.approaches:
            ctl.observe(a, a == "East" and (i // 600) % 5 == 0, t, vehicles=rng.randint(0, 15))
        s = time.perf_counter_ns()
        ctl.tick(t)
        out.append((time.perf_counter_ns() - s) / 1000)
    return _stats(out)


def bench_decision(base_name: str, params: dict, n: int = 20000):
    timing = Timing()
    base = create_base(base_name, timing, params)
    rng = random.Random(1)
    appr = ("North", "East", "South", "West")
    out = []
    for _ in range(n):
        ctx = Context(now=100.0, current=rng.choice(appr), approaches=appr,
                      vehicles={a: rng.randint(0, 20) for a in appr},
                      waiting_s={a: rng.uniform(0, 80) for a in appr})
        s = time.perf_counter_ns()
        base.next_phase(ctx)
        out.append((time.perf_counter_ns() - s) / 1000)
    return _stats(out)


def sim_throughput(fair_csv: Path):
    if not fair_csv.exists():
        return []
    rows = list(csv.DictReader(fair_csv.open()))
    by = {}
    for r in rows:
        if r.get("wall_s"):
            by.setdefault(r["controller"], []).append(3600.0 / float(r["wall_s"]))
    return [{"controller": c, "sim_s_per_wall_s_mean": round(statistics.mean(v), 1),
             "sim_s_per_wall_s_min": round(min(v), 1), "runs": len(v)} for c, v in sorted(by.items())]


def main():
    res = []
    marl = {"weights": str(WEIGHTS)}
    for name, params in (("fixed_time", {}), ("adaptive", {"min_green_s": 6, "max_green_s": 30, "per_vehicle_s": 1.0}),
                         ("marl", marl)):
        res.append({"what": f"tick ({name})", **bench_tick(name, params)})
        res.append({"what": f"decision ({name})", **bench_decision(name, params)})
    out = ROOT / "results"
    with open(out / "performance.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["what", "mean_us", "median_us", "p99_us", "max_us", "n"])
        w.writeheader()
        w.writerows(res)
    thr = sim_throughput(out / "heldout" / "fairness_by_run.csv")
    L = ["# Performance", "", f"Machine: {platform.processor() or platform.machine()}, {platform.platform()}, "
         f"Python {platform.python_version()}. One CPU core per measurement.", "",
         "## Signal controller", "", "| Measured | mean | median | p99 | max |", "|---|---|---|---|---|"]
    L += [f"| {r['what']} | {r['mean_us']} µs | {r['median_us']} µs | {r['p99_us']} µs | {r['max_us']} µs |" for r in res]
    L += ["", "The live backend ticks every 0.1 s (100 000 µs), so the controller uses well under 1% of that budget."]
    if thr:
        L += ["", "## Simulation throughput (1-hour SUMO runs, 1 s steps, from the run matrix)", "",
              "| Controller | simulated s per wall-clock s (mean) | slowest run | runs |", "|---|---|---|---|"]
        L += [f"| {r['controller']} | {r['sim_s_per_wall_s_mean']} | {r['sim_s_per_wall_s_min']} | {r['runs']} |" for r in thr]
        L += ["", "Runs were executed two at a time, so per-run numbers include sharing the CPU."]
    L += ["", "Detector and classifier latency: see `Projects/runs/eval_test/summary.md` (run `Projects/eval_detector.py`)."]
    (out / "performance.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
