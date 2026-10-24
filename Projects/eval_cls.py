from pathlib import Path
from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(r"C:\Smester7\Projects\runs\cls_v1-3\weights\best.pt")
    amb = next(k for k, v in model.names.items() if v == "ambulance")
    root = Path(r"C:\Smester7\Projects\crops\test")
    TH = 0.5
    for cls in ("ambulance", "other_vehicle"):
        for src in ("pub", "pk", "local"):
            files = sorted((root / cls).glob(f"{src}_*.jpg"))
            if not files:
                continue
            probs = [r.probs.data[amb].item()
                     for r in model.predict([str(f) for f in files], imgsz=96, batch=64,
                                            device=0, stream=True, verbose=False)]
            flagged = sum(p >= TH for p in probs)
            if cls == "ambulance":
                print(f"{src:6s} ambulance crops: {len(files):4d} | recall @{TH}: {flagged/len(files):.3f}")
            else:
                print(f"{src:6s} other_vehicle crops: {len(files):4d} | false-alarm rate @{TH}: {flagged/len(files):.3f}")