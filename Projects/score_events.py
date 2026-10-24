import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\Smester7\Projects\tracking_out")
GT = Path(r"C:\Smester7\Projects\ground_truth.csv")
MARGIN = 1.0     # window ke khatam hone ke itne second baad tak ka confirm bhi theek maante hain

gt = defaultdict(list)
for r in csv.DictReader(open(GT)):
    gt[r["video"]].append((float(r["start_s"]), float(r["end_s"])))

names = sorted(set(gt) | {p.parent.name for p in ROOT.glob("*/events.csv")})
for video in names:
    ev = ROOT / video / "events.csv"
    times = [float(e["confirm_time_s"]) for e in csv.DictReader(open(ev))] if ev.exists() else []
    used, detected, lat = set(), 0, []
    for s, e in gt.get(video, []):
        hits = [t for t in times if s <= t <= e + MARGIN]
        if hits:
            detected += 1; used.update(hits); lat.append(min(hits) - s)
    false_events = [t for t in times if t not in used]
    n = len(gt.get(video, []))
    print(f"{video}: ambulance passes {n} | detected {detected} | missed {n - detected} | "
          f"false events {len(false_events)} {false_events}")
    if lat:
        print("   confirm kitni der baad (window shuru se, second):", [round(x, 2) for x in lat])