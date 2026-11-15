"""train_cls_v5.py - try to raise ambulance recall (mid-report Sections 6.10 and 7.7).

The mid-report's corrective actions, one change at a time, each compared with run cls_v4-2:
  A  --imgsz 128             larger input (crops are 96 px now; fine detail is lost)
  B  --oversample 2          repeat every ambulance training crop N times (class is ~17% of train)
  C  --model yolo26s-cls.pt  larger model
Threshold tuning on the val PR curve needs no training: eval_detector.py --target-recall 0.95

    cd Projects
    python train_cls_v5.py --name cls_v5_img128 --imgsz 128
    python train_cls_v5.py --name cls_v5_os2 --oversample 2
    python train_cls_v5.py --name cls_v5_s --model yolo26s-cls.pt
    python train_cls_v5.py --compare cls_v4-2 cls_v5_img128 cls_v5_os2 cls_v5_s     # val-split table

Each run is then evaluated on val (never test) and written to runs/<name>/val_metrics.json. Pick the best
on val, and only then run eval_detector.py on the test split with that model, once.
Oversampling builds runs/<name>/data/ (train with repeated ambulance crops; val/test copied unchanged).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def build_oversampled(src: Path, dst: Path, factor: int) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    for split in ("train", "val", "test"):
        for cls in ("ambulance", "other_vehicle"):
            s, d = src / split / cls, dst / split / cls
            d.mkdir(parents=True, exist_ok=True)
            files = [f for f in s.iterdir() if f.is_file()]
            for f in files:
                shutil.copy2(f, d / f.name)
                if split == "train" and cls == "ambulance":
                    for k in range(1, factor):
                        shutil.copy2(f, d / f"{f.stem}_os{k}{f.suffix}")
    return dst


def val_metrics(weights: Path, data: Path, imgsz: int, device) -> dict:
    import numpy as np
    from ultralytics import YOLO

    from eval_detector import confusion, list_split, pr_auc, predict, scores
    items = list_split(data / "val")
    y = np.array([t for _, t in items])
    p = predict(YOLO(str(weights)), [f for f, _ in items], imgsz, device, 64)
    out = {"weights": str(weights), "imgsz": imgsz, "pr_auc": round(pr_auc(y, p), 4)}
    for th in (0.5, 0.3):
        s = scores(confusion(y, p, th))
        out[f"th{th}"] = {k: round(s[k], 4) for k in ("accuracy", "precision", "recall", "f1", "false_alarm_rate")}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(HERE / "crops"))
    ap.add_argument("--name", default="cls_v5")
    ap.add_argument("--model", default="yolo26n-cls.pt")
    ap.add_argument("--imgsz", type=int, default=96)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--oversample", type=int, default=1, help="repeat each ambulance training crop this many times")
    ap.add_argument("--device", default="0")
    ap.add_argument("--compare", nargs="+", help="only print a val-split comparison of these run names")
    a = ap.parse_args()
    runs = HERE / "runs"

    if a.compare:
        print("| run | imgsz | PR-AUC | recall@0.5 | precision@0.5 | F1@0.5 | recall@0.3 | precision@0.3 |")
        print("|---|---|---|---|---|---|---|---|")
        for name in a.compare:
            f = runs / name / "val_metrics.json"
            if not f.exists():
                w = runs / name / "weights" / "best.pt"
                if not w.exists():
                    print(f"| {name} | missing |")
                    continue
                f.write_text(json.dumps(val_metrics(w, Path(a.data), 96, a.device), indent=2))
            m = json.loads(f.read_text())
            t5, t3 = m["th0.5"], m["th0.3"]
            print(f"| {name} | {m['imgsz']} | {m['pr_auc']:.3f} | {t5['recall']:.3f} | {t5['precision']:.3f} | "
                  f"{t5['f1']:.3f} | {t3['recall']:.3f} | {t3['precision']:.3f} |")
        return

    from ultralytics import YOLO
    data = Path(a.data)
    if a.oversample > 1:
        data = build_oversampled(data, runs / a.name / "data", a.oversample)
    model = YOLO(a.model)
    model.train(data=str(data), imgsz=a.imgsz, epochs=a.epochs, batch=a.batch, device=a.device,
                project=str(runs), name=a.name, exist_ok=True)
    best = runs / a.name / "weights" / "best.pt"
    m = val_metrics(best, Path(a.data), a.imgsz, a.device)
    m.update(model=a.model, oversample=a.oversample, epochs=a.epochs)
    (runs / a.name / "val_metrics.json").write_text(json.dumps(m, indent=2))
    print(json.dumps(m, indent=2))
    print(f"\nCompare: python train_cls_v5.py --compare cls_v4-2 {a.name}")


if __name__ == "__main__":
    main()
