"""Signal drivers: the only code that would touch signal hardware.

  none        no hardware (the default): commands go nowhere, nothing is read back
  simulated   a simulated field controller: applies each command after `latency_s` and reports the lamps it
              really shows; faults can be injected (a stuck lamp, a dropped link) to test the monitor

Adding a hardware driver (FYP-2, with the traffic authority): subclass SignalDriver and implement
  write(lamps)   send the lamp states (e.g. NTCIP 1202 phase control over SNMP, or a relay board over serial)
  read()         return the lamp states the controller / load switches report, or None if it cannot tell
  flash()        put the cabinet into its own flash mode (the cabinet's monitor also does this independently)
and register it in DRIVERS. Keep the conflict monitor in front of it, and keep the cabinet's own hardware
conflict monitor: software checks add to it, they never replace it."""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod


class SignalDriver(ABC):
    name = "base"

    @abstractmethod
    def write(self, lamps: dict[str, str]) -> None: ...

    def read(self) -> dict[str, str] | None:
        return None

    def flash(self) -> None:
        """Fail-safe: all approaches flashing red."""

    def info(self) -> dict:
        return {"driver": self.name}


class NullDriver(SignalDriver):
    name = "none"

    def write(self, lamps: dict[str, str]) -> None:
        pass


class SimulatedController(SignalDriver):
    """Stands in for a field controller. Thread-safe; uses time.monotonic() unless a clock is given (tests)."""
    name = "simulated"

    def __init__(self, approaches: tuple[str, ...], latency_s: float = 0.05, clock=time.monotonic):
        self.approaches = tuple(approaches)
        self.latency_s = latency_s
        self.clock = clock
        self._lock = threading.Lock()
        self._shown = {a: "red" for a in self.approaches}
        self._pending: list[tuple[float, dict[str, str]]] = []
        self.flashing = False
        self.writes = 0
        # fault injection
        self.stuck: dict[str, str] = {}        # approach -> lamp it is stuck on
        self.link_down = False                  # commands are lost

    def _settle(self) -> None:
        now = self.clock()
        while self._pending and self._pending[0][0] <= now:
            _, lamps = self._pending.pop(0)
            self._shown.update(lamps)
        for a, v in self.stuck.items():
            self._shown[a] = v

    def write(self, lamps: dict[str, str]) -> None:
        with self._lock:
            if self.link_down or self.flashing:
                return
            self.writes += 1
            self._pending.append((self.clock() + self.latency_s, dict(lamps)))
            self._settle()

    def read(self) -> dict[str, str] | None:
        with self._lock:
            self._settle()
            if self.flashing:
                return {a: "red" for a in self.approaches}
            return dict(self._shown)

    def flash(self) -> None:
        with self._lock:
            self.flashing = True
            self._pending.clear()

    def unflash(self) -> None:
        with self._lock:
            self.flashing = False
            self._shown = {a: "red" for a in self.approaches}

    def info(self) -> dict:
        return {"driver": self.name, "latency_s": self.latency_s, "flashing": self.flashing, "writes": self.writes,
                "stuck": dict(self.stuck), "link_down": self.link_down}


DRIVERS = {"none": NullDriver, "simulated": SimulatedController}


def create_driver(name: str, approaches: tuple[str, ...], **params) -> SignalDriver:
    if name == "none":
        return NullDriver()
    if name == "simulated":
        return SimulatedController(approaches, **params)
    raise ValueError(f"unknown signal driver '{name}'. Available: {sorted(DRIVERS)}")
