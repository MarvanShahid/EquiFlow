"""score_tracking.py - score the tracking pipeline (track_pipeline.py) on the real Islamabad videos.

For every video in ground_truth.csv it compares the confirmed ambulance events in
tracking_out/<video>/events.csv with the hand-labelled ambulance windows (start_s, end_s):

  * an ambulance pass counts as detected if a confirmation falls inside its window
    (from pre_margin seconds before the start to post_margin seconds after the end)
  * every other confirmation is a false event
  * latency = first confirmation inside the window - window start

Videos without a tracking_out/<video>/events.csv were not processed and are listed as such
(they are NOT counted as clean). Run track_pipeline.py on them first.

    python score_tracking.py                     # -> tracking_out/tracking_scores.csv, tracking_scores.md
    python score_tracking.py --pre-margin 0      # strict: no early confirmations allowed
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# which split each local video's crops went into (build_crops.py LOCAL_SPLIT); videos with ambulances
# were not used for crops at all
VIDEO_ROLE = {"test6": "train", "test7": "train", "test8": "train", "test9": "val", "test11": "test",
              "v1": "train", "v2": "train"}


def load_gt(path: Path) -> dict[str, list[tuple[float, float]]]:
    gt: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            gt[r["video"]]
            if r["start_s"].strip() and r["end_s"].strip():
                gt[r["video"]].append((float(r["start_s"]), float(r["end_s"])))
    return gt


def score(gt, root: Path, pre: float, post: float):
    rows = []
    for video in sorted(set(gt) | {p.parent.name for p in root.glob("*/events.csv")}):
        ev = root / video / "events.csv"
        processed = ev.exists()
        times = sorted(float(e["confirm_time_s"]) for e in csv.DictReader(open(ev))) if processed else []
        windows = gt.get(video, [])
        used, lat = set(), []
        detected = 0
        for s, e in windows:
            hits = [t for t in times if s - pre <= t <= e + post]
            if hits:
                detected += 1
                used.update(hits)
                lat.append(max(0.0, min(hits) - s))
        false = [t for t in times if t not in used]
        rows.append({"video": video, "processed": processed, "used_for_training_crops": VIDEO_ROLE.get(video, "no"),
                     "ambulance_passes": len(windows), "detected": detected if processed else "",
                     "missed": (len(windows) - detected) if processed else "",
                     "false_events": len(false) if processed else "",
                     "false_event_times_s": " ".join(f"{t:g}" for t in false),
                     "latency_s": " ".join(f"{x:.2f}" for x in lat)})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default=str(HERE / "ground_truth.csv"))
    ap.add_argument("--root", default=str(HERE / "tracking_out"))
    ap.add_argument("--pre-margin", type=float, default=1.0, help="accept a confirmation this early (labels are hand-timed)")
    ap.add_argument("--post-margin", type=float, default=1.0)
    a = ap.parse_args()
    root = Path(a.root)
    gt = load_gt(Path(a.gt))
    rows = score(gt, root, a.pre_margin, a.post_margin)
    strict = {r["video"]: r for r in score(gt, root, 0.0, a.post_margin)}
    with open(root / "tracking_scores.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    done = [r for r in rows if r["processed"]]
    passes = sum(r["ambulance_passes"] for r in done)
    det = sum(r["detected"] for r in done)
    false = sum(r["false_events"] for r in done)
    lat = [float(x) for r in done for x in r["latency_s"].split()]
    s_det = sum(strict[r["video"]]["detected"] for r in done)
    clean = [r for r in done if r["ambulance_passes"] == 0]
    L = ["# Tracking pipeline on the Islamabad videos", "",
         f"Ground truth: `{Path(a.gt).name}`. A pass is detected if a confirmation falls between "
         f"{a.pre_margin:g} s before and {a.post_margin:g} s after its labelled window.", "",
         "| Video | processed | crops from this video in | ambulance passes | detected | missed | false events | latency (s) |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['video']} | {'yes' if r['processed'] else '**no**'} | {r['used_for_training_crops']} | "
                 f"{r['ambulance_passes']} | {r['detected']} | {r['missed']} | {r['false_events']}"
                 f"{' (' + r['false_event_times_s'] + ')' if r['false_event_times_s'] else ''} | {r['latency_s']} |")
    L += ["", f"**Processed videos: {len(done)} of {len(rows)}.** Ambulance passes detected: {det} of {passes}"
          + (f" ({100 * det / passes:.0f}%)" if passes else "")
          + f"; strict (no early confirmation): {s_det} of {passes}.",
          f"False events: {false} in {len(done)} processed videos; {sum(r['false_events'] for r in clean)} of them "
          f"in the {len(clean)} processed videos that contain no ambulance."]
    if lat:
        L.append(f"Confirmation latency after the window starts: mean {statistics.mean(lat):.2f} s, max {max(lat):.2f} s.")
    missing = [r["video"] for r in rows if not r["processed"]]
    if missing:
        L.append(f"Not processed yet (run `python track_pipeline.py {' '.join(missing)}`): {', '.join(missing)}.")
    trained = [r["video"] for r in done if r["used_for_training_crops"] == "train"]
    if trained:
        L.append(f"Note: crops from {', '.join(trained)} were used to train the classifier, so results on them are optimistic.")
    (root / "tracking_scores.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
