"""Tests the voting logic of DirectionTracker with stand-in models (no ultralytics / weights needed)."""
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SCRIPT = {"p": [], "boxes": []}  # per-frame classifier probability and vehicle box


class _T:
    def __init__(self, a): self.a = np.array(a)
    def int(self): return self
    def cpu(self): return self
    def tolist(self): return self.a.tolist()
    def numpy(self): return self.a


class _V:
    def __init__(self, v): self.v = v
    def item(self): return self.v


class FakeYOLO:
    def __init__(self, path):
        self.is_cls = "cls" in path
        self.names = {0: "ambulance", 1: "other_vehicle"} if self.is_cls else {2: "car"}
        self.predictor = None
        self.frame = -1

    def track(self, **kw):
        self.frame += 1
        box = SCRIPT["boxes"][min(self.frame, len(SCRIPT["boxes"]) - 1)]
        return [types.SimpleNamespace(boxes=types.SimpleNamespace(id=_T([7]), xyxy=_T([box])))]

    def predict(self, crops, **kw):
        p = SCRIPT["p"][min(self.cls_calls, len(SCRIPT["p"]) - 1)]
        self.cls_calls += 1
        return [types.SimpleNamespace(probs=types.SimpleNamespace(data=[_V(p), _V(1 - p)])) for _ in crops]
    cls_calls = 0


sys.modules["ultralytics"] = types.SimpleNamespace(YOLO=FakeYOLO)

from app.config import VisionCfg  # noqa: E402
from app.vision.live import DirectionTracker, SharedClassifier  # noqa: E402


def run(ps, boxes, zone=None, lanes=None, calibration=None, **cfg):
    SCRIPT["p"], SCRIPT["boxes"] = ps, boxes
    c = VisionCfg(cls_weights="cls.pt", det_weights="det.pt", **cfg)
    cl = SharedClassifier(c)
    cl.model.cls_calls = 0
    tr = DirectionTracker(c, cl, zone=zone, lanes=lanes, calibration=calibration)
    out = []
    for _ in range(len(ps)):
        frame = np.zeros((360, 640, 3), np.uint8)
        out.append(tr.process(frame))
    return out


MOVING = [(100 + 10 * i, 100, 160 + 10 * i, 160) for i in range(60)]
STILL = [(100, 100, 160, 160)]


def test_confirms_after_k_votes_and_releases():
    res = run([0.9] * 10 + [0.1] * 12, MOVING)
    first = next(i for i, r in enumerate(res) if r.new_confirmed)
    assert first == 4                      # 5th positive frame (K=5)
    assert res[first].ambulances and res[first].ambulances[0].track_id == 7
    assert sum(len(r.new_confirmed) for r in res) == 1   # only reported once
    assert res[9].ambulances                # still active while evidence is high
    assert not res[-1].ambulances           # released after the evidence fades
    assert all(r.vehicles == 1 for r in res)


def test_single_frame_spike_is_ignored():
    res = run([0.05, 0.95, 0.05, 0.05, 0.9, 0.05, 0.05, 0.05, 0.05, 0.05], MOVING)
    assert not any(r.new_confirmed for r in res)


def test_stationary_filter():
    res = run([0.95] * 12, STILL, min_move=0.01)
    assert not any(r.new_confirmed for r in res)
    res = run([0.95] * 12, STILL, min_move=0.0)
    assert any(r.new_confirmed for r in res)


LEFT_HALF = [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]       # x < 320 px of the 640 px test frame


def test_fr04_zone_counts_only_vehicles_inside_and_queue_only_stationary_ones():
    still_in = run([0.1] * 8, STILL, zone=LEFT_HALF)       # box bottom-centre (130, 160): inside, not moving
    assert all(r.vehicles == 1 for r in still_in)
    assert still_in[-1].queue == 1
    outside = run([0.1] * 8, [(400, 100, 460, 160)], zone=LEFT_HALF)
    assert all(r.vehicles == 0 and r.queue == 0 for r in outside)
    moving_in = run([0.1] * 8, MOVING, zone=LEFT_HALF)     # 10 px per frame > 0.004 * 640
    assert moving_in[-1].vehicles == 1 and moving_in[-1].queue == 0
    no_zone = run([0.1] * 3, [(400, 100, 460, 160)])
    assert no_zone[-1].vehicles == 1 and no_zone[-1].queue is None    # old behaviour without a zone



# calibrated lane-level queues: two lanes side by side, stop line at the bottom of the 640x360 frame,
# calibration: the frame covers 7 m (x) by 36 m (y) of road, viewed from straight above
LANES = [{"id": "L1", "polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]], "stop_line": [[0, 1], [0.5, 1]]},
         {"id": "L2", "polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]], "stop_line": [[0.5, 1], [1, 1]]}]
CAL = {"image": [[0, 0], [1, 0], [1, 1], [0, 1]], "world": [[0, 36], [7, 36], [7, 0], [0, 0]]}


def test_lanes_report_vehicles_queue_and_queue_length_in_metres():
    res = run([0.1] * 8, STILL, lanes=LANES, calibration=CAL)    # bottom-centre (130, 160): lane L1, y = 160/360
    lanes = res[-1].lanes
    assert lanes["L1"]["vehicles"] == 1 and lanes["L1"]["queued"] == 1
    assert lanes["L2"] == {"vehicles": 0, "queued": 0, "queue_m": 0.0}
    expect = 36 * (1 - 160 / 360) + 2.5                          # metres from the stop line + half a vehicle
    assert abs(lanes["L1"]["queue_m"] - expect) < 0.2, lanes
    assert res[-1].vehicles == 1 and res[-1].queue == 1         # no zone: the lanes are the approach
    moving = run([0.1] * 8, MOVING, lanes=LANES, calibration=CAL)
    assert moving[-1].lanes["L1"]["queued"] + moving[-1].lanes["L2"]["queued"] == 0


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except Exception as e:  # noqa: BLE001
                import traceback; traceback.print_exc(); fails += 1; print("FAIL", name, "->", repr(e))
    sys.exit(1 if fails else 0)
