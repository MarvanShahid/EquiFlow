"""Calibrated lane-level queues for one camera approach.

Configuration (per approach, in the intersection's config; all image coordinates normalised 0..1):

    lanes:
      North:
        - {id: N1, polygon: [[x, y], ...], stop_line: [[x, y], [x, y]]}
        - {id: N2, polygon: [...], stop_line: [...]}
    calibration:
      North:
        image: [[x, y], [x, y], [x, y], [x, y]]    # four points on the road surface in the image
        world: [[X, Y], [X, Y], [X, Y], [X, Y]]    # the same points on the ground, in metres

The calibration is a ground-plane homography (image -> metres), e.g. from lane markings of known width and
dash spacing. A vehicle belongs to the lane that contains its bottom-centre (where it touches the road). Per
lane the model reports the vehicles in it, the ones standing still (the queue), and the queue length in metres:
the ground distance from the stop line to the farthest queued vehicle plus half a vehicle length. Without a
calibration the counts are still reported and the length is None.

`Projects/calibrate_lanes.py` produces this configuration by clicking on a video frame."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Lane:
    id: str
    polygon: np.ndarray          # (n, 2) normalised image coordinates
    stop_line: np.ndarray | None  # (2, 2) normalised image coordinates


def homography(image_pts, world_pts) -> np.ndarray:
    img = np.asarray(image_pts, dtype=np.float64)
    wld = np.asarray(world_pts, dtype=np.float64)
    if img.shape != wld.shape or img.shape[0] < 4 or img.shape[1] != 2:
        raise ValueError("calibration needs at least 4 image points and the same number of world points")
    for pts, name in ((img, "image"), (wld, "world")):
        span = float(np.ptp(pts, axis=0).max()) or 1.0
        for i in range(len(pts)):                      # three points on one line make the homography meaningless
            for j in range(i + 1, len(pts)):
                for k in range(j + 1, len(pts)):
                    a, b, c = pts[i], pts[j], pts[k]
                    if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-4 * span * span:
                        raise ValueError(f"calibration {name} points {i}, {j}, {k} are on one line")
    H, _ = cv2.findHomography(img, wld, 0)
    if H is None:
        raise ValueError("calibration points are degenerate (three of them on one line?)")
    return H


def to_world(H: np.ndarray, pts) -> np.ndarray:
    p = np.asarray(pts, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(p, H).reshape(-1, 2)


def _seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    t = 0.0 if not ab.any() else float(np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


class LaneModel:
    def __init__(self, lanes: list[dict], calibration: dict | None = None, half_vehicle_m: float = 2.5):
        self.lanes = [Lane(str(l["id"]), np.asarray(l["polygon"], dtype=np.float32),
                           np.asarray(l["stop_line"], dtype=np.float64) if l.get("stop_line") else None)
                      for l in lanes]
        for l in self.lanes:
            if l.polygon.ndim != 2 or len(l.polygon) < 3:
                raise ValueError(f"lane {l.id}: polygon needs at least 3 points")
        self.H = homography(calibration["image"], calibration["world"]) if calibration else None
        self.half_vehicle_m = half_vehicle_m
        self._stop_world = {l.id: to_world(self.H, l.stop_line) for l in self.lanes
                            if self.H is not None and l.stop_line is not None}

    def lane_of(self, x: float, y: float) -> str | None:
        """Lane containing the normalised image point (x, y), or None."""
        for l in self.lanes:
            if cv2.pointPolygonTest(l.polygon.reshape(-1, 1, 2), (float(x), float(y)), False) >= 0:
                return l.id
        return None

    def distance_to_stop_m(self, lane_id: str, x: float, y: float) -> float | None:
        s = self._stop_world.get(lane_id)
        if s is None:
            return None
        p = to_world(self.H, [[x, y]])[0]
        return _seg_dist(p, s[0], s[1])

    def measure(self, vehicles: list[tuple[float, float, bool]]) -> dict[str, dict]:
        """vehicles: (x, y, stationary) per tracked vehicle, (x, y) = normalised bottom-centre of its box.
        Returns lane id -> {vehicles, queued, queue_m}."""
        out = {l.id: {"vehicles": 0, "queued": 0, "queue_m": None} for l in self.lanes}
        far: dict[str, float] = {}
        for x, y, stationary in vehicles:
            lid = self.lane_of(x, y)
            if lid is None:
                continue
            out[lid]["vehicles"] += 1
            if stationary:
                out[lid]["queued"] += 1
                d = self.distance_to_stop_m(lid, x, y)
                if d is not None:
                    far[lid] = max(far.get(lid, 0.0), d)
        for lid, r in out.items():
            if lid in far:
                r["queue_m"] = round(far[lid] + self.half_vehicle_m, 1)
            elif r["queued"] == 0 and lid in self._stop_world:
                r["queue_m"] = 0.0
        return out
