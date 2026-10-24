import math
import time
from collections import defaultdict, deque
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO

# ============================================================
# 1. SETTINGS
# ============================================================

# Model 1: vehicle detector (COCO) | Model 2: ambulance classifier (yours)
DET_WEIGHTS = "yolo26s.pt"
CLS_WEIGHTS = r"C:\Smester7\Projects\runs\cls_v4\weights\best.pt"

VIDEO_PATHS = {
    "North": r"C:\Smester7\Projects\videos\test11.mp4",
    "South": r"C:\Smester7\Projects\videos\test12.mp4",
    "East":  r"C:\Smester7\Projects\videos\v1.mp4",
    "West":  r"C:\Smester7\Projects\videos\v2.mp4",
}

DEVICE = 0                  # GPU 0. Use "cpu" if no GPU.
IMGSZ = 1280                # detector input size
DET_CONF = 0.35             # detector confidence
VEHICLE_CLASSES = [2, 3, 5, 7]   # COCO: car, motorcycle, bus, truck
CLS_IMGSZ = 96              # classifier input size

# Voting rule (same as your tracking script)
TH_FRAME = 0.6              # crop counts as "ambulance vote" if p >= this
M, K = 8, 5                 # need K positive votes in the last M frames
MEAN_MIN = 0.65             # mean p over last M frames must be >= this
RELEASE = 1                 # drop confirmation when votes <= this
MIN_MOVE = 0.00             # min movement (fraction of frame width); raise to ignore stationary objects
PAD, MIN_SIDE = 0.12, 20    # crop padding, min box side (pixels @ 1920 width)

ALERT_COOLDOWN_SECONDS = 10

# ============================================================
# 2. LOAD MODELS
# ============================================================

print("Loading models...")
classifier = YOLO(CLS_WEIGHTS)
AMB = next(k for k, v in classifier.names.items() if v == "ambulance")

# One detector instance PER direction, so each direction has its own tracker state.
detectors = {d: YOLO(DET_WEIGHTS) for d in VIDEO_PATHS}
print("Classifier classes:", classifier.names)
print("-" * 60)

# ============================================================
# 3. OPEN ALL FOUR VIDEOS
# ============================================================

caps = {}
for direction, path in VIDEO_PATHS.items():
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open {direction} video: {path}")
        for c in caps.values():
            c.release()
        raise SystemExit("Please correct the video paths and run again.")
    caps[direction] = cap


# ============================================================
# 4. PER-DIRECTION STATE
# ============================================================

class DirectionState:
    def __init__(self):
        self.votes = defaultdict(lambda: deque(maxlen=M))
        self.probs = defaultdict(list)
        self.centers = defaultdict(lambda: deque(maxlen=15))
        self.active = set()        # currently confirmed ambulance track IDs
        self.confirmed = set()     # all track IDs ever confirmed
        self.last_alert = 0.0


states = {d: DirectionState() for d in VIDEO_PATHS}


def process_frame(direction, frame):
    """Detect -> track -> classify -> vote. Returns annotated frame."""
    st = states[direction]
    det = detectors[direction]
    H, W = frame.shape[:2]
    min_side = MIN_SIDE * W / 1920
    thick = max(2, W // 600)
    font_scale = max(0.6, W / 1800)

    # ---- Model 1: vehicle detection + ByteTrack ----
    r = det.track(
        source=frame,
        tracker="bytetrack.yaml",
        persist=True,
        imgsz=IMGSZ,
        conf=DET_CONF,
        classes=VEHICLE_CLASSES,
        device=DEVICE,
        verbose=False,
    )[0]

    crops, keep = [], []
    if r.boxes is not None and r.boxes.id is not None:
        ids = r.boxes.id.int().cpu().tolist()
        boxes = r.boxes.xyxy.cpu().numpy()
        for tid, (x1, y1, x2, y2) in zip(ids, boxes):
            bw, bh = x2 - x1, y2 - y1
            if min(bw, bh) < min_side:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            a = int(max(0, cx - bw / 2 * (1 + PAD)))
            b = int(max(0, cy - bh / 2 * (1 + PAD)))
            c = int(min(W, cx + bw / 2 * (1 + PAD)))
            d = int(min(H, cy + bh / 2 * (1 + PAD)))
            crop = frame[b:d, a:c]
            if crop.size == 0:
                continue
            crops.append(crop)
            keep.append((tid, int(x1), int(y1), int(x2), int(y2)))

    # ---- Model 2: ambulance classifier on every crop ----
    ps = []
    if crops:
        ps = [
            rr.probs.data[AMB].item()
            for rr in classifier.predict(crops, imgsz=CLS_IMGSZ, device=DEVICE, verbose=False)
        ]

    # ---- Voting rule ----
    for (tid, x1, y1, x2, y2), p in zip(keep, ps):
        st.probs[tid].append(p)
        st.votes[tid].append(int(p >= TH_FRAME))
        st.centers[tid].append(((x1 + x2) / 2, (y1 + y2) / 2))

        n_votes = sum(st.votes[tid])
        (xa, ya), (xb, yb) = st.centers[tid][0], st.centers[tid][-1]
        moved = math.hypot(xb - xa, yb - ya)

        if (
            tid not in st.active
            and n_votes >= K
            and np.mean(st.probs[tid][-M:]) >= MEAN_MIN
            and moved >= MIN_MOVE * W
        ):
            st.active.add(tid)

            if tid not in st.confirmed:
                st.confirmed.add(tid)
                now = time.time()
                if now - st.last_alert >= ALERT_COOLDOWN_SECONDS:
                    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                    print(
                        f"[ALERT] Ambulance detected "
                        f"---- Direction: {direction} "
                        f"---- Track ID: {tid} "
                        f"---- Time: {ts} "
                        f"---- Confidence: {p:.2f}"
                    )
                    st.last_alert = now

        elif tid in st.active and n_votes <= RELEASE:
            st.active.discard(tid)

        if tid in st.active:
            color, label = (0, 0, 255), f"AMBULANCE id{tid} p{p:.2f}"
        elif n_votes > 0:
            color, label = (0, 255, 255), f"? id{tid} p{p:.2f}"
        else:
            color, label = (0, 200, 0), f"id{tid} p{p:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)
        cv2.putText(frame, label, (x1, max(y1 - 6, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thick)

    # ---- Direction banner ----
    banner_color = (0, 0, 255) if st.active else (60, 60, 60)
    banner = f"{direction}" + ("  -  AMBULANCE" if st.active else "")
    cv2.rectangle(frame, (0, 0), (int(W * 0.35), int(60 * font_scale) + 10), banner_color, -1)
    cv2.putText(frame, banner, (10, int(45 * font_scale) + 5),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2, (255, 255, 255), thick)
    return frame


# ============================================================
# 5. MAIN LOOP
# ============================================================

try:
    while True:
        active_videos = 0

        for direction, cap in caps.items():
            ok, frame = cap.read()
            if not ok:
                continue
            active_videos += 1

            annotated = process_frame(direction, frame)
            cv2.imshow(f"{direction} Traffic", annotated)

        if active_videos == 0:
            print("All videos have finished.")
            break

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Detection stopped by user.")
            break

finally:
    for cap in caps.values():
        cap.release()
    cv2.destroyAllWindows()

    print("-" * 60)
    for d, st in states.items():
        print(f"{d}: confirmed ambulance tracks = {len(st.confirmed)}")
    print("All video resources released.")