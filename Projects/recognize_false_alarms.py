import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\Smester7\Projects\tracking_out")   # one subfolder per video, each with events.csv
GT = Path(r"C:\Smester7\Projects\ground_truth.csv")  # columns: video,start_s,end_s
MARGIN = 1.0  # a confirmation up to this many seconds after the window ends still counts as a hit

# Load ground truth: video -> list of (start, end) ambulance windows
gt = defaultdict(list)
with open(GT, newline="", encoding="utf-8-sig") as f:   # utf-8-sig strips the BOM that Excel adds
    for r in csv.DictReader(f):
        gt[r["video"]]  # touch the key so videos with no ambulance still get an (empty) entry
        if r["start_s"].strip() and r["end_s"].strip():  # skip rows with blank start/end
            gt[r["video"]].append((float(r["start_s"]), float(r["end_s"])))

# Evaluate every video that appears in the ground truth or has an output folder
names = sorted(set(gt) | {p.parent.name for p in ROOT.glob("*/events.csv")})
for video in names:
    ev = ROOT / video / "events.csv"
    # Confirmation timestamps produced by the tracker (empty if the video has no events file)
    times = [float(e["confirm_time_s"]) for e in csv.DictReader(open(ev))] if ev.exists() else []

    used, detected, lat = set(), 0, []
    for s, e in gt.get(video, []):
        # Confirmations that fall inside this ambulance window (plus margin)
        hits = [t for t in times if s <= t <= e + MARGIN]
        if hits:
            detected += 1
            used.update(hits)               # mark these confirmations as explained by a real pass
            lat.append(min(hits) - s)       # latency = earliest confirmation minus window start

    # Any confirmation not matched to a ground-truth window is a false event
    false_events = [t for t in times if t not in used]
    n = len(gt.get(video, []))
    print(f"{video}: ambulance passes {n} | detected {detected} | missed {n - detected} | "
          f"false events {len(false_events)} {false_events}")
    if lat:
        print("   confirmation delay from window start (seconds):", [round(x, 2) for x in lat])