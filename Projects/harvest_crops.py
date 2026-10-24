import csv, shutil, sys
from collections import defaultdict
from pathlib import Path
import cv2
from ultralytics import YOLO

DET_WEIGHTS = "yolo26s.pt"
CLS_WEIGHTS = r"C:\Smester7\Projects\runs\cls_v1-3\weights\best.pt"
VIDEO_DIR = Path(r"C:\Smester7\Projects\videos")
CROPS = Path(r"C:\Smester7\Projects\crops")
GT = Path(r"C:\Smester7\Projects\ground_truth.csv")
SPLIT = "train"
IMGSZ, PAD, MIN_SIDE = 1280, 0.12, 20
EVERY, EVERY_NEAR = 6, 2          # normal: har 6th frame; ambulance window ke aas paas: har 2nd
SAFE = 3.0                        # window ke aas paas itne second
MAX_NEG_PER_TRACK = 12

def windows_for(name):
    w = []
    if GT.exists():
        with open(GT, newline="", encoding="utf-8-sig") as f:   # utf-8-sig strips the BOM Excel adds
            for r in csv.DictReader(f):
                if r["video"] == name and r["start_s"].strip() and r["end_s"].strip():
                    w.append((float(r["start_s"]), float(r["end_s"])))
    return w

def harvest(name):
    wins = windows_for(name)
    paths = list(VIDEO_DIR.glob(name + ".*"))
    if not paths:
        print("VIDEO NAHI MILI:", name); return
    video = str(paths[0])
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    min_side = MIN_SIDE * W / 1920
    cls, det = YOLO(CLS_WEIGHTS), YOLO(DET_WEIGHTS)
    amb = next(k for k, v in cls.names.items() if v == "ambulance")
    tmp = CROPS.parent / "harvest_tmp" / name
    shutil.rmtree(tmp, ignore_errors=True)
    tracks = defaultdict(list)                       # tid -> [(t, p, path)]
    stream = det.track(source=video, tracker="bytetrack.yaml", persist=True, stream=True,
                       imgsz=IMGSZ, conf=0.35, classes=[2, 3, 5, 7], device=0, verbose=False)
    for f, r in enumerate(stream):
        t = f / fps
        near = any(s - SAFE <= t <= e + SAFE for s, e in wins)
        if f % (EVERY_NEAR if near else EVERY) != 0 or r.boxes is None or r.boxes.id is None:
            continue
        frame, items, crops = r.orig_img, [], []
        for tid, (x1, y1, x2, y2) in zip(r.boxes.id.int().cpu().tolist(), r.boxes.xyxy.cpu().numpy()):
            bw, bh = x2 - x1, y2 - y1
            if min(bw, bh) < min_side:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            a, b = int(max(0, cx - bw / 2 * (1 + PAD))), int(max(0, cy - bh / 2 * (1 + PAD)))
            c, d = int(min(W, cx + bw / 2 * (1 + PAD))), int(min(H, cy + bh / 2 * (1 + PAD)))
            crop = frame[b:d, a:c]
            if crop.size:
                items.append(tid); crops.append(crop)
        if not crops:
            continue
        ps = [rr.probs.data[amb].item() for rr in cls.predict(crops, imgsz=96, device=0, verbose=False)]
        for tid, crop, p in zip(items, crops, ps):
            d = tmp / str(tid); d.mkdir(parents=True, exist_ok=True)
            path = d / f"{f:06d}.jpg"; cv2.imwrite(str(path), crop)
            tracks[tid].append((t, p, path))

    amb_dir, neg_dir = CROPS / SPLIT / "ambulance", CROPS / SPLIT / "other_vehicle"
    amb_dir.mkdir(parents=True, exist_ok=True); neg_dir.mkdir(parents=True, exist_ok=True)
    n_amb = n_neg = 0
    for tid, items in tracks.items():
        near = [x for x in items if any(s - SAFE <= x[0] <= e + SAFE for s, e in wins)]
        if near:
            inside = [x for x in items if any(s - 1 <= x[0] <= e + 1 for s, e in wins)]
            if inside and max(x[1] for x in inside) >= 0.5:
                for t, p, pa in inside:
                    shutil.copy(pa, amb_dir / f"local_amb_{name}_{tid}_{pa.stem}.jpg"); n_amb += 1
            continue                                  # window ke aas paas ki baqi tracks: chhor do
        step = max(1, len(items) // MAX_NEG_PER_TRACK)
        for t, p, pa in items[::step][:MAX_NEG_PER_TRACK]:
            shutil.copy(pa, neg_dir / f"local_neg_{name}_{tid}_{pa.stem}.jpg"); n_neg += 1
    print(f"{name}: ambulance candidates {n_amb} | negatives {n_neg} | tracks {len(tracks)}")

if __name__ == "__main__":
    for n in sys.argv[1:]:
        harvest(n)