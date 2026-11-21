"""aggregate.py - statistics over the run matrix (results/heldout/ from run_matrix.py).

Writes to the same folder:
  summary_stats.csv     per controller: mean, standard deviation and 95% CI of every metric over all runs
  by_scenario.csv       the same per demand level
  paired.csv            EquiFlow vs every other controller on IDENTICAL runs (network, demand, seed):
                        mean difference, 95% CI of the difference (paired t), share of runs EquiFlow wins
  marl_heldout.csv      MARL vs adaptive on network/demand combinations seen vs not seen in MARL training
  RESULTS_TABLES.md     all of it as markdown tables for the report

    python aggregate.py [--dir results/heldout] [--reference equiflow]
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORDER = ["fixed", "actuated", "fixed+preempt", "equiflow", "equiflow-marl", "equiflow-norecovery",
         "equiflow-nogapout", "equiflow-nocorridor", "equiflow-recovery-v1"]
NAMES = {"fixed": "Fixed-time", "actuated": "Actuated", "fixed+preempt": "Fixed-time + priority",
         "equiflow": "EquiFlow", "equiflow-marl": "EquiFlow (MARL)", "equiflow-norecovery": "EquiFlow, no recovery",
         "equiflow-nogapout": "EquiFlow, no gap-out", "equiflow-nocorridor": "EquiFlow, no corridor",
         "equiflow-recovery-v1": "EquiFlow, old recovery rule"}
# metric -> (label, lower is better)
METRICS = {
    "car_wait_s": ("Car mean wait (s)", True),
    "mean_wait_s": ("All ordinary vehicles, mean wait (s)", True),
    "p95_wait_s": ("95th-percentile wait (s)", True),
    "max_wait_s": ("Longest single wait (s)", True),
    "share_wait_over_60s": ("Vehicles waiting > 60 s (share)", True),
    "worst_approach_mean_wait_s": ("Worst approach, mean wait (s)", True),
    "jain_approach_wait": ("Jain fairness index across approaches (1 = equal)", False),
    "ambulance_wait_s": ("Ambulance mean wait (s)", True),
    "ambulance_travel_s": ("Ambulance mean travel time (s)", True),
    "detection_to_green_s": ("Detection to green (s)", True),
    "recovery_s_mean": ("Recovery interval after priority (s)", True),
}
# MARL training set (marl/train_marl.py TRAIN) and seeds 1-5
MARL_TRAIN = {("cross_signal", "high"), ("sector_grid", "high"), ("five_way_signal", "medium"), ("t_signal", "high"),
              ("diamond", "high"), ("six_way", "medium"), ("cross_signal", "asymmetric"), ("sector_grid", "medium")}

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t95(df: int) -> float:
    if df <= 0:
        return float("nan")
    keys = sorted(T95)
    for k in keys:
        if df <= k:
            return T95[k]
    return 1.96


def num(x):
    try:
        return float(x) if x not in ("", None, "None") else None
    except ValueError:
        return None


def load(d: Path):
    runs: dict[tuple, dict] = {}
    for r in csv.DictReader((d / "fairness_by_run.csv").open()):
        k = (r["controller"], r["intersection"], r["scenario"], r["seed"])
        runs[k] = {m: num(r.get(m)) for m in METRICS if m != "car_wait_s"}
    for r in csv.DictReader((d / "summary_by_class.csv").open()):
        k = (r["controller"], r["intersection"], r["scenario"], str(r["seed"]))
        if r["vehicle_type"] == "car" and k in runs:
            runs[k]["car_wait_s"] = num(r["mean_waiting_s"])
    return runs


def describe(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, None, 0
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    ci = t95(len(xs) - 1) * sd / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")
    return m, sd, ci, len(xs)


def fmt(m, ci=None, digits=2):
    if m is None:
        return "–"
    if ci is None or ci != ci:
        return f"{m:.{digits}f}"
    return f"{m:.{digits}f} ± {ci:.{digits}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "results" / "heldout"))
    ap.add_argument("--reference", default="equiflow")
    a = ap.parse_args()
    d = Path(a.dir)
    runs = load(d)
    ctrls = [c for c in ORDER if any(k[0] == c for k in runs)] + sorted({k[0] for k in runs} - set(ORDER))

    # ---------------------------------------------------------------- per controller
    stats_rows = []
    for c in ctrls:
        for m in METRICS:
            mean, sd, ci, n = describe([v[m] for k, v in runs.items() if k[0] == c])
            stats_rows.append({"controller": c, "metric": m, "mean": mean, "sd": sd, "ci95": ci, "n": n})
    _write(d / "summary_stats.csv", stats_rows)
    S = {(r["controller"], r["metric"]): r for r in stats_rows}

    scen_rows = []
    for c in ctrls:
        for scen in ("low", "medium", "high", "asymmetric"):
            for m in METRICS:
                mean, sd, ci, n = describe([v[m] for k, v in runs.items() if k[0] == c and k[2] == scen])
                scen_rows.append({"controller": c, "scenario": scen, "metric": m, "mean": mean, "sd": sd,
                                  "ci95": ci, "n": n})
    _write(d / "by_scenario.csv", scen_rows)

    # ---------------------------------------------------------------- paired vs reference
    ref = a.reference
    paired = []
    for c in ctrls:
        if c == ref:
            continue
        for m, (_, lower) in METRICS.items():
            diffs, wins = [], 0
            for k, v in runs.items():
                if k[0] != c:
                    continue
                rk = (ref,) + k[1:]
                if rk not in runs or v[m] is None or runs[rk][m] is None:
                    continue
                diff = runs[rk][m] - v[m]
                diffs.append(diff)
                better = diff < -1e-9 if lower else diff > 1e-9
                wins += better
            mean, sd, ci, n = describe(diffs)
            if n:
                paired.append({"reference": ref, "versus": c, "metric": m, "mean_diff": mean, "ci95": ci, "n": n,
                               "ref_wins_share": wins / n,
                               "significant": bool(ci == ci and abs(mean) > ci)})
    _write(d / "paired.csv", paired)

    # ---------------------------------------------------------------- MARL held out
    marl_rows = []
    for seen in (True, False):
        for m in ("car_wait_s", "p95_wait_s", "jain_approach_wait", "ambulance_wait_s"):
            diffs = []
            for k, v in runs.items():
                if k[0] != "equiflow-marl" or ((k[1], k[2]) in MARL_TRAIN) != seen:
                    continue
                rk = ("equiflow",) + k[1:]
                if rk in runs and v[m] is not None and runs[rk][m] is not None:
                    diffs.append(v[m] - runs[rk][m])
            mean, sd, ci, n = describe(diffs)
            marl_rows.append({"network_demand_in_training": seen, "metric": m, "marl_minus_adaptive": mean,
                              "ci95": ci, "n": n})
    _write(d / "marl_heldout.csv", marl_rows)

    # ---------------------------------------------------------------- markdown
    n_runs = {c: sum(1 for k in runs if k[0] == c) for c in ctrls}
    seeds = sorted({int(k[3]) for k in runs})
    L = ["# Results: held-out evaluation", "",
         f"{len(runs)} one-hour SUMO runs. Seeds {', '.join(map(str, seeds))} (the MARL controller was trained on "
         "seeds 1-5, so none of these were seen in training); 6 signalised networks x 4 demand levels per controller "
         "(the corridor ablation only on the two multi-junction networks). Values are mean ± 95% confidence interval "
         "over runs.", "", "## Main comparison", ""]
    main_c = [c for c in ("fixed", "actuated", "fixed+preempt", "equiflow", "equiflow-marl") if c in ctrls]
    L += ["| Metric | " + " | ".join(NAMES.get(c, c) for c in main_c) + " |",
          "|---|" + "---|" * len(main_c)]
    for m, (label, _) in METRICS.items():
        digits = 3 if m in ("jain_approach_wait", "share_wait_over_60s") else 2
        L.append(f"| {label} | " + " | ".join(fmt(S[(c, m)]["mean"], S[(c, m)]["ci95"], digits) for c in main_c) + " |")
    L.append("| Runs | " + " | ".join(str(n_runs[c]) for c in main_c) + " |")

    abl = [c for c in ("equiflow", "equiflow-recovery-v1", "equiflow-norecovery", "equiflow-nogapout",
                       "equiflow-nocorridor") if c in ctrls]
    if len(abl) > 1:
        L += ["", "## Ablations (what each part of EquiFlow contributes)", "",
              "| Metric | " + " | ".join(NAMES.get(c, c) for c in abl) + " |", "|---|" + "---|" * len(abl)]
        for m, (label, _) in METRICS.items():
            digits = 3 if m in ("jain_approach_wait", "share_wait_over_60s") else 2
            L.append(f"| {label} | " + " | ".join(fmt(S[(c, m)]["mean"], S[(c, m)]["ci95"], digits) for c in abl) + " |")
        L.append("| Runs | " + " | ".join(str(n_runs[c]) for c in abl) + " |")
        L.append("")
        L.append("The corridor ablation runs only on sector_grid and diamond; compare it with EquiFlow on those "
                 "networks in paired.csv (the paired rows use matched runs only).")

    L += ["", f"## Paired comparison: {NAMES.get(ref, ref)} minus each controller, on identical runs", "",
          "Negative = EquiFlow lower (for waits, better). * = the 95% CI excludes 0. Win share = runs where "
          "EquiFlow is better.", "",
          "| Versus | Metric | Mean difference ± 95% CI | EquiFlow wins | Runs |", "|---|---|---|---|---|"]
    keym = ("car_wait_s", "p95_wait_s", "max_wait_s", "jain_approach_wait", "ambulance_wait_s", "recovery_s_mean")
    for r in paired:
        if r["metric"] not in keym:
            continue
        digits = 3 if r["metric"] == "jain_approach_wait" else 2
        L.append(f"| {NAMES.get(r['versus'], r['versus'])} | {METRICS[r['metric']][0]} | "
                 f"{fmt(r['mean_diff'], r['ci95'], digits)}{' *' if r['significant'] else ''} | "
                 f"{100 * r['ref_wins_share']:.0f}% | {r['n']} |")

    L += ["", "## By demand level (car mean wait, s)", "",
          "| Demand | " + " | ".join(NAMES.get(c, c) for c in main_c) + " |", "|---|" + "---|" * len(main_c)]
    SC = {(r["controller"], r["scenario"], r["metric"]): r for r in scen_rows}
    for scen in ("low", "medium", "high", "asymmetric"):
        L.append(f"| {scen} | " + " | ".join(fmt(SC[(c, scen, 'car_wait_s')]['mean'], SC[(c, scen, 'car_wait_s')]['ci95'])
                                           for c in main_c) + " |")
    L += ["", "## By demand level (95th-percentile wait, s)", "",
          "| Demand | " + " | ".join(NAMES.get(c, c) for c in main_c) + " |", "|---|" + "---|" * len(main_c)]
    for scen in ("low", "medium", "high", "asymmetric"):
        L.append(f"| {scen} | " + " | ".join(fmt(SC[(c, scen, 'p95_wait_s')]['mean'], SC[(c, scen, 'p95_wait_s')]['ci95'])
                                           for c in main_c) + " |")

    if any(r["n"] for r in marl_rows):
        L += ["", "## MARL on network/demand combinations it was and was not trained on", "",
              "MARL minus adaptive EquiFlow on identical runs (negative = MARL better). All seeds are unseen.", "",
              "| Metric | trained combinations | unseen combinations |", "|---|---|---|"]
        MR = {(r["network_demand_in_training"], r["metric"]): r for r in marl_rows}
        for m in ("car_wait_s", "p95_wait_s", "jain_approach_wait", "ambulance_wait_s"):
            s, u = MR[(True, m)], MR[(False, m)]
            digits = 3 if m == "jain_approach_wait" else 2
            L.append(f"| {METRICS[m][0]} | {fmt(s['marl_minus_adaptive'], s['ci95'], digits)} (n={s['n']}) | "
                     f"{fmt(u['marl_minus_adaptive'], u['ci95'], digits)} (n={u['n']}) |")
    (d / "RESULTS_TABLES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def _write(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) and v == v else v) for k, v in r.items()})


if __name__ == "__main__":
    main()
