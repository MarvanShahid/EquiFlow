"""Live vision: your two-model pipeline.

  Model 1  yolo26s (COCO)  + ByteTrack -> vehicle boxes with stable track IDs
  Model 2  cls_v4 classifier           -> p(ambulance) for each vehicle crop
  Voting   K of the last M frames      -> "confirmed ambulance"

The logic is the same as your tracking script. Differences for a long-running
service: per-track history is pruned, and each approach owns its detector (so
ByteTrack state is not shared) while the small classifier is shared behind a lock.

ultralytics is imported lazily so the backend still starts (in sim mode) on a
machine without it."""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

import cv2
import numpy as np

from ..config import VisionCfg
from .types import AmbDet, BaseSource, FrameResult, OnResult

PRUNE_AFTER_FRAMES = 300


class SharedClassifier:
    def __init__(self, cfg: VisionCfg):
        from ultralytics import YOLO  # lazy
        self.cfg = cfg
        self.model = YOLO(cfg.cls_weights)
        names = self.model.names
        self.amb_idx = next(k for k, v in names.items() if v == "ambulance")
        self._lock = threading.Lock()

    def prob_ambulance(self, crops: list[np.ndarray]) -> list[float]:
        with self._lock:  # one GPU call at a time
            res = self.model.predict(crops, imgsz=self.cfg.cls_imgsz, device=self.cfg.device, verbose=False)
        return [r.probs.data[self.amb_idx].item() for r in res]


