"""IntersectionController: the safety + preemption layer around a base controller.

Guarantees (covered by tests/test_controller.py):
  * at most one approach is non-red at any time
  * every green ends with a full yellow, then a full all-red, before the next green
  * an ambulance on approach A turns A green and the other three red
  * preemption is FIFO when several ambulances are present
  * a stuck detection cannot hold the junction longer than max_preempt_s
  * after a preemption, approaches that waited get extra green (fair recovery)

The controller never reads a clock. Callers pass `now` (seconds), so it is
deterministic in tests and can run inside a SUMO/MARL simulation step."""
from __future__ import annotations

import math

from .base import BaseController
from .types import (APPROACHES, Context, Emit, Mode, PreemptConfig, Stage, Stats, Timing)

INF = math.inf


class IntersectionController:
    def __init__(self, iid: str, base: BaseController, timing: Timing, preempt: PreemptConfig,
                 approaches: tuple[str, ...] = APPROACHES, emit: Emit | None = None, now: float = 0.0):
        self.id = iid
        self.base = base
        self.timing = timing
        self.cfg = preempt
        self.approaches = tuple(approaches)
        self._emit = emit or (lambda *_a, **_k: None)

        a = self.approaches
        self.vehicles = {x: 0 for x in a}
        self.last_seen = {x: -INF for x in a}
        self.first_seen = {x: -INF for x in a}
        self.manual_until = {x: -INF for x in a}
        self.last_green_end = {x: now for x in a}
        self.suppressed: set[str] = set()

        self.preempt_target: str | None = None
        self.target_since = 0.0
        self.preempt_started: float | None = None
        self.served: set[str] = set()
        self.recovery_plan: list[tuple[str, float]] = []
        self.recovering = False
        self.stats = Stats()
        self._mode = Mode.NORMAL

        self.stage = Stage.ALL_RED
        self.cur: str | None = None
        self.stage_start = now
        self.stage_dur = 0.0
        approach, green_s = self._decide(now, current=a[-1])
        self._start_green(approach, green_s, "base", now)

    # ---------------------------------------------------------------- inputs
    def observe(self, approach: str, present: bool, now: float, vehicles: int | None = None) -> None:
        """Report what the camera sees. Call every frame / heartbeat."""
        if vehicles is not None:
            self.vehicles[approach] = vehicles
        if not present:
            return
        if not self._raw_active(approach, now):
            self.first_seen[approach] = now
        self.last_seen[approach] = now

    def inject(self, approach: str, duration_s: float, now: float) -> None:
        """Operator override: behave as if an ambulance were present for duration_s."""
        if not self._raw_active(approach, now):
            self.first_seen[approach] = now
        self.manual_until[approach] = now + duration_s

    def cancel(self, approach: str) -> None:
        self.last_seen[approach] = -INF
        self.manual_until[approach] = -INF
        self.suppressed.discard(approach)

    def is_ambulance_active(self, approach: str, now: float) -> bool:
        return self._active(approach, now)

    # ------------------------------------------------------------------ tick
    def tick(self, now: float) -> None:
        self._refresh(now)
        target = self._choose_target(now)
        if target != self.preempt_target:
            self._set_target(target, now)

        elapsed = now - self.stage_start
        if self.stage is Stage.GREEN:
            cut = target is not None and target != self.cur and elapsed >= self.cfg.min_green_s
            expired = target is None and elapsed >= self.stage_dur
            if cut or expired:
                self._start_yellow(now)
        elif self.stage is Stage.YELLOW:
            if elapsed >= self.timing.yellow_s:
                self._start_all_red(now)
        elif elapsed >= self.timing.all_red_s:
            approach, green_s, source = self._next_approach(now)
            self._start_green(approach, green_s, source, now)
        self._update_mode()

    # ------------------------------------------------------------- snapshot
    def lamps(self) -> dict[str, str]:
        lamps = {a: "red" for a in self.approaches}
        if self.stage is Stage.GREEN and self.cur:
            lamps[self.cur] = "green"
        elif self.stage is Stage.YELLOW and self.cur:
            lamps[self.cur] = "yellow"
        return lamps

    def snapshot(self, now: float) -> dict:
        elapsed = max(0.0, now - self.stage_start)
        holding = self.stage is Stage.GREEN and self.preempt_target == self.cur
        if holding:
            remaining = None
        elif self.stage is Stage.GREEN:
            remaining = max(0.0, self.stage_dur - elapsed)
        elif self.stage is Stage.YELLOW:
            remaining = max(0.0, self.timing.yellow_s - elapsed)
        else:
            remaining = max(0.0, self.timing.all_red_s - elapsed)
        return {
            "id": self.id,
            "controller": self.base.name,
            "mode": self._mode.value,
            "stage": self.stage.value,
            "current": self.cur,
            "active_preempt": self.preempt_target,
            "stage_elapsed_s": round(elapsed, 1),
            "stage_remaining_s": None if remaining is None else round(remaining, 1),
            "lamps": self.lamps(),
            "ambulance": {a: self._active(a, now) for a in self.approaches},
            "vehicles": dict(self.vehicles),
            "waiting_s": {a: round(self._waiting(a, now), 1) for a in self.approaches},
            "recovery_plan": [a for a, _ in self.recovery_plan],
            "stats": self.stats.to_dict(),
        }

    # ------------------------------------------------------------- internals
    def _raw_active(self, a: str, now: float) -> bool:
        return (now - self.last_seen[a]) <= self.cfg.clear_hold_s or now < self.manual_until[a]

    def _active(self, a: str, now: float) -> bool:
        return a not in self.suppressed and self._raw_active(a, now)

    def _waiting(self, a: str, now: float) -> float:
        if a == self.cur and self.stage in (Stage.GREEN, Stage.YELLOW):
            return 0.0
        return max(0.0, now - self.last_green_end[a])

    def _context(self, now: float, current: str | None) -> Context:
        return Context(now=now, current=current, approaches=self.approaches,
                       vehicles=dict(self.vehicles),
                       waiting_s={a: self._waiting(a, now) for a in self.approaches})

    def _decide(self, now: float, current: str | None) -> tuple[str, float]:
        d = self.base.next_phase(self._context(now, current))
        return d.approach, d.green_s

    def _refresh(self, now: float) -> None:
        for a in list(self.suppressed):
            if not self._raw_active(a, now):
                self.suppressed.discard(a)
        t = self.preempt_target
        if t is not None and now - self.target_since >= self.cfg.max_preempt_s:
            self.suppressed.add(t)
            self._emit("preempt_timeout", approach=t, max_preempt_s=self.cfg.max_preempt_s)

    def _choose_target(self, now: float) -> str | None:
        if self.preempt_target and self._active(self.preempt_target, now):
            return self.preempt_target  # keep serving the same ambulance (no flapping)
        cands = [a for a in self.approaches if self._active(a, now)]
        return min(cands, key=lambda a: self.first_seen[a]) if cands else None

    def _set_target(self, target: str | None, now: float) -> None:
        prev = self.preempt_target
        if prev is None and target is not None:
            self.preempt_started = now
            self.served = set()
            self.target_since = now
            self.preempt_target = target
            self._emit("preempt_started", approach=target, queued=[
                a for a in self.approaches if a != target and self._active(a, now)])
            if self.stage is Stage.GREEN and self.cur == target:
                self._granted(target, now)  # already green: zero-latency grant
        elif prev is not None and target is None:
            self._end_preempt(now)
            self.preempt_target = None
        else:  # ambulance served, next one in the queue
            self.target_since = now
            self.preempt_target = target
            self._emit("preempt_switched", from_approach=prev, approach=target)
            if self.stage is Stage.GREEN and self.cur == target:
                self._granted(target, now)

    def _granted(self, a: str, now: float) -> None:
        if a in self.served:
            return
        self.served.add(a)
        latency = max(0.0, now - self.first_seen[a])
        self.stats.latencies_s.append(latency)
        del self.stats.latencies_s[:-200]
        self._emit("preempt_green", approach=a, latency_s=round(latency, 2))

    def _end_preempt(self, now: float) -> None:
        dur = now - (self.preempt_started if self.preempt_started is not None else now)
        self.stats.preemptions += 1
        self.stats.total_preempt_s += dur
        self._emit("preempt_ended", approach=self.preempt_target, duration_s=round(dur, 1),
                   served=sorted(self.served))
        if self.served:
            extra = min(self.cfg.recovery_max_s, self.cfg.recovery_factor * dur)
            others = sorted((a for a in self.approaches if a not in self.served),
                            key=lambda a: -self._waiting(a, now))
            self.recovery_plan = [(a, self.timing.green_s + extra) for a in others]
            if self.recovery_plan:
                self._emit("recovery_planned", plan=[a for a, _ in self.recovery_plan],
                           extra_green_s=round(extra, 1))
        if self.stage is Stage.GREEN and self.cur in self.served:
            self.stage_dur = 0.0  # release the junction right away
        self.preempt_started = None
        self.served = set()

    def _next_approach(self, now: float) -> tuple[str, float, str]:
        if self.preempt_target:
            return self.preempt_target, self.timing.green_s, "preempt"
        if self.recovery_plan:
            a, d = self.recovery_plan.pop(0)
            return a, d, "recovery"
        a, d = self._decide(now, self.cur)
        return a, d, "base"

    def _start_green(self, a: str, dur: float, source: str, now: float) -> None:
        self.stage = Stage.GREEN
        self.cur = a
        self.stage_start = now
        self.stage_dur = dur
        self.recovering = source == "recovery"
        if source == "preempt":
            self._granted(a, now)
        self._emit("phase_changed", approach=a, source=source, green_s=round(dur, 1))

    def _start_yellow(self, now: float) -> None:
        self.stage = Stage.YELLOW
        self.stage_start = now
        if self.cur:
            self.last_green_end[self.cur] = now

    def _start_all_red(self, now: float) -> None:
        self.stage = Stage.ALL_RED
        self.stage_start = now

    def _update_mode(self) -> None:
        if self.preempt_target:
            m = Mode.PREEMPT
        elif self.recovery_plan or self.recovering:
            m = Mode.RECOVERY
        else:
            m = Mode.NORMAL
        if m is not self._mode:
            self._emit("mode_changed", from_mode=self._mode.value, to_mode=m.value)
            self._mode = m
