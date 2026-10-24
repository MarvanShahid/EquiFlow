import csv, math
from collections import defaultdict, deque
from pathlib import Path
import cv2, numpy as np
from ultralytics import YOLO

WEIGHTS = r"C:\Smester7\Projects\runs\v0\weights\best.pt"
VIDEO   = r"C:\Smester7\Projects\videos\test8.mp4"
OUT_DIR = Path(r"C:\Smester7\Projects\tracking_out"); OUT_DIR.mkdir(exist_ok=True)

AMB_CONF = 0.35    
M, K = 8, 4       
ZONES = {}         

def zone_of(pt):
    for name, poly in ZONES.items():
        if cv2.pointPolygonTest(np.array(poly, np.int32), pt, False) >= 0:
            return name
    return "unknown"

if __name__ == "__main__":
    model = YOLO(WEIGHTS)
    cap = cv2.VideoCapture(VIDEO)
    if not cap.isOpened():
        raise SystemExit("Video khul nahi rahi: VIDEO ka path check karo")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    writer = cv2.VideoWriter(str(OUT_DIR / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    if not writer.isOpened():
        raise SystemExit("Output video nahi ban sakti")

    votes = defaultdict(lambda: deque(maxlen=M))
    centers = defaultdict(lambda: deque(maxlen=15))
    confs = defaultdict(list)
    first_seen, confirmed, events = {}, {}, []

    stream = model.track(source=VIDEO, tracker="bytetrack.yaml", persist=True, stream=True,
                         conf=0.25, imgsz=640, device=0, verbose=False)
    for f, r in enumerate(stream):
        frame = r.orig_img.copy()
        if r.boxes is not None and r.boxes.id is not None:
            rows = zip(r.boxes.xyxy.cpu().numpy(), r.boxes.id.int().cpu().tolist(),
                       r.boxes.cls.int().cpu().tolist(), r.boxes.conf.cpu().tolist())
            for box, tid, cls, cf in rows:
                x1, y1, x2, y2 = map(int, box)
                is_amb = int(cls == 0 and cf >= AMB_CONF)
                votes[tid].append(is_amb)
                centers[tid].append(((x1 + x2) / 2, (y1 + y2) / 2))
                if is_amb:
                    first_seen.setdefault(tid, f)
                    confs[tid].append(cf)
                if tid not in confirmed and sum(votes[tid]) >= K:
                    confirmed[tid] = f
                    (xa, ya), (xb, yb) = centers[tid][0], centers[tid][-1]
                    events.append({
                        "track_id": tid, "first_frame": first_seen[tid], "confirm_frame": f,
                        "confirm_time_s": round(f / fps, 2),
                        "delay_s": round((f - first_seen[tid]) / fps, 2),
                        "zone": zone_of(centers[tid][-1]),
                        "dx": round(xb - xa, 1), "dy": round(yb - ya, 1),
                        "heading_deg": round(math.degrees(math.atan2(yb - ya, xb - xa)), 1),
                        "mean_conf": round(float(np.mean(confs[tid])), 3),
                    })
                if tid in confirmed:
                    color, label = (0, 0, 255), f"AMBULANCE id{tid}"       # laal: confirmed
                elif sum(votes[tid]) > 0:
                    color, label = (0, 255, 255), f"? id{tid}"             # peela: shak
                else:
                    color, label = (0, 200, 0), f"id{tid} {r.names[cls]}"  # hara: baqi
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, max(y1 - 6, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        writer.write(frame)

    writer.release()
    if events:
        with open(OUT_DIR / "events.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=events[0].keys())
            w.writeheader(); w.writerows(events)
    print("confirmed ambulance tracks:", len(confirmed))
    for e in events:
        print(e)
    print("saved:", OUT_DIR)