class DirectionTracker:
    """Detect -> track -> classify -> vote, for one approach."""

    def __init__(self, cfg: VisionCfg, classifier: SharedClassifier):
        from ultralytics import YOLO  # lazy
        self.cfg = cfg
        self.cls = classifier
        self.det = YOLO(cfg.det_weights)
        self._reset_state()

    def _reset_state(self) -> None:
        c = self.cfg
        self.votes: dict[int, deque] = defaultdict(lambda: deque(maxlen=c.m))
        self.probs: dict[int, deque] = defaultdict(lambda: deque(maxlen=c.m))
        self.centers: dict[int, deque] = defaultdict(lambda: deque(maxlen=15))
        self.last_frame: dict[int, int] = {}
        self.active: set[int] = set()
        self.confirmed: set[int] = set()
        self.frame_no = 0

    def reset(self) -> None:
        """Call when a video loops: forget tracks and restart ByteTrack."""
        self._reset_state()
        self.det.predictor = None  # next .track() builds a fresh tracker
        try:
            from ultralytics.trackers.basetrack import BaseTrack
            BaseTrack.reset_id()
        except Exception:  # noqa: BLE001
            pass

    def process(self, frame: np.ndarray) -> FrameResult:
        c = self.cfg
        H, W = frame.shape[:2]
        self.frame_no += 1
        min_side = c.min_side * W / 1920
        thick, fscale = max(2, W // 600), max(0.6, W / 1800)

        r = self.det.track(source=frame, tracker="bytetrack.yaml", persist=True, imgsz=c.imgsz,
                           conf=c.det_conf, classes=c.vehicle_classes, device=c.device, verbose=False)[0]

        crops, keep = [], []
        if r.boxes is not None and r.boxes.id is not None:
            ids = r.boxes.id.int().cpu().tolist()
            for tid, (x1, y1, x2, y2) in zip(ids, r.boxes.xyxy.cpu().numpy()):
                bw, bh = x2 - x1, y2 - y1
                if min(bw, bh) < min_side:
                    continue
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                a = int(max(0, cx - bw / 2 * (1 + c.pad)))
                b = int(max(0, cy - bh / 2 * (1 + c.pad)))
                e = int(min(W, cx + bw / 2 * (1 + c.pad)))
                d = int(min(H, cy + bh / 2 * (1 + c.pad)))
                crop = frame[b:d, a:e]
                if crop.size == 0:
                    continue
                crops.append(crop)
                keep.append((int(tid), int(x1), int(y1), int(x2), int(y2)))

        ps = self.cls.prob_ambulance(crops) if crops else []
        seen: dict[int, tuple] = {}
        new_confirmed: list[AmbDet] = []

        for (tid, x1, y1, x2, y2), p in zip(keep, ps):
            self.last_frame[tid] = self.frame_no
            self.probs[tid].append(p)
            self.votes[tid].append(int(p >= c.th_frame))
            self.centers[tid].append(((x1 + x2) / 2, (y1 + y2) / 2))
            n_votes = sum(self.votes[tid])
            (xa, ya), (xb, yb) = self.centers[tid][0], self.centers[tid][-1]
            moved = math.hypot(xb - xa, yb - ya)

            if (tid not in self.active and n_votes >= c.k
                    and float(np.mean(self.probs[tid])) >= c.mean_min and moved >= c.min_move * W):
                self.active.add(tid)
                if tid not in self.confirmed:
                    self.confirmed.add(tid)
                    new_confirmed.append(self._det(tid, p, x1, y1, x2, y2, W, H))
            elif tid in self.active and n_votes <= c.release:
                self.active.discard(tid)

            if tid in self.active:
                color, label = (0, 0, 255), f"AMBULANCE id{tid} p{p:.2f}"
            elif n_votes > 0:
                color, label = (0, 255, 255), f"? id{tid} p{p:.2f}"
            else:
                color, label = (0, 200, 0), f"id{tid} p{p:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)
            cv2.putText(frame, label, (x1, max(y1 - 6, 20)), cv2.FONT_HERSHEY_SIMPLEX, fscale, color, thick)
            seen[tid] = (p, x1, y1, x2, y2)

        # tracks that are active but not in this frame's detections stay active until released
        ambulances = [self._det(t, *seen[t], W, H) for t in self.active if t in seen]
        if self.frame_no % 100 == 0:
            self._prune()
        return FrameResult(vehicles=len(keep), ambulances=ambulances, new_confirmed=new_confirmed, annotated=frame)

    @staticmethod
    def _det(tid, p, x1, y1, x2, y2, W, H) -> AmbDet:
        return AmbDet(track_id=tid, confidence=float(p), cx=round(((x1 + x2) / 2) / W, 4),
                      cy=round(((y1 + y2) / 2) / H, 4), bbox=(x1, y1, x2, y2))

    def _prune(self) -> None:
        for tid in [t for t, f in self.last_frame.items() if self.frame_no - f > PRUNE_AFTER_FRAMES]:
            for d in (self.votes, self.probs, self.centers, self.last_frame):
                d.pop(tid, None)
            self.active.discard(tid)


class LiveSource(BaseSource):
    kind = "live"

    def __init__(self, approach: str, source: str, tracker: DirectionTracker, cfg: VisionCfg,
                 on_result: OnResult, loop_video: bool | None = None):
        super().__init__(approach, on_result, cfg.stream_width, cfg.jpeg_quality)
        self.source = int(source) if str(source).isdigit() else source
        self.tracker = tracker
        self.cfg = cfg
        is_file = isinstance(self.source, str) and not self.source.lower().startswith(("rtsp://", "http://", "https://"))
        self.loop_video = is_file if loop_video is None else loop_video

    def run(self) -> None:
        while not self._stop_evt.is_set():
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                self.ok, self.error = False, f"cannot open source: {self.source}"
                self._stop_evt.wait(3.0)
                continue
            self.ok, self.error = True, None
            native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            interval = 1.0 / native_fps
            n = 0
            next_t = time.monotonic()
            while not self._stop_evt.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                n += 1
                t0 = time.monotonic()
                if n % max(1, self.cfg.process_every) == 0:
                    try:
                        res = self.tracker.process(frame)
                    except Exception as e:  # noqa: BLE001 - keep the feed alive
                        self.error = f"inference error: {e}"
                        continue
                    self.publish_frame(frame, res, time.monotonic() - t0)
                # keep real-time pace for files; if inference is slower than the video, drop frames
                next_t += interval
                lag = time.monotonic() - next_t
                if lag > 0:
                    for _ in range(min(5, int(lag / interval))):
                        cap.grab()
                    next_t = time.monotonic()
                else:
                    self._stop_evt.wait(-lag)
            cap.release()
            if self.loop_video and not self._stop_evt.is_set():
                self.tracker.reset()
            elif not self._stop_evt.is_set():
                self.ok, self.error = False, "stream ended; reconnecting"
                self._stop_evt.wait(3.0)
