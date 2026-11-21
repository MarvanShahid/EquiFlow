"""Summarise an event log (backend/logs/events_*.csv, or one written by run_equiflow.py --event-log)
into one row per preemption episode: detection -> green -> end -> recovery.

    python scripts/preempt_report.py logs/events_20261115_120000.csv
    python scripts/preempt_report.py logs/events_*.csv --out logs/episodes.csv
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.eventlog import episodes, read_log, write_episodes  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--out", help="write the episode table here (default: next to each log)")
    a = ap.parse_args()
    allep = []
    for f in a.logs:
        eps = episodes(read_log(f))
        allep += eps
        if not a.out:
            dst = Path(f).with_name(Path(f).name.replace("events_", "episodes_", 1))
            if dst == Path(f):
                dst = Path(f).with_suffix(".episodes.csv")
            write_episodes(eps, dst)
    if a.out:
        write_episodes(allep, a.out)
    done = [e for e in allep if e["completed"]]
    lat = [e["detection_to_green_s"] for e in done if e["detection_to_green_s"] is not None]
    dur = [float(e["preempt_duration_s"]) for e in done if e["preempt_duration_s"] is not None]
    print(f"preemptions        {len(allep)}")
    print(f"completed          {len(done)}")
    print(f"ended by timeout   {sum(e['ended_reason'] == 'timeout' for e in allep)}")
    print(f"with recovery      {sum(bool(e['recovery_greens']) for e in done)}")
    by = {}
    for e in allep:
        by[e["trigger"]] = by.get(e["trigger"], 0) + 1
    print("triggers           " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
    if lat:
        print(f"detection->green   mean {statistics.mean(lat):.2f} s, max {max(lat):.2f} s")
    if dur:
        print(f"priority held      mean {statistics.mean(dur):.1f} s, max {max(dur):.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
