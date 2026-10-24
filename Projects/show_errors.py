from collections import Counter
from pathlib import Path
import cv2, numpy as np
from ultralytics import YOLO

WEIGHTS = r"C:\Smester7\Projects\runs\cls_v1\weights\best.pt"
ROOT = Path(r"C:\Smester7\Projects\crops\test")
TH = 0.5

model = YOLO(WEIGHTS)
amb = next(k for k, v in model.names.items() if v == "ambulance")

def probs(files):
    return [r.probs.data[amb].item()
            for r in model.predict([str(f) for f in files], imgsz=96, batch=64,
                                   device=0, stream=True, verbose=False)]

def source(f):
    n = f.name
    return "pk" if n.startswith("pk_") else "local" if n.startswith("local_") else n.split("_")[1]

def sheet(items, name, tile=140, cols=10, max_n=100):
    items = items[:max_n]
    if not items:
        print(name, "- kuch nahi"); return
    rows = (len(items) + cols - 1) // cols
    grid = np.full((rows * tile, cols * tile, 3), 30, np.uint8)
    for k, (f, p) in enumerate(items):
        im = cv2.imread(str(f))
        if im is None: continue
        h, w = im.shape[:2]; s = tile / max(h, w)
        im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))))
        r, c = divmod(k, cols)
        grid[r * tile:r * tile + im.shape[0], c * tile:c * tile + im.shape[1]] = im
        cv2.putText(grid, f"{p:.2f}", (c * tile + 3, r * tile + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    cv2.imwrite(name, grid)

miss, fa = [], []
files = sorted((ROOT / "ambulance").glob("*.jpg"))
miss = [(f, p) for f, p in zip(files, probs(files)) if p < TH]
files = sorted((ROOT / "other_vehicle").glob("*.jpg"))
fa = [(f, p) for f, p in zip(files, probs(files)) if p >= TH]

print("missed ambulances:", len(miss), "| false alarms:", len(fa))
print("missed by source:", dict(Counter(source(f) for f, _ in miss)))
print("false alarms by source:", dict(Counter(source(f) for f, _ in fa)))
sheet(sorted(miss, key=lambda t: t[1]), "errors_missed.jpg")
sheet(sorted(fa, key=lambda t: -t[1]), "errors_false_alarms.jpg")