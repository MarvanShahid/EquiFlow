"""Calibrated lane-level queues (app/vision/lanes.py): ground homography, lane membership, queue length in metres."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.vision.lanes import LaneModel, homography, to_world  # noqa: E402

# A straight two-lane road seen in perspective: the near edge (stop line) spans the image bottom, the far edge
# 40 m away is narrower near the top. Lanes 3.5 m wide each: road x = 0..7 m, y = 0 (stop line)..40 m.
IMAGE = [[0.30, 0.20], [0.70, 0.20], [0.95, 0.95], [0.05, 0.95]]
WORLD = [[0.0, 40.0], [7.0, 40.0], [7.0, 0.0], [0.0, 0.0]]
CAL = {"image": IMAGE, "world": WORLD}


def lane_poly(x0_m, x1_m):
    H = homography(WORLD, IMAGE)                    # world -> image, to draw the lane in the image
    return to_world(H, [[x0_m, 40], [x1_m, 40], [x1_m, 0], [x0_m, 0]]).tolist()


def stop_line(x0_m, x1_m):
    return to_world(homography(WORLD, IMAGE), [[x0_m, 0], [x1_m, 0]]).tolist()


LANES = [{"id": "N1", "polygon": lane_poly(0, 3.5), "stop_line": stop_line(0, 3.5)},
         {"id": "N2", "polygon": lane_poly(3.5, 7.0), "stop_line": stop_line(3.5, 7.0)}]


def img(x_m, y_m):
    return to_world(homography(WORLD, IMAGE), [[x_m, y_m]])[0]


def test_homography_maps_the_calibration_points_and_keeps_straight_lines():
    H = homography(IMAGE, WORLD)
    assert np.allclose(to_world(H, IMAGE), WORLD, atol=1e-6)
    mid = to_world(H, [img(1.75, 20.0)])[0]          # a point 20 m up lane 1 maps back to 20 m
    assert np.allclose(mid, [1.75, 20.0], atol=1e-6)


def test_perspective_queue_lengths_are_in_ground_metres():
    m = LaneModel(LANES, CAL)
    vehicles = [(*img(1.75, 6.0), True), (*img(1.75, 18.0), True), (*img(1.75, 30.0), False),   # lane 1
                (*img(5.25, 9.0), True)]                                                       # lane 2
    r = m.measure(vehicles)
    assert r["N1"]["vehicles"] == 3 and r["N1"]["queued"] == 2
    assert abs(r["N1"]["queue_m"] - (18.0 + 2.5)) < 0.05          # farthest STOPPED vehicle, not the moving one
    assert r["N2"] == {"vehicles": 1, "queued": 1, "queue_m": 11.5}
    # equal steps on the ground are unequal steps in the image (perspective): the far one is smaller
    near = img(1.75, 10)[1] - img(1.75, 0)[1]
    far = img(1.75, 40)[1] - img(1.75, 30)[1]
    assert abs(near) > abs(far) * 1.5


def test_without_calibration_counts_only():
    m = LaneModel(LANES)
    r = m.measure([(*img(1.75, 6.0), True)])
    assert r["N1"] == {"vehicles": 1, "queued": 1, "queue_m": None}
    assert r["N2"] == {"vehicles": 0, "queued": 0, "queue_m": None}


def test_vehicles_outside_every_lane_are_ignored():
    m = LaneModel(LANES, CAL)
    r = m.measure([(0.01, 0.5, True), (0.5, 0.05, True)])
    assert all(v["vehicles"] == 0 for v in r.values())


def test_bad_calibration_is_rejected():
    with pytest.raises(ValueError):
        homography(IMAGE[:3], WORLD[:3])
    with pytest.raises(ValueError):
        homography([[0, 0], [0.5, 0.5], [1, 1], [0.2, 0.2]], WORLD)      # all on one line
    with pytest.raises(ValueError):
        LaneModel([{"id": "x", "polygon": [[0, 0], [1, 1]]}])
