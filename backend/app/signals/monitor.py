"""ConflictMonitor: an independent check of every lamp state sent to (and read back from) the signal hardware.

It plays the role of the malfunction management unit / conflict monitor in a real signal cabinet: it does not
trust the controller that produced the lamp states, it only watches them. It knows nothing about ambulances,
queues or the controller's plans, only the safety rules:

  conflict        two conflicting approaches non-red at the same time
  no_yellow       an approach goes from green straight to red (yellow skipped)
  short_yellow    a yellow shorter than yellow_s
  short_all_red   a new green before all_red_s of all-red after the previous yellow ended
  short_green     a green shorter than min_green_s (flicker), unless it ends in a fault-flash
  watchdog        no command for watchdog_s (the controller or its link has stopped)
  mismatch        the lamps the hardware reports differ from the commanded ones for longer than mismatch_s
  bad_state       a lamp value that is not red / yellow / green

Times use the caller's clock (seconds), so it can be driven by tests and simulations. `tolerance_s` absorbs tick
jitter (the controller runs every 0.1 s)."""
from __future__ import annotations

from dataclasses import dataclass, field

LAMPS = ("red", "yellow", "green")


@dataclass
class MonitorConfig:
    yellow_s: float = 3.0
    all_red_s: float = 2.0
    min_green_s: float = 1.0
    watchdog_s: float = 1.0
    mismatch_s: float = 0.5
    tolerance_s: float = 0.15
    # pairs of approaches allowed to be non-red together (none for one-approach-at-a-time control)
    compatible: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Fault:
    kind: str
    detail: str
    t: float


class ConflictMonitor:
    def __init__(self, approaches: tuple[str, ...], cfg: MonitorConfig | None = None):
        self.approaches = tuple(approaches)
        self.cfg = cfg or MonitorConfig()
        self._compatible = {frozenset(p) for p in self.cfg.compatible}
        self.state = {a: "red" for a in self.approaches}
        self.since = {a: None for a in self.approaches}     # when the current lamp started (None = from boot)
        self.last_yellow_end: float | None = None
        self.last_command: float | None = None
        self.mismatch_since: float | None = None

    # ------------------------------------------------------------------ commanded states
    def check_command(self, lamps: dict[str, str], now: float) -> Fault | None:
        c, tol = self.cfg, self.cfg.tolerance_s
        for a, v in lamps.items():
            if a not in self.state:
                return Fault("bad_state", f"unknown approach {a!r}", now)
            if v not in LAMPS:
                return Fault("bad_state", f"{a}: lamp value {v!r}", now)
        new = {a: lamps.get(a, "red") for a in self.approaches}
        live = [a for a in self.approaches if new[a] != "red"]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if frozenset((a, b)) not in self._compatible:
                    return Fault("conflict", f"{a} {new[a]} and {b} {new[b]} at the same time", now)
        for a in self.approaches:
            old, cur, t0 = self.state[a], new[a], self.since[a]
            held = None if t0 is None else now - t0
            if old == cur:
                continue
            if old == "green" and cur == "red":
                return Fault("no_yellow", f"{a} went green -> red without yellow", now)
            if old == "green" and held is not None and held < c.min_green_s - tol:
                return Fault("short_green", f"{a} green for {held:.2f} s < {c.min_green_s} s", now)
            if old == "yellow" and cur == "red" and held is not None and held < c.yellow_s - tol:
                return Fault("short_yellow", f"{a} yellow for {held:.2f} s < {c.yellow_s} s", now)
            if old == "yellow" and cur == "green":
                return Fault("no_yellow", f"{a} went yellow -> green", now)
            if cur == "green" and self.last_yellow_end is not None:
                gap = now - self.last_yellow_end
                if gap < c.all_red_s - tol:
                    return Fault("short_all_red", f"{a} green {gap:.2f} s after the last yellow < {c.all_red_s} s", now)
        for a in self.approaches:                 # accept the new state
            if self.state[a] != new[a]:
                if self.state[a] == "yellow" and new[a] == "red":
                    self.last_yellow_end = now
                self.state[a], self.since[a] = new[a], now
        self.last_command = now
        return None

    # ------------------------------------------------------------------ time and feedback
    def check_watchdog(self, now: float) -> Fault | None:
        if self.last_command is not None and now - self.last_command > self.cfg.watchdog_s:
            return Fault("watchdog", f"no command for {now - self.last_command:.2f} s > {self.cfg.watchdog_s} s", now)
        return None

    def check_feedback(self, reported: dict[str, str] | None, now: float) -> Fault | None:
        """Compare what the hardware says it shows with what was last commanded."""
        if reported is None:
            self.mismatch_since = None
            return None
        diff = [a for a in self.approaches if reported.get(a, "red") != self.state[a]]
        if not diff:
            self.mismatch_since = None
            return None
        if self.mismatch_since is None:
            self.mismatch_since = now
        if now - self.mismatch_since > self.cfg.mismatch_s:
            d = ", ".join(f"{a}: commanded {self.state[a]}, shows {reported.get(a, 'red')}" for a in diff)
            return Fault("mismatch", d, now)
        return None
