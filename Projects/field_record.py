"""field_record.py - record a field session with the live pipeline (shadow mode: nothing controls a signal).

Runs exactly the backend's live vision (YOLO26s + ByteTrack + classifier + vote, settings from
backend/config.live.yaml, lanes/calibration from an intersection there if given) on a camera or a video, and
writes everything needed to score it afterwards:

  tracking_out/<name>/events.csv     confirmed ambulances, same format as track_pipeline.py -> score_tracking.py
  tracking_out/<name>/frames.csv     per processed frame: time, vehicles, queue, per-lane queue / metres, fps
  tracking_out/<name>/tracked.mp4    annotated video (optional, --no-video to skip)
  tracking_out/<name>/session.json   source, start time, settings, software versions

    python field_record.py rtsp://user:pass@192.168.1.20/stream1 --name junctionA_north --minutes 30
    python field_record.py 0 --name window_test --minutes 5            # webcam 0
    python field_record.py videos/test1.mp4 --name smoke --minutes 0.2  # a file (stops at its end)
    python field_record.py ... --intersection J1 --approach North       # use that approach's lanes/calibration

Afterwards: label the real ambulance passes (start_s, end_s) in ground_truth.csv under <name> and run
score_tracking.py. See docs/FIELD_TEST.md for the full procedure (permissions, privacy, what to record).
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
import gpu_compat  # noqa: E402,F401  (blocked torchvision CUDA ops / lap: see gpu_compat.py)
from app.config import load_config  # noqa: E402
from app.vision.live import DirectionTracker, SharedClassifier  # noqa: E402

EVENT_FIELDS = ["track_id", "first_vote_frame", "confirm_frame", "confirm_time_s", "delay_s",
                "mean_p", "max_p", "dx", "dy", "heading_deg"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="rtsp:// or http:// URL, webcam index, or a video file")
    ap.add_argument("--name", required=True, help="session name (folder under tracking_out/)")
    ap.add_argument("--minutes", type=float, default=10.0, help="stop after this long (a file also stops at its end)")
    ap.add_argument("--config", default=str(HERE.parent / "backend" / "config.live.yaml"))
    ap.add_argument("--intersection", help="intersection id in the config whose lanes/calibration to use")
    ap.add_argument("--approach", default="North")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()

    cfg = load_config(a.config)
    v = cfg.vision
    icfg = next((i for i in cfg.intersections if i.id == a.intersection), None) if a.intersection else None
    lanes = icfg.lanes.get(a.approach) if icfg else None
    cal = icfg.calibration.get(a.approach) if icfg else None
    zone = icfg.zones.get(a.approach) if icfg else None
    tracker = DirectionTracker(v, SharedClassifier(v), zone=zone, lanes=lanes, calibration=cal)

    src = int(a.source) if a.source.isdigit() else a.source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"cannot open {a.source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    is_file = isinstance(src, str) and Path(src).exists()
    out = HERE / "tracking_out" / a.name
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat(timespec="seconds")
    (out / "session.json").write_text(json.dumps({
        "source": a.source if "@" not in str(a.source) else str(a.source).split("@")[-1],   # never store passwords
        "started": started, "minutes": a.minutes, "config": a.config, "intersection": a.intersection,
        "approach": a.approach, "lanes": bool(lanes), "calibrated": bool(cal),
        "vote": {"k": v.k, "m": v.m, "th_frame": v.th_frame, "mean_min": v.mean_min}, "cls_weights": v.cls_weights,
        "python": platform.python_version(), "platform": platform.platform()}, indent=2), encoding="utf-8")

    writer = None
    events, rows = [], []
    t0, n = time.monotonic(), 0
    deadline = t0 + a.minutes * 60
    try:
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok:
                if is_file:
                    break
                time.sleep(0.5)                           # a live stream hiccup: keep trying until the deadline
                continue
            n += 1
            t_rel = n / fps if is_file else time.monotonic() - t0
            t1 = time.perf_counter()
            res = tracker.process(frame)
            dt = time.perf_counter() - t1
            for d in res.new_confirmed:
                events.append({"track_id": d.track_id, "first_vote_frame": "", "confirm_frame": n,
                               "confirm_time_s": round(t_rel, 2), "delay_s": "", "mean_p": round(d.confidence, 3),
                               "max_p": "", "dx": "", "dy": "", "heading_deg": ""})
                print(f"  ambulance confirmed at {t_rel:.1f} s (track {d.track_id}, p {d.confidence:.2f})")
            rows.append({"frame": n, "t_s": round(t_rel, 2), "vehicles": res.vehicles, "queue": res.queue,
                         "lanes": json.dumps(res.lanes) if res.lanes else "", "ms": round(1000 * dt, 1)})
            if not a.no_video:
                if writer is None:
                    h, w = frame.shape[:2]
                    writer = cv2.VideoWriter(str(out / "tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                writer.write(res.annotated if res.annotated is not None else frame)
    except KeyboardInterrupt:
        print("stopped by user")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
    with open(out / "events.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EVENT_FIELDS)
        w.writeheader()
        w.writerows(events)
    with open(out / "frames.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["frame", "t_s", "vehicles", "queue", "lanes", "ms"])
        w.writeheader()
        w.writerows(rows)
    ms = sorted(r["ms"] for r in rows) or [0]
    print(f"{a.name}: {n} frames, {len(events)} ambulance confirmations, median {ms[len(ms) // 2]} ms per frame "
          f"-> {out}")


if __name__ == "__main__":
    main()
