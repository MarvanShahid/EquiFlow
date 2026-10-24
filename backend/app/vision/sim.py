"""Simulated camera: lets you build and demo the whole stack without GPUs,
weights or videos. It draws a synthetic road with moving cars and (on demand or
at random) an ambulance, and emits the same FrameResult the live pipeline does."""
from __future__ import annotations

import random
import time

import cv2
import numpy as np

from ..config import SimCfg
from .types import AmbDet, BaseSource, FrameResult, OnResult

W, H = 640, 360
FPS = 10
# direction a vehicle travels on screen for each approach (they drive towards the junction)
VEC = {"North": (0, 1), "South": (0, -1), "East": (-1, 0), "West": (1, 0)}


class SimSource(BaseSource):
    kind = "sim"

    def __init__(self, approach: str, cfg: SimCfg, on_result: OnResult, stream_width: int = 640,
                 jpeg_quality: int = 70, seed: int | None = None):
        super().__init__(approach, on_result, stream_width, jpeg_quality)
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.cars: list[dict] = []
        self.amb: dict | None = None
        self.amb_until = 0.0
        self.next_auto = time.monotonic() + self.rng.uniform(5, cfg.max_gap_s)
        self.track_ctr = 0
        self.ok = True
        self.vx, self.vy = VEC.get(approach, (0, 1))

    # called by the API when an operator presses "Simulate ambulance"
    def trigger(self, duration_s: float | None = None) -> None:
        self.amb_until = time.monotonic() + (duration_s or self.cfg.ambulance_s)

    def run(self) -> None:
        dt = 1.0 / FPS
        while not self._stop_evt.is_set():
            t0 = time.monotonic()
            frame, res = self._step(t0, dt)
            self.publish_frame(frame, res, dt)
            self._stop_evt.wait(max(0.0, dt - (time.monotonic() - t0)))

    # ------------------------------------------------------------------
    def _lane_pos(self, s: float, lane: int) -> tuple[float, float]:
        """s in 0..1 along the direction of travel, lane 0/1 across."""
        if self.vx == 0:  # vertical road
            x = W * (0.42 + 0.16 * lane)
            y = H * (s if self.vy > 0 else 1 - s)
            return x, y
        y = H * (0.42 + 0.16 * lane)
        x = W * (s if self.vx > 0 else 1 - s)
        return x, y

    def _step(self, now: float, dt: float):
        if self.cfg.auto_ambulance and now >= self.next_auto and self.amb is None:
            self.trigger()
            self.next_auto = now + self.rng.uniform(self.cfg.min_gap_s, self.cfg.max_gap_s)

        for c in self.cars:
            c["s"] += c["v"] * dt
        self.cars = [c for c in self.cars if c["s"] < 1.1]
        if self.rng.random() < 0.18 and len(self.cars) < 14:
            self.cars.append({"s": -0.05, "lane": self.rng.randint(0, 1), "v": self.rng.uniform(0.07, 0.14),
                              "col": self.rng.choice([(90, 90, 200), (60, 160, 90), (170, 120, 60),
                                                      (150, 150, 150), (40, 160, 200)])})

        amb_on = now < self.amb_until
        if amb_on and self.amb is None:
            self.track_ctr += 1
            self.amb = {"s": -0.05, "lane": 0, "v": 0.09, "id": 1000 + self.track_ctr, "frames": 0, "confirmed": False}
        if not amb_on and self.amb is not None and self.amb["s"] > 1.05:
            self.amb = None
        if self.amb is not None:
            self.amb["s"] = min(1.15, self.amb["s"] + self.amb["v"] * dt)
            self.amb["frames"] += 1
            if not amb_on and self.amb["s"] >= 1.15:
                self.amb = None

        frame = self._draw_road()
        for c in self.cars:
            self._draw_vehicle(frame, c, c["col"], f"id{int(c['s'] * 1000) % 97}")

        ambs: list[AmbDet] = []
        new: list[AmbDet] = []
        if self.amb is not None and -0.02 < self.amb["s"] < 1.1:
            x, y = self._lane_pos(self.amb["s"], self.amb["lane"])
            confirmed = self.amb["frames"] >= 5  # mimics the K-of-M voting delay
            bw, bh = self._size()
            det = AmbDet(self.amb["id"], 0.93, round(x / W, 4), round(y / H, 4),
                         (int(x - bw / 2), int(y - bh / 2), int(x + bw / 2), int(y + bh / 2)))
            if confirmed:
                ambs.append(det)
                if not self.amb["confirmed"]:
                    self.amb["confirmed"] = True
                    new.append(det)
            self._draw_vehicle(frame, self.amb, (245, 245, 245), f"AMBULANCE id{self.amb['id']}" if confirmed else "?",
                               red=confirmed, flash=int(now * 4) % 2)
        return frame, FrameResult(vehicles=len(self.cars) + (1 if self.amb else 0), ambulances=ambs,
                                  new_confirmed=new, annotated=frame)

    def _size(self) -> tuple[int, int]:
        return (22, 38) if self.vx == 0 else (38, 22)

    def _draw_road(self) -> np.ndarray:
        f = np.full((H, W, 3), (38, 40, 44), np.uint8)
        if self.vx == 0:
            cv2.rectangle(f, (int(W * 0.35), 0), (int(W * 0.65), H), (58, 60, 66), -1)
            for y in range(0, H, 30):
                cv2.line(f, (W // 2, y), (W // 2, y + 14), (200, 200, 200), 2)
        else:
            cv2.rectangle(f, (0, int(H * 0.35)), (W, int(H * 0.65)), (58, 60, 66), -1)
            for x in range(0, W, 30):
                cv2.line(f, (x, H // 2), (x + 14, H // 2), (200, 200, 200), 2)
        return f

    def _draw_vehicle(self, frame, c, color, label, red=False, flash=0):
        x, y = self._lane_pos(c["s"], c["lane"])
        bw, bh = self._size()
        p1, p2 = (int(x - bw / 2), int(y - bh / 2)), (int(x + bw / 2), int(y + bh / 2))
        cv2.rectangle(frame, p1, p2, color, -1)
        if red:
            cv2.rectangle(frame, p1, p2, (0, 0, 255), 2)
            bar = (0, 0, 255) if flash else (255, 80, 0)
            cv2.rectangle(frame, (p1[0], p1[1]), (p2[0], p1[1] + 5), bar, -1)
            cv2.putText(frame, label, (p1[0] - 20, max(p1[1] - 8, 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255), 2)
