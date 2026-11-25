"""SignalOutput: sends the controller's lamps to a driver through the conflict monitor, and latches the fail-safe.

  apply(lamps, now)   every controller tick: monitor the command, write it, read back and compare
  poll(now)           between commands (watchdog, feedback); apply() calls it too
  reset(now)          operator reset after a fault; refused while the cause is still present

While latched, the driver is kept in flash (all-red flashing) and no command reaches it; the controller keeps
running internally so its state is ready when an operator resets the output."""
from __future__ import annotations

import threading

from .drivers import SignalDriver
from .monitor import ConflictMonitor, Fault


class SignalOutput:
    def __init__(self, iid: str, approaches: tuple[str, ...], driver: SignalDriver, monitor: ConflictMonitor,
                 emit=None):
        self.id = iid
        self.approaches = tuple(approaches)
        self.driver, self.monitor = driver, monitor
        self._emit = emit or (lambda *_a, **_k: None)
        self._lock = threading.Lock()
        self.fault: Fault | None = None
        self.faults_total = 0
        self.commands = 0
        self.resets = 0

    @property
    def flashing(self) -> bool:
        return self.fault is not None

    def _latch(self, f: Fault) -> None:
        self.fault = f
        self.faults_total += 1
        self.driver.flash()
        self._emit("signal_fault", kind=f.kind, detail=f.detail, action="flash")

    def apply(self, lamps: dict[str, str], now: float) -> None:
        with self._lock:
            if self.fault is not None:
                self.driver.flash()
                return
            f = self.monitor.check_command(lamps, now)
            if f is not None:
                self._latch(f)
                return
            self.driver.write({a: lamps.get(a, "red") for a in self.approaches})
            self.commands += 1
            self._poll(now)

    def poll(self, now: float) -> None:
        with self._lock:
            self._poll(now)

    def _poll(self, now: float) -> None:
        if self.fault is not None:
            return
        f = self.monitor.check_watchdog(now) or self.monitor.check_feedback(self.driver.read(), now)
        if f is not None:
            self._latch(f)

    def start_watchdog(self, clock, period_s: float = 0.1) -> None:
        """Independent thread: catches a controller (or ticker) that stops sending commands."""
        self._wd_stop = threading.Event()

        def loop():
            while not self._wd_stop.wait(period_s):
                self.poll(clock())

        threading.Thread(target=loop, daemon=True, name=f"signal-watchdog-{self.id}").start()

    def stop_watchdog(self) -> None:
        if getattr(self, "_wd_stop", None) is not None:
            self._wd_stop.set()

    def reset(self, now: float) -> tuple[bool, str]:
        """Operator reset. Allowed only when the hardware can be brought back to all-red and reads back as such."""
        with self._lock:
            if self.fault is None:
                return True, "no fault"
            if hasattr(self.driver, "unflash"):
                self.driver.unflash()
            reported = self.driver.read()
            if reported is not None and any(v != "red" for v in reported.values()):
                self.driver.flash()
                return False, f"hardware does not show all-red after reset ({reported}); fault kept"
            if getattr(self.driver, "link_down", False):
                self.driver.flash()
                return False, "link to the controller is down; fault kept"
            old = self.fault
            self.fault = None
            self.resets += 1
            m = self.monitor
            m.state = {a: "red" for a in self.approaches}         # restart from all-red, as after a power-up
            m.since = {a: now for a in self.approaches}
            m.last_yellow_end, m.last_command, m.mismatch_since = now, now, None
            self._emit("signal_reset", cleared=old.kind)
            return True, f"cleared {old.kind}"

    def status(self) -> dict:
        f = self.fault
        return {"driver": self.driver.info(), "flashing": self.flashing,
                "fault": None if f is None else {"kind": f.kind, "detail": f.detail},
                "faults_total": self.faults_total, "commands": self.commands, "resets": self.resets}
