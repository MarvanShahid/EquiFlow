"""Formal evaluation of the ambulance recogniser (Iteration 2): held-out TEST split + latency.

What it measures
  1. Classification on crops/<split>/{ambulance,other_vehicle}: confusion matrix, accuracy,
     precision, recall, F1, specificity, false-alarm rate, balanced accuracy, ROC-AUC and PR-AUC,
     per data source (file prefix pub_ / pk_ / local_ / ...) and a threshold sweep.
  2. Which images it gets wrong (errors.csv), for error analysis.
  3. Latency: the classifier per crop (batch 1 and batched) and the vehicle detector (yolo26s) per
     frame at the pipeline's imgsz, on whatever device is used (GPU if available).

    cd Projects
    python eval_detector.py                         # test split, threshold 0.5, latency on
    python eval_detector.py --split val             # val split with the pipeline model (cls_v5_img128)
    python eval_detector.py --split val --weights runs/cls_v4-2/weights/best.pt --imgsz 96   # mid-report model
    python eval_detector.py --threshold 0.6         # the per-frame threshold the tracker uses (th_frame)
    python eval_detector.py --no-latency --device cpu
    python eval_detector.py --target-recall 0.95    # pick the threshold on VAL for 95% recall, report TEST at it

Results land in runs/eval_<split>/: metrics.json, summary.md, threshold_sweep.csv, per_source.csv,
errors.csv. summary.md is written so it can go straight into the report.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import time
from datetime import datetime
from pathlib import Path

import gpu_compat  # noqa: F401,E402  (see gpu_compat.py)
import numpy as np

HERE = Path(__file__).resolve().parent  # the Projects folder
CLASSES = ("ambulance", "other_vehicle")
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ----------------------------------------------------------------------------- metrics (pure numpy)
def confusion(y_true: np.ndarray, p_amb: np.ndarray, th: float) -> dict:
    pred = p_amb >= th
    tp = int(np.sum(pred & y_true))
    fp = int(np.sum(pred & ~y_true))
    fn = int(np.sum(~pred & y_true))
    tn = int(np.sum(~pred & ~y_true))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def scores(c: dict) -> dict:
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    n = tp + fp + fn + tn
    div = lambda a, b: a / b if b else float("nan")  # noqa: E731
    p, r = div(tp, tp + fp), div(tp, tp + fn)
    spec = div(tn, tn + fp)
    return {"n": n, "accuracy": div(tp + tn, n), "precision": p, "recall": r,
            "f1": div(2 * p * r, p + r) if (p == p and r == r) else float("nan"),
            "specificity": spec, "false_alarm_rate": div(fp, fp + tn),
            "balanced_accuracy": (r + spec) / 2 if (r == r and spec == spec) else float("nan"),
            "majority_baseline": div(max(tp + fn, fp + tn), n)}


def roc_auc(y: np.ndarray, s: np.ndarray) -> float:
    """Mann-Whitney U formulation, ties counted as half."""
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    allv = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(allv))
    i = 0
    while i < len(allv):                      # average ranks over ties
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    r = np.empty(len(allv))
    r[order] = ranks
    rpos = r[:len(pos)].sum()
    return float((rpos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def pr_auc(y: np.ndarray, s: np.ndarray) -> float:
    """Average precision (area under the precision-recall curve, step-wise)."""
    if y.sum() == 0:
        return float("nan")
    o = np.argsort(-s, kind="mergesort")
    ss, yt = s[o], y[o]
    last = np.r_[np.where(np.diff(ss))[0], len(ss) - 1]   # one point per distinct score (ties together)
    tp = np.cumsum(yt)[last]
    prec = tp / (last + 1)
    rec = tp / y.sum()
    return float(np.sum(np.diff(np.r_[0.0, rec]) * prec))


def source_of(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[0] if "_" in stem else "other"


# ----------------------------------------------------------------------------- data + inference
def list_split(root: Path) -> list[tuple[Path, bool]]:
    items = []
    for cls in CLASSES:
        d = root / cls
        if not d.is_dir():
            raise SystemExit(f"Missing folder {d}. Expected {root}/ambulance and {root}/other_vehicle "
                             f"(the crops dataset the classifier was trained on).")
        items += [(f, cls == "ambulance") for f in sorted(d.iterdir()) if f.suffix.lower() in EXTS]
    if not items:
        raise SystemExit(f"No images under {root}")
    return items


def predict(model, files: list[Path], imgsz: int, device, batch: int) -> np.ndarray:
    amb = next(k for k, v in model.names.items() if v == "ambulance")
    out = []
    for i in range(0, len(files), batch):
        chunk = [str(f) for f in files[i:i + batch]]
        for r in model.predict(chunk, imgsz=imgsz, batch=len(chunk), device=device, verbose=False):
            out.append(float(r.probs.data[amb].item()))
    return np.array(out)


def _sync(device) -> None:
    try:
        import torch
        if torch.cuda.is_available() and str(device) not in ("cpu",):
            torch.cuda.synchronize()
    except Exception:  # noqa: BLE001
        pass


def time_it(fn, warmup: int, runs: int, device) -> dict:
    for _ in range(warmup):
        fn()
    _sync(device)
    ts = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        _sync(device)
        ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    return {"mean_ms": statistics.mean(ts), "median_ms": statistics.median(ts),
            "p95_ms": ts[min(len(ts) - 1, int(0.95 * len(ts)))], "runs": runs}


def latency(cls_model, det_weights: str | None, sample: list[Path], cls_imgsz: int, det_imgsz: int,
            device, runs: int, frame: Path | None) -> dict:
    import cv2
    crops = [cv2.imread(str(f)) for f in sample[:64]]
    crops = [c for c in crops if c is not None]
    res = {}
    one = crops[0]
    res["classifier_batch1"] = time_it(
        lambda: cls_model.predict(one, imgsz=cls_imgsz, device=device, verbose=False), 10, runs, device)
    b = crops[:16]
    t = time_it(lambda: cls_model.predict(b, imgsz=cls_imgsz, batch=len(b), device=device, verbose=False),
                3, max(10, runs // 5), device)
    t["per_crop_ms"] = t["mean_ms"] / len(b)
    t["batch"] = len(b)
    res["classifier_batch16"] = t
    if det_weights:
        from ultralytics import YOLO
        det = YOLO(det_weights)
        img = cv2.imread(str(frame)) if frame else None
        if img is None:                   # no frame given: a synthetic 1080p frame (timing only)
            img = np.random.default_rng(0).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
        res["detector_frame"] = time_it(
            lambda: det.predict(img, imgsz=det_imgsz, classes=[2, 3, 5, 7], device=device, verbose=False),
            5, max(10, runs // 3), device)
        res["detector_frame"]["imgsz"] = det_imgsz
        res["detector_frame"]["frame"] = str(frame) if frame else "synthetic 1920x1080"
        # one frame of the live pipeline = detector + one classifier call per vehicle (batched)
        per_vehicle = res["classifier_batch16"]["per_crop_ms"]
        res["pipeline_estimate"] = {
            f"{k}_vehicles_ms": round(res["detector_frame"]["mean_ms"] + k * per_vehicle, 1) for k in (5, 10, 20)}
    return res


# ----------------------------------------------------------------------------- report
def fmt(x: float, pct: bool = True) -> str:
    if x != x:
        return "n/a"
    return f"{100 * x:.1f}%" if pct else f"{x:.3f}"


def write_outputs(out: Path, split: str, th: float, files, y, p, model_path, lat, device, tuned=None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    c = confusion(y, p, th)
    s = scores(c)
    metrics = {"split": split, "threshold": th, "weights": str(model_path), "device": str(device),
               "evaluated_at": datetime.now().isoformat(timespec="seconds"), "host": platform.node(),
               "counts": {"ambulance": int(y.sum()), "other_vehicle": int((~y).sum())},
               "confusion": c, **{k: round(v, 4) if v == v else None for k, v in s.items()},
               "roc_auc": round(roc_auc(y, p), 4), "pr_auc": round(pr_auc(y, p), 4)}
    if tuned:
        metrics["threshold_tuning"] = tuned

    # threshold sweep
    sweep = []
    for t in np.round(np.arange(0.05, 0.96, 0.05), 2):
        cc = confusion(y, p, float(t))
        ss = scores(cc)
        sweep.append({"threshold": float(t), **cc, **{k: round(ss[k], 4) for k in
                                                     ("precision", "recall", "f1", "false_alarm_rate")}})
    with open(out / "threshold_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sweep[0].keys()))
        w.writeheader()
        w.writerows(sweep)
    valid = [r for r in sweep if r["f1"] == r["f1"]]
    best = max(valid, key=lambda r: r["f1"]) if valid else {"threshold": th, "f1": float("nan"),
                                                            "precision": float("nan"), "recall": 0.0}
    metrics["best_f1_threshold"] = {"threshold": best["threshold"], "f1": best["f1"],
                                    "precision": best["precision"], "recall": best["recall"]}
    hi = [r for r in sweep if r["precision"] == r["precision"] and r["precision"] >= 0.95]
    if hi:
        metrics["max_recall_at_precision_0.95"] = max(hi, key=lambda r: r["recall"])

    # per source
    srcs = sorted({source_of(f) for f in files})
    rows = []
    for src in srcs:
        m = np.array([source_of(f) == src for f in files])
        cc = confusion(y[m], p[m], th)
        ss = scores(cc)
        rows.append({"source": src, "ambulance": int(y[m].sum()), "other_vehicle": int((~y[m]).sum()), **cc,
                     "recall": round(ss["recall"], 4) if ss["recall"] == ss["recall"] else "",
                     "false_alarm_rate": round(ss["false_alarm_rate"], 4) if ss["false_alarm_rate"] == ss["false_alarm_rate"] else ""})
    with open(out / "per_source.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    metrics["per_source"] = rows

    # errors, most confident mistakes first
    err = [(str(f), "ambulance" if yy else "other_vehicle", round(float(pp), 4))
           for f, yy, pp in zip(files, y, p) if (pp >= th) != yy]
    err.sort(key=lambda e: -abs(e[2] - th))
    with open(out / "errors.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "true_class", "p_ambulance"])
        w.writerows(err)
    with open(out / "scores.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "true_class", "p_ambulance"])
        w.writerows((str(ff), "ambulance" if yy else "other_vehicle", round(float(pp), 5))
                    for ff, yy, pp in zip(files, y, p))

    if lat:
        metrics["latency"] = {k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                              for k, v in lat.items()}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # markdown summary for the report
    L = [f"# Ambulance recogniser: {split} split", "",
         f"Weights `{Path(model_path).name}`, threshold {th}, device {device}, {metrics['evaluated_at']}.", "",
         f"Images: {c['tp'] + c['fn']} ambulance, {c['tn'] + c['fp']} other vehicle.", "",
         *([f"Threshold {th:.4f} was chosen on the **val** split as the highest giving ambulance recall >= "
            f"{tuned['target_recall']} there (val recall {tuned['val_recall']:.3f}, precision "
            f"{tuned['val_precision']:.3f}); the test split was not used to choose it.", ""] if tuned else []),
         "| | true ambulance | true other |", "|---|---|---|",
         f"| predicted ambulance | {c['tp']} (TP) | {c['fp']} (FP) |",
         f"| predicted other | {c['fn']} (FN) | {c['tn']} (TN) |", "",
         "| Metric | Value |", "|---|---|",
         f"| Accuracy | {fmt(s['accuracy'])} (majority-class baseline {fmt(s['majority_baseline'])}) |",
         f"| Ambulance precision | {fmt(s['precision'])} |",
         f"| Ambulance recall | {fmt(s['recall'])} |",
         f"| F1 | {fmt(s['f1'], False)} |",
         f"| False-alarm rate | {fmt(s['false_alarm_rate'])} |",
         f"| Balanced accuracy | {fmt(s['balanced_accuracy'])} |",
         f"| ROC-AUC | {metrics['roc_auc']:.3f} |",
         f"| PR-AUC (average precision) | {metrics['pr_auc']:.3f} |", "",
         f"Best F1 over thresholds: {fmt(best['f1'], False)} at {best['threshold']} "
         f"(precision {fmt(best['precision'])}, recall {fmt(best['recall'])}).", ""]
    L += ["| Source | ambulance | other | recall | false-alarm rate |", "|---|---|---|---|---|"]
    L += [f"| {r['source']} | {r['ambulance']} | {r['other_vehicle']} | "
          f"{fmt(r['recall']) if r['recall'] != '' else 'n/a'} | "
          f"{fmt(r['false_alarm_rate']) if r['false_alarm_rate'] != '' else 'n/a'} |" for r in rows]
    if lat:
        L += ["", f"## Latency ({device})", "", "| Stage | mean | median | p95 |", "|---|---|---|---|"]
        for k, v in lat.items():
            if "mean_ms" in v:
                extra = f" ({v['per_crop_ms']:.2f} ms per crop)" if "per_crop_ms" in v else ""
                L.append(f"| {k} | {v['mean_ms']:.1f} ms{extra} | {v['median_ms']:.1f} ms | {v['p95_ms']:.1f} ms |")
        if "pipeline_estimate" in lat:
            pe = lat["pipeline_estimate"]
            L += ["", "Estimated time per frame for the full pipeline (detector + classifier per vehicle): " +
                  ", ".join(f"{k.split('_')[0]} vehicles {v} ms" for k, v in pe.items()) + "."]
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(HERE / "crops"), help="crops dataset root (has train/val/test)")
    ap.add_argument("--split", default="test", choices=["test", "val", "train"])
    ap.add_argument("--weights", default=str(HERE / "runs" / "cls_v5_img128" / "weights" / "best.pt"))
    ap.add_argument("--det-weights", default=str(HERE / "yolo26s.pt"), help="vehicle detector for latency")
    ap.add_argument("--imgsz", type=int, default=128, help="classifier input size (cls_v5_img128: 128, cls_v4-2: 96)")
    ap.add_argument("--det-imgsz", type=int, default=1280)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--device", default=None, help="0 for the first GPU, cpu; default: GPU if available")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--no-latency", action="store_true")
    ap.add_argument("--latency-runs", type=int, default=100)
    ap.add_argument("--frame", help="a real video frame (jpg/png) for detector latency")
    ap.add_argument("--out", help="output folder (default runs/eval_<split>)")
    ap.add_argument("--target-recall", type=float,
                    help="choose the threshold on the val split as the highest one reaching this ambulance recall, "
                         "then evaluate --split at it (threshold tuning without touching the test set)")
    a = ap.parse_args()

    from ultralytics import YOLO
    if a.device is None:
        try:
            import torch
            a.device = 0 if torch.cuda.is_available() else "cpu"
        except ImportError:
            a.device = "cpu"
    items = list_split(Path(a.data) / a.split)
    files = [f for f, _ in items]
    y = np.array([t for _, t in items])
    print(f"{a.split}: {int(y.sum())} ambulance + {int((~y).sum())} other-vehicle crops, device {a.device}")
    model = YOLO(a.weights)
    tuned = None
    if a.target_recall is not None:
        v_items = list_split(Path(a.data) / "val")
        v_y = np.array([t for _, t in v_items])
        v_p = predict(model, [f for f, _ in v_items], a.imgsz, a.device, a.batch)
        cands = sorted(set(np.round(v_p, 4).tolist()) | {0.5}, reverse=True)
        ok = [t for t in cands if scores(confusion(v_y, v_p, t))["recall"] >= a.target_recall]
        a.threshold = float(ok[0]) if ok else float(min(cands))
        vs = scores(confusion(v_y, v_p, a.threshold))
        tuned = {"on": "val", "target_recall": a.target_recall, "threshold": round(a.threshold, 4),
                 "val_recall": round(vs["recall"], 4), "val_precision": round(vs["precision"], 4),
                 "val_false_alarm_rate": round(vs["false_alarm_rate"], 4)}
        print(f"threshold tuned on val: {a.threshold:.4f} (val recall {vs['recall']:.3f}, "
              f"precision {vs['precision']:.3f})")
    t0 = time.time()
    p = predict(model, files, a.imgsz, a.device, a.batch)
    print(f"classified {len(files)} crops in {time.time() - t0:.1f} s")
    lat = None
    if not a.no_latency:
        print("measuring latency ...")
        det = a.det_weights if a.det_weights and Path(a.det_weights).exists() else None
        lat = latency(model, det, files, a.imgsz, a.det_imgsz, a.device, a.latency_runs,
                      Path(a.frame) if a.frame else None)
    out = Path(a.out) if a.out else HERE / "runs" / (f"eval_{a.split}" + (f"_recall{a.target_recall:g}" if tuned else ""))
    m = write_outputs(out, a.split, a.threshold, files, y, p, a.weights, lat, a.device, tuned)
    print((out / "summary.md").read_text(encoding="utf-8"))
    print(f"saved to {out}  (metrics.json, summary.md, threshold_sweep.csv, per_source.csv, errors.csv)")
    if m.get("recall") is not None and m["recall"] < 0.9:
        print("note: ambulance recall is below 90%; see errors.csv and try a lower --threshold "
              "(threshold_sweep.csv shows the trade-off)")


if __name__ == "__main__":
    main()
