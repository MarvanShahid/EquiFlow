
import csv, math, sys
from collections import defaultdict, deque
from pathlib import Path
import cv2, numpy as np
from ultralytics import YOLO

DET_WEIGHTS = "yolo26s.pt"
CLS_WEIGHTS = r"C:\Smester7\Projects\runs\cls_v4-2\weights\best.pt"
VIDEO_DIR = Path(r"C:\Smester7\Projects\videos")
OUT_ROOT = Path(r"C:\Smester7\Projects\tracking_out")
IMGSZ = 1280
TH_FRAME = 0.6
M, K = 8, 5
PAD, MIN_SIDE = 0.12, 20
OUT_W = 1920
MEAN_MIN = 0.65
RELEASE = 1

cls = YOLO(CLS_WEIGHTS)
AMB = next(k for k, v in cls.names.items() if v == "ambulance")

MIN_MOVE = 0.00

from ultralytics.trackers.basetrack import BaseTrack


def run(name):
    BaseTrack.reset_id()
    paths = list(VIDEO_DIR.glob(name + ".*"))

    if not paths:
        print("VIDEO NOT Found:", name)
        return

    video = str(paths[0])
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    out_h = int(H * OUT_W / W)
    out = OUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)

    writer = cv2.VideoWriter(
        str(out / "tracked.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (OUT_W, out_h)
    )

    T, FS, min_side = max(3, W // 600), max(0.8, W / 1800), MIN_SIDE * W / 1920

    det = YOLO(DET_WEIGHTS)
    votes = defaultdict(lambda: deque(maxlen=M))
    probs = defaultdict(list)
    centers = defaultdict(lambda: deque(maxlen=15))
    first_vote, confirmed, events = {}, {}, []
    active = set()
    f = -1

    stream = det.track(
        source=video,
        tracker="bytetrack.yaml",
        persist=True,
        stream=True,
        imgsz=IMGSZ,
        conf=0.35,
        classes=[2, 3, 5, 7],
        device=0,
        verbose=False
    )

    for f, r in enumerate(stream):
        frame = r.orig_img.copy()
        crops, keep = [], []

        if r.boxes is not None and r.boxes.id is not None:
            for tid, (x1, y1, x2, y2) in zip(
                r.boxes.id.int().cpu().tolist(),
                r.boxes.xyxy.cpu().numpy()
            ):
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

        ps = [
            rr.probs.data[AMB].item()
            for rr in cls.predict(crops, imgsz=96, device=0, verbose=False)
        ] if crops else []

        for (tid, x1, y1, x2, y2), p in zip(keep, ps):
            probs[tid].append(p)
            is_amb = int(p >= TH_FRAME)
            votes[tid].append(is_amb)
            centers[tid].append(((x1 + x2) / 2, (y1 + y2) / 2))

            if is_amb:
                first_vote.setdefault(tid, f)

            n_votes = sum(votes[tid])
            (xa, ya), (xb, yb) = centers[tid][0], centers[tid][-1]
            moved = math.hypot(xb - xa, yb - ya)

            if (
                tid not in active
                and n_votes >= K
                and np.mean(probs[tid][-M:]) >= MEAN_MIN
                and moved >= MIN_MOVE * W
            ):
                active.add(tid)

                if tid not in confirmed:
                    confirmed[tid] = f
                    (xa, ya), (xb, yb) = centers[tid][0], centers[tid][-1]

                    events.append({
                        "track_id": tid,
                        "first_vote_frame": first_vote[tid],
                        "confirm_frame": f,
                        "confirm_time_s": round(f / fps, 2),
                        "delay_s": round((f - first_vote[tid]) / fps, 2),
                        "mean_p": round(float(np.mean(probs[tid])), 3),
                        "max_p": round(float(np.max(probs[tid])), 3),
                        "dx": round(xb - xa, 1),
                        "dy": round(yb - ya, 1),
                        "heading_deg": round(
                            math.degrees(math.atan2(yb - ya, xb - xa)), 1
                        )
                    })

            elif tid in active and n_votes <= RELEASE:
                active.discard(tid)

            if tid in active:
                color, label = (0, 0, 255), f"AMBULANCE id{tid} p{p:.2f}"
            elif sum(votes[tid]) > 0:
                color, label = (0, 255, 255), f"? id{tid} p{p:.2f}"
            else:
                color, label = (0, 200, 0), f"id{tid} p{p:.2f}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, T)
            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 6, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                FS,
                color,
                T
            )

        writer.write(cv2.resize(frame, (OUT_W, out_h)))

    writer.release()

    if events:
        with open(out / "events.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=events[0].keys())
            w.writeheader()
            w.writerows(events)

    print(
        f"{name}: {f + 1} frames ({(f + 1) / fps:.1f}s) | "
        f"confirmed ambulance tracks: {len(confirmed)} | "
        f"confirm times (s): {[e['confirm_time_s'] for e in events]}"
    )


if __name__ == "__main__":
    for n in (sys.argv[1:] or ["test12"]):
        run(n)
