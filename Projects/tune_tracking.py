"""tune_tracking.py - re-tune the tracker's voting thresholds for a new classifier, without re-running video.

Step 1 (GPU, once per classifier): run detector + ByteTrack + classifier exactly as track_pipeline.py does
and record every track's ambulance probability per frame.
    python tune_tracking.py dump                    # -> tracking_out/tune/probs_<video>.csv
Step 2 (CPU, seconds): replay track_pipeline.py's voting rule for every setting in the grid and score each one
against ground_truth.csv with score_tracking.py's rule.
    python tune_tracking.py sweep                   # -> tracking_out/tune/sweep.csv, tune.md

Because the same few videos are used to choose and to score the setting, the sweep also runs
leave-one-video-out: for every video, the setting is chosen on the other videos only and scored on that one.
That total is the honest estimate; the best in-sample score is optimistic.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import math
import statistics
import gpu_compat  # noqa: F401  (see gpu_compat.py)
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "tracking_out" / "tune"

# the setting before re-tuning for cls_v5_img128 (Iteration 2); track_pipeline.py now uses k=3, mean_min=0.70
CURRENT = {"th_frame": 0.6, "mean_min": 0.65, "k": 5, "m": 8}
GRID = {"th_frame": [round(0.30 + 0.05 * i, 2) for i in range(10)],   # 0.30 .. 0.75
        "mean_min": [round(0.40 + 0.05 * i, 2) for i in range(9)],    # 0.40 .. 0.80
        "k": [3, 4, 5, 6],
        "m": [8]}


# ----------------------------------------------------------------------------- step 1: dump probabilities
def dump(videos: list[str]):
    import track_pipeline as tp  # loads the classifier the pipeline uses
    from ultralytics import YOLO
    from ultralytics.trackers.basetrack import BaseTrack
    import cv2

    OUT.mkdir(parents=True, exist_ok=True)
    for name in videos:
        paths = list(tp.VIDEO_DIR.glob(name + ".*"))
        if not paths:
            print("VIDEO NOT FOUND:", name)
            continue
        BaseTrack.reset_id()
        cap = cv2.VideoCapture(str(paths[0]))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        min_side = tp.MIN_SIDE * W / 1920
        det = YOLO(tp.DET_WEIGHTS)
        rows = []
        stream = det.track(source=str(paths[0]), tracker="bytetrack.yaml", persist=True, stream=True,
                           imgsz=tp.IMGSZ, conf=0.35, classes=[2, 3, 5, 7], device=0, verbose=False)
        for f, r in enumerate(stream):
            frame = r.orig_img
            crops, keep = [], []
            if r.boxes is not None and r.boxes.id is not None:
                for tid, (x1, y1, x2, y2) in zip(r.boxes.id.int().cpu().tolist(), r.boxes.xyxy.cpu().numpy()):
                    bw, bh = x2 - x1, y2 - y1
                    if min(bw, bh) < min_side:
                        continue
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    a = int(max(0, cx - bw / 2 * (1 + tp.PAD)))
                    b = int(max(0, cy - bh / 2 * (1 + tp.PAD)))
                    c = int(min(W, cx + bw / 2 * (1 + tp.PAD)))
                    d = int(min(H, cy + bh / 2 * (1 + tp.PAD)))
                    crop = frame[b:d, a:c]
                    if crop.size == 0:
                        continue
                    crops.append(crop)
                    keep.append((tid, cx, cy))
            ps = [rr.probs.data[tp.AMB].item()
                  for rr in tp.cls.predict(crops, imgsz=tp.CLS_IMGSZ, device=0, verbose=False)] if crops else []
            for (tid, cx, cy), p in zip(keep, ps):
                rows.append((f, tid, round(cx, 1), round(cy, 1), round(p, 5)))
        with open(OUT / f"probs_{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "track_id", "cx", "cy", "p", "fps", "width"])
            for row in rows:
                w.writerow(list(row) + [fps, W])
        print(f"{name}: {f + 1} frames, {len(rows)} track-frames")


# ----------------------------------------------------------------------------- step 2: replay + score
def load_probs(path: Path):
    tracks = defaultdict(list)
    fps = 25.0
    for r in csv.DictReader(open(path)):
        tracks[int(r["track_id"])].append((int(r["frame"]), float(r["p"])))
        fps = float(r["fps"])
    for v in tracks.values():
        v.sort()
    return tracks, fps


def replay(tracks, fps, th_frame, mean_min, k, m, release=1):
    """track_pipeline.py's rule (MIN_MOVE 0): confirm a track once when >= k of its last m frame votes are
    ambulance (p >= th_frame) and the mean p of its last m frames >= mean_min. Returns confirm times (s)."""
    times = []
    for seq in tracks.values():
        votes, probs, active, confirmed = deque(maxlen=m), [], False, False
        for f, p in seq:
            probs.append(p)
            votes.append(int(p >= th_frame))
            n = sum(votes)
            if not active and n >= k and statistics.fmean(probs[-m:]) >= mean_min:
                active = True
                if not confirmed:
                    confirmed = True
                    times.append(round(f / fps, 2))
            elif active and n <= release:
                active = False
    return sorted(times)


def score_video(times, windows, pre=1.0, post=1.0):
    used, lat, det = set(), [], 0
    for s, e in windows:
        hits = [t for t in times if s - pre <= t <= e + post]
        if hits:
            det += 1
            used.update(hits)
            lat.append(max(0.0, min(hits) - s))
    return det, len([t for t in times if t not in used]), lat


def key(res):
    """best = most passes detected, then fewest false events, then lowest mean latency"""
    det, false, lat = res
    return (-det, false, statistics.fmean(lat) if lat else 99.0)


def sweep():
    from score_tracking import load_gt
    gt = load_gt(HERE / "ground_truth.csv")
    data = {}
    for v in sorted(gt):
        p = OUT / f"probs_{v}.csv"
        if p.exists():
            data[v] = load_probs(p)
    missing = sorted(set(gt) - set(data))
    combos = [dict(zip(GRID, c)) for c in itertools.product(*GRID.values())]
    if CURRENT not in combos:
        combos.append(dict(CURRENT))

    # per (combo, video) results
    per = {}
    for ci, c in enumerate(combos):
        for v, (tracks, fps) in data.items():
            per[ci, v] = score_video(replay(tracks, fps, **c), gt[v])

    def total(ci, vids):
        det = sum(per[ci, v][0] for v in vids)
        false = sum(per[ci, v][1] for v in vids)
        lat = [x for v in vids for x in per[ci, v][2]]
        return det, false, lat

    vids = list(data)
    passes = sum(len(gt[v]) for v in vids)
    rows = []
    for ci, c in enumerate(combos):
        det, false, lat = total(ci, vids)
        rows.append({**c, "detected": det, "passes": passes, "false_events": false,
                     "mean_latency_s": round(statistics.fmean(lat), 2) if lat else ""})
    order = sorted(range(len(combos)), key=lambda ci: key(total(ci, vids)))
    best = order[0]
    cur = combos.index(CURRENT)

    # leave-one-video-out: choose on the other videos, score on the held-out one
    lovo_det = lovo_false = 0
    lovo_lat, picks = [], []
    for v in vids:
        rest = [u for u in vids if u != v]
        ci = min(range(len(combos)), key=lambda ci: key(total(ci, rest)))
        d, fa, la = per[ci, v]
        lovo_det += d
        lovo_false += fa
        lovo_lat += la
        picks.append((v, combos[ci], d, len(gt[v]), fa))

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "sweep.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows[ci] for ci in order)

    def line(name, c, res):
        det, false, lat = res
        ml = f"{statistics.fmean(lat):.2f}" if lat else ""
        return (f"| {name} | {c['th_frame']} | {c['mean_min']} | {c['k']}/{c['m']} | {det} of {passes} | {false} | {ml} |")

    L = ["# Re-tuning the tracker's voting thresholds", "",
         f"Videos: {', '.join(vids)}" + (f" (no probabilities for: {', '.join(missing)})" if missing else "") + ".",
         f"Grid: th_frame {GRID['th_frame'][0]}-{GRID['th_frame'][-1]}, mean_min {GRID['mean_min'][0]}-"
         f"{GRID['mean_min'][-1]}, k {GRID['k']} of m {GRID['m']}: {len(combos)} settings.", "",
         "| setting | th_frame | mean_min | k/m | passes detected | false events | mean latency (s) |",
         "|---|---|---|---|---|---|---|",
         line("current", CURRENT, total(cur, vids)),
         line("best in-sample", combos[best], total(best, vids))]
    for ci in order[1:6]:
        L.append(line("next best", combos[ci], total(ci, vids)))
    L += ["", f"**Leave-one-video-out** (setting chosen without the scored video): {lovo_det} of {passes} passes, "
              f"{lovo_false} false events"
              + (f", mean latency {statistics.fmean(lovo_lat):.2f} s" if lovo_lat else "") + ".", "",
          "| held-out video | setting chosen on the others (th_frame / mean_min / k) | detected | false |",
          "|---|---|---|---|"]
    for v, c, d, n, fa in picks:
        L.append(f"| {v} | {c['th_frame']} / {c['mean_min']} / {c['k']} | {d} of {n} | {fa} |")
    (OUT / "tune.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["dump", "sweep"])
    ap.add_argument("videos", nargs="*", help="dump: videos to process (default: all in ground_truth.csv)")
    a = ap.parse_args()
    if a.step == "dump":
        from score_tracking import load_gt
        dump(a.videos or sorted(load_gt(HERE / "ground_truth.csv")))
    else:
        sweep()


if __name__ == "__main__":
    main()
