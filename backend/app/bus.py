"""In-process event bus. Everything that happens (ambulance detected, phase
changed, preemption started, ...) is published here once and fanned out to
WebSocket clients, the MQTT bridge, and the history served by GET /api/events."""
from __future__ import annotations

import asyncio
import itertools
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Callable


class EventBus:
    def __init__(self, history: int = 500):
        self._history: deque[dict] = deque(maxlen=history)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict], None]] = []
        self._queues: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def add_listener(self, fn: Callable[[dict], None]) -> None:
        """Sync listener, called in the publisher's thread. Must not block."""
        self._listeners.append(fn)

    def publish(self, type: str, **data) -> dict:
        event = {"id": next(self._ids), "ts": round(time.time(), 3), "type": type, **data}
        with self._lock:
            self._history.append(event)
            queues = list(self._queues)
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:  # noqa: BLE001 - a bad listener must never break control
                pass
        if self._loop is not None:
            for q in queues:
                self._loop.call_soon_threadsafe(self._put, q, event)
        return event

    @staticmethod
    def _put(q: asyncio.Queue, event: dict) -> None:
        if q.full():
            try:
                q.get_nowait()  # slow client: drop the oldest
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(event)

    def recent(self, limit: int = 100, exclude: tuple[str, ...] = ()) -> list[dict]:
        with self._lock:
            items = [e for e in self._history if e["type"] not in exclude]
        return items[-limit:][::-1]  # newest first

    @contextmanager
    def subscribe(self):
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        with self._lock:
            self._queues.add(q)
        try:
            yield q
        finally:
            with self._lock:
                self._queues.discard(q)
