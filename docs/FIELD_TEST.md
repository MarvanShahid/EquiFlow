# Field test procedure (live traffic, shadow mode)

EquiFlow has only been evaluated in simulation and on recorded clips. This is the procedure for the first test on
live traffic. It runs in **shadow mode**: the system watches a real junction and logs what it would do, but it
**never controls a signal**. Controlling real signals is a separate, later step that needs the traffic authority
(see [DEPLOYMENT.md](DEPLOYMENT.md), "Signal hardware").

## 1. Before going out

- **Permission.** Written permission from the traffic authority / junction owner to mount or point a camera at
  the junction, and from the land owner where the camera stands. Do not stand in the carriageway.
- **Privacy.** The pipeline stores only vehicle boxes and counts, but the optional annotated video shows people
  and number plates: record it only if the permission covers it, keep it on an encrypted disk, delete it after
  labelling (keep `events.csv` and `frames.csv`), and never publish it. Use `--no-video` if in doubt.
- **Camera.** A fixed view of one approach, high enough to see 60-100 m of queue, the stop line in view, no
  backlight. 1080p at 25-30 fps is enough. An IP camera (RTSP) or a phone with an IP-camera app on the same
  network works; note its address.
- **Laptop.** The GPU laptop, on mains power (on battery the detector ran about 2x slower), with
  `backend/config.live.yaml` set to `device: 0`. Check the pipeline runs: `python Projects/gpu_compat.py`, then a
  short recorded clip with `field_record.py` (median about 27 ms per frame on the RTX 4050).
- **Calibration (for queue lengths).** Measure on site, or take from road-marking standards: lane width and the
  dash length + gap of the lane markings. Pick four points on the road surface whose ground positions you know
  (e.g. the corners of a lane between two dashes) and run `Projects/calibrate_lanes.py` on a frame from the
  camera; check the overlay with `--check` (the 5 m grid must line up with the dashes).

## 2. Recording

```
cd Projects
python field_record.py rtsp://<camera-address>/stream --name <junction>_<approach>_<date> --minutes 30 \
    --intersection J1 --approach North
```

- Record at least **2 hours per approach**, over several days and times (peak / off-peak, day / dusk), so that
  some real ambulance passes are included. Ambulances are rare: plan for many hours in total.
- Alongside, keep a **manual log**: the time of every ambulance that actually passes (with or without siren),
  and of any white van / rescue vehicle that could be mistaken for one. A second person with a phone stopwatch is
  enough; the recording's `session.json` gives its start time.
- For queue validation, count by hand the queued vehicles (and the queue end, using the road markings) in each
  lane at the end of several red phases, and note the time.

## 3. Scoring

1. Add the labelled ambulance passes to `Projects/ground_truth.csv` (`<name>,start_s,end_s`; sessions without
   an ambulance get one empty row) and run `python Projects/score_tracking.py`: detected passes, misses, false
   confirmations and confirmation latency, the same measures as on the recorded clips.
2. Queue validation: compare `frames.csv` (per-lane `queued` and `queue_m`) at the noted times with the hand
   counts: mean absolute error in vehicles and in metres per lane.
3. Shadow control: replay the session through the controller (`frames.csv` gives the counts per time; the
   ambulance confirmations come from `events.csv`) and compare the priority it would have given with what the
   real signal did.

## 4. What counts as a pass (proposed acceptance criteria)

| Measure | Target |
|---|---|
| Real ambulance passes confirmed | at least 90%, confirmation within 3 s of it entering the view |
| False confirmations | at most 1 per camera-hour |
| Lane queue count | mean absolute error at most 1 vehicle per lane |
| Lane queue length | mean absolute error at most 5 m |
| Pipeline speed | at least 15 frames per second per approach |

These are the thresholds above which the simulation results (Section 5 of RESULTS.md: no false priority up to
10% false frames) are expected to carry over. A failed criterion is a finding, not a reason to stop: record it
in the failure analysis.

## 5. After the test

Before any real control: hardware-in-the-loop with the actual signal controller on a bench, the cabinet's own
conflict monitor in place, and the authority's approval. EquiFlow's software conflict monitor
(`backend/app/signals/`) adds to the cabinet's, it never replaces it.
