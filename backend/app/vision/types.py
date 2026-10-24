from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2


@dataclass
class AmbDet:
    track_id: int
    confidence: float
    cx: float  # centre, normalised 0..1
    cy: float
    bbox: tuple[int, int, int, int]


@dataclass
class FrameResult:
    vehicles: int                       # tracked vehicles seen this frame
    ambulances: list[AmbDet]            # confirmed ambulance tracks currently active
    new_confirmed: list[AmbDet]         # tracks that became confirmed on this frame
    annotated: Any = None               # BGR image with boxes drawn (numpy array)


OnResult = Callable[[str, FrameResult, float], None]  # (approach, result, fps)


class BaseSource(threading.Thread):
    """One camera / video feed for one approach. Produces FrameResults and a
    JPEG of the latest annotated frame for the MJPEG stream."""

    kind = "base"

    def __init__(self, approach: str, on_result: OnResult, stream_width: int = 640, jpeg_quality: int = 70):
        super().__init__(daemon=True, name=f"src-{approach}")
        self.approach = approach
        self.on_result = on_result
        self.stream_width = stream_width
        self.jpeg_quality = jpeg_quality
        self._stop_evt = threading.Event()
        self._jpeg: bytes | None = None
        self._lock = threading.Lock()
        self.ok = False
        self.error: str | None = None
        self.fps = 0.0

    def stop(self) -> None:
        self._stop_evt.set()

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def publish_frame(self, frame, result: FrameResult, dt: float) -> None:
        if dt > 0:
            inst = 1.0 / dt
            self.fps = inst if self.fps == 0 else 0.8 * self.fps + 0.2 * inst
        h, w = frame.shape[:2]
        if w > self.stream_width:
            frame = cv2.resize(frame, (self.stream_width, int(h * self.stream_width / w)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if ok:
            with self._lock:
                self._jpeg = buf.tobytes()
        self.on_result(self.approach, result, self.fps)

    def info(self) -> dict:
        return {"kind": self.kind, "ok": self.ok, "error": self.error, "fps": round(self.fps, 1)}
