"""make_plots.py - figures for the report, from results/heldout (run_matrix.py + aggregate.py),
results/robustness.csv and marl/training_log.csv.

    python make_plots.py            # -> ../docs/figures/*.png (and .pdf for LaTeX)

Each controller keeps one colour in every figure. Every bar carries its value, so nothing depends on
colour alone (palette validated for colour-vision deficiency; see the dataviz palette check).
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results" / "heldout"
OUT = ROOT.parent / "docs" / "figures"

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"fixed": "#2a78d6", "actuated": "#eb6834", "fixed+preempt": "#1baf7a", "equiflow": "#eda100",
          "equiflow-marl": "#e87ba4"}
ABLATION_GREY = "#9a9893"
NAMES = {"fixed": "Fixed-time", "actuated": "Actuated", "fixed+preempt": "Fixed-time\n+ priority",
         "equiflow": "EquiFlow", "equiflow-marl": "EquiFlow\n(MARL)", "equiflow-recovery": "+ recovery\n(queue)",
         "equiflow-recovery-order": "+ recovery\n(re-order)", "equiflow-tail-v1": "first tail\nsettings",
         "equiflow-corridor": "+ corridor",
         "equiflow-nogapout": "no\ngap-out", "equiflow-noextend": "no green\nextension",
         "equiflow-nocorridor": "no\ncorridor", "equiflow-corridor-v1": "old\ncorridor",
         "equiflow-recovery-v1": "+ recovery\n(first rule)"}
MAIN = ["fixed", "actuated", "fixed+preempt", "equiflow", "equiflow-marl"]

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "legend.frameon": False,
})


def stats():
    S = {}
    for r in csv.DictReader((RES / "summary_stats.csv").open()):
        S[(r["controller"], r["metric"])] = (float(r["mean"]) if r["mean"] else None,
                                             float(r["ci95"]) if r["ci95"] not in ("", "nan") else 0.0)
    return S


def scen_stats():
    S = {}
    for r in csv.DictReader((RES / "by_scenario.csv").open()):
        S[(r["controller"], r["scenario"], r["metric"])] = (float(r["mean"]) if r["mean"] else None,
                                                            float(r["ci95"]) if r["ci95"] not in ("", "nan") else 0.0)
    return S


def bars(ax, ctrls, S, metric, title, unit="s", colors=None, digits=1):
    xs = range(len(ctrls))
    vals = [S.get((c, metric), (None, 0))[0] or 0.0 for c in ctrls]
    errs = [S.get((c, metric), (None, 0))[1] or 0.0 for c in ctrls]
    cols = [(colors or COLORS).get(c, ABLATION_GREY) for c in ctrls]
    ax.bar(xs, vals, width=0.62, color=cols, edgecolor=SURF, linewidth=2, zorder=2)
    ax.errorbar(xs, vals, yerr=errs, fmt="none", ecolor=INK2, elinewidth=1, capsize=3, zorder=3)
    top = max(v + e for v, e in zip(vals, errs)) or 1
    for x, v, e in zip(xs, vals, errs):
        ax.text(x, v + e + top * 0.02, f"{v:.{digits}f}", ha="center", va="bottom", color=INK, fontsize=8)
    ax.set_xticks(list(xs), [NAMES.get(c, c) for c in ctrls], fontsize=8)
    ax.set_ylim(0, top * 1.18)
    ax.set_title(title, loc="left")
    ax.set_ylabel(unit)
    ax.tick_params(length=0)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def fig_main(S):
    ctrls = [c for c in MAIN if (c, "car_wait_s") in S]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.4))
    bars(axs[0], ctrls, S, "ambulance_wait_s", "Ambulance: mean wait at signals")
    bars(axs[1], ctrls, S, "car_wait_s", "Cars: mean wait")
    bars(axs[2], ctrls, S, "p95_wait_s", "All ordinary vehicles: 95th-percentile wait")
    fig.suptitle("Held-out SUMO evaluation (mean ± 95% CI over runs)", x=0.01, ha="left", fontsize=11,
                 fontweight="bold", color=INK)
    fig.tight_layout()
    save(fig, "fig_main_comparison")


def fig_fairness(S):
    ctrls = [c for c in MAIN if (c, "car_wait_s") in S]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.4))
    bars(axs[0], ctrls, S, "max_wait_s", "Longest single wait")
    bars(axs[1], ctrls, S, "worst_approach_mean_wait_s", "Worst-served approach: mean wait")
    bars(axs[2], ctrls, S, "affected_mean_wait_s", "Vehicles held by an ambulance: mean wait")
    bars(axs[3], ctrls, S, "jain_approach_wait", "Jain index across approaches", unit="1 = equal",
         digits=3)
    axs[3].set_ylim(0, 1.12)
    fig.tight_layout()
    save(fig, "fig_fairness")


def fig_ablation(S):
    ctrls = [c for c in ("equiflow", "equiflow-noextend", "equiflow-nogapout", "equiflow-tail-v1",
                         "equiflow-recovery", "equiflow-recovery-order", "equiflow-recovery-v1")
             if (c, "car_wait_s") in S]
    if len(ctrls) < 2:
        return
    fig, axs = plt.subplots(1, 3, figsize=(18, 3.8))
    bars(axs[0], ctrls, S, "car_wait_s", "Cars: mean wait")
    bars(axs[1], ctrls, S, "p95_wait_s", "95th-percentile wait")
    bars(axs[2], ctrls, S, "affected_mean_wait_s", "Vehicles held by an ambulance: mean wait")
    fig.suptitle("What each part of EquiFlow contributes (grey = one part switched off, changed or added)", x=0.01, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    save(fig, "fig_ablation")


def fig_by_demand(SC):
    ctrls = [c for c in MAIN if (c, "high", "car_wait_s") in SC]
    scens = ["low", "medium", "high", "asymmetric"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, metric, title in ((axs[0], "car_wait_s", "Cars: mean wait by demand"),
                              (axs[1], "p95_wait_s", "95th-percentile wait by demand")):
        for c in ctrls:
            ys = [SC[(c, s, metric)][0] for s in scens]
            ax.plot(range(4), ys, color=COLORS[c], linewidth=2, marker="o", markersize=5,
                    markeredgecolor=SURF, markeredgewidth=1.5, label=NAMES[c].replace("\n", " "), zorder=3)
        ax.set_xticks(range(4), scens)
        ax.set_xlim(-0.2, 3.2)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("s")
        ax.set_title(title, loc="left")
        ax.tick_params(length=0)
    h, lab = axs[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=len(lab), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, "fig_by_demand")


def fig_robustness():
    f = ROOT / "results" / "robustness.csv"
    if not f.exists():
        return
    rows = [r for r in csv.DictReader(f.open()) if r.get("seed") == "6"]
    votes = sorted({r.get("vote") or "5/8 mean>=0.65" for r in rows}, reverse=True)
    vcol = ["#2a78d6", "#eda100", "#1baf7a"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
    for i, vote in enumerate(votes):
        vr = [r for r in rows if (r.get("vote") or "5/8 mean>=0.65") == vote]
        for ax, key, xkey, fixed, title in (
                (axs[0], "false_confirmations", "fp_prob", ("miss_prob", 0.0), "False priority runs per hour"),
                (axs[1], "ambulance_wait_s", "miss_prob", ("fp_prob", 0.0), "Ambulance mean wait (s)")):
            xs = sorted({float(r[xkey]) for r in vr})
            pts = []
            for x in xs:
                v = [float(r[key]) for r in vr if float(r[xkey]) == x and float(r[fixed[0]]) == fixed[1]]
                if v:
                    pts.append((x, sum(v) / len(v)))
            if pts:
                ax.plot([p[0] * 100 for p in pts], [p[1] for p in pts], color=vcol[i % 3], linewidth=2, marker="o",
                        markersize=5, markeredgecolor=SURF, markeredgewidth=1.5, label=f"vote {vote}")
            ax.set_title(title, loc="left")
    axs[0].set_xlabel("frames wrongly scored as ambulance (%), no missed frames")
    axs[1].set_xlabel("frames missed (%), no false alarms")
    for ax in axs:
        ax.set_ylim(bottom=0)
        ax.tick_params(length=0)
    axs[0].legend(fontsize=7)
    fig.suptitle("Robustness to camera errors (sector grid + cross junction, heavy traffic, seed 6)", x=0.01, ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    fig.tight_layout()
    save(fig, "fig_robustness")


def fig_marl_training():
    f = ROOT.parent / "marl" / "training_log.csv"
    if not f.exists():
        return
    rows = list(csv.DictReader(f.open()))
    ep = [int(r["episode"]) for r in rows]
    mw = [float(r["mean_wait_s"]) for r in rows]
    eps = [float(r["epsilon"]) for r in rows]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.2))
    axs[0].plot(ep, mw, color=COLORS["equiflow-marl"], linewidth=1.2, alpha=0.5)
    k = 5
    sm = [sum(mw[max(0, i - k + 1):i + 1]) / len(mw[max(0, i - k + 1):i + 1]) for i in range(len(mw))]
    axs[0].plot(ep, sm, color=INK, linewidth=2, label=f"{k}-episode moving average")
    axs[0].set_title("MARL training: mean wait per episode (s)", loc="left")
    axs[0].legend(fontsize=7)
    axs[1].plot(ep, eps, color=INK2, linewidth=2)
    axs[1].set_title("Exploration rate (epsilon)", loc="left")
    for ax in axs:
        ax.set_xlabel("episode")
        ax.set_ylim(bottom=0)
        ax.tick_params(length=0)
    fig.tight_layout()
    save(fig, "fig_marl_training")


def main():
    S = stats()
    fig_main(S)
    fig_fairness(S)
    fig_ablation(S)
    fig_by_demand(scen_stats())
    fig_robustness()
    fig_marl_training()


if __name__ == "__main__":
    main()
