"""IntersectionController: the safety + preemption layer around a base controller.

Guarantees (covered by tests/test_controller.py):
  * at most one approach is non-red at any time
  * every green ends with a full yellow, then a full all-red, before the next green
  * an ambulance on approach A turns A green and the other three red
  * preemption is FIFO when several ambulances are present
  * a stuck detection cannot hold the junction longer than max_preempt_s
  * after a preemption, approaches that waited get extra green (fair recovery), longest wait first,
    more of it for longer queues
  * an empty green ends early (gap-out) only after gap_out_min_green_s, only if another approach has
    demand, never during priority, and always through yellow + all-red

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

    def time_to_green(self, approach: str, now: float) -> float:
        """Shortest time (s) in which `approach` could be green if it were requested now, honouring the
        minimum green, yellow and all-red. 0 if it is green already."""
        elapsed = now - self.stage_start
        t = self.timing
        if self.stage is Stage.GREEN:
            if self.cur == approach:
                return 0.0
            return max(0.0, self.cfg.min_green_s - elapsed) + t.yellow_s + t.all_red_s
        if self.stage is Stage.YELLOW:
            return max(0.0, t.yellow_s - elapsed) + t.all_red_s
        return max(0.0, t.all_red_s - elapsed)

    def green_remaining(self, now: float) -> float:
        """Planned green left on the current approach (0 when not green)."""
        if self.stage is not Stage.GREEN:
            return 0.0
        return max(0.0, self.stage_dur - (now - self.stage_start))

    # ------------------------------------------------------------------ tick
    def tick(self, now: float) -> None:
        self._refresh(now)
        target = self._choose_target(now)
        if target != self.preempt_target:
            self._set_target(target, now)

        elapsed = now - self.stage_start
        if self.stage is Stage.GREEN:
            cut = target is not None and target != self.cur and elapsed >= self.cfg.min_green_s
            expired = target is None and elapsed >= self.stage_dur and not self._extend(elapsed, now)
            gap = target is None and not expired and self._gap_out(elapsed)
            if gap:
                self._emit("green_ended_early", approach=self.cur, after_s=round(elapsed, 1),
                           planned_s=round(self.stage_dur, 1))
            if cut or expired or gap:
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

    def _gap_out(self, elapsed: float) -> bool:
        if not self.cfg.gap_out or self.cur is None or elapsed < self.cfg.gap_out_min_green_s:
            return False
        if self.vehicles.get(self.cur, 0) > 0:
            return False
        return any(self.vehicles.get(a, 0) > 0 for a in self.approaches if a != self.cur)

    def _extend(self, elapsed: float, now: float) -> bool:
        """Keep a base-controller green past its planned length while its approach is still the busiest
        (actuated-style), bounded by extend_max_green_s and by how long the others have waited."""
        c = self.cfg
        if not c.extend or self.cur is None or self.recovering or self._source != "base":
            return False
        if elapsed >= c.extend_max_green_s:
            return False
        mine = self.vehicles.get(self.cur, 0)
        others = [a for a in self.approaches if a != self.cur]
        if mine <= 0 or mine < c.extend_ratio * max((self.vehicles.get(a, 0) for a in others), default=0):
            return False
        if any(self.vehicles.get(a, 0) > 0 and self._waiting(a, now) >= c.extend_wait_cap_s for a in others):
            return False
        if not self._extended:
            self._extended = True
            self.stats.extensions += 1
            self._emit("green_extended", approach=self.cur, planned_s=round(self.stage_dur, 1), vehicles=mine)
        return True

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
        if self.served and self.cfg.recovery:
            extra = min(self.cfg.recovery_max_s, self.cfg.recovery_factor * dur)
            others = sorted((a for a in self.approaches if a not in self.served),
                            key=lambda a: (-self._waiting(a, now), -self.vehicles.get(a, 0)))
            qmax = max((self.vehicles.get(a, 0) for a in others), default=0)
            w = min(1.0, max(0.0, self.cfg.recovery_queue_weight))

            def extra_for(a: str) -> float:
                share = self.vehicles.get(a, 0) / qmax if qmax > 0 else 1.0
                return extra * ((1 - w) + w * share)

            if self.cfg.recovery_mode == "order" and qmax > 0:
                # only re-order: the delayed approaches that have a queue go first, longest wait first, but each
                # green's length is left to the base controller, decided when that green starts (None = undecided)
                self.recovery_plan = [(a, None) for a in others if self.vehicles.get(a, 0) > 0]
            elif self.cfg.recovery_mode == "queue" and qmax > 0:
                # serve the delayed approaches that actually have a queue, longest wait first, each for about as
                # long as its queue needs to clear (bounded below by the gap-out minimum, above by green + max extra)
                lo = self.cfg.gap_out_min_green_s
                hi = self.timing.green_s + self.cfg.recovery_max_s
                self.recovery_plan = [(a, min(hi, max(lo, self.cfg.recovery_headway_s * self.vehicles.get(a, 0)
                                                      + extra_for(a))))
                                      for a in others if self.vehicles.get(a, 0) > 0]
            else:    # no queue information (or "fixed" mode): the Iteration 2 v1 rule
                self.recovery_plan = [(a, self.timing.green_s + extra_for(a)) for a in others]
            if self.recovery_plan:
                self._emit("recovery_planned", plan=[a for a, _ in self.recovery_plan],
                           extra_green_s=round(extra, 1),
                           greens_s={a: (round(d, 1) if d is not None else None) for a, d in self.recovery_plan},
                           queues={a: self.vehicles.get(a, 0) for a in others})
        if self.stage is Stage.GREEN and self.cur in self.served:
            self.stage_dur = 0.0  # release the junction right away
        self.preempt_started = None
        self.served = set()

    def _next_approach(self, now: float) -> tuple[str, float, str]:
        if self.preempt_target:
            return self.preempt_target, self.timing.green_s, "preempt"
        while self.recovery_plan:
            a, d = self.recovery_plan.pop(0)
            if d is None:                         # "order" mode: base controller sizes the green, now
                if self.vehicles.get(a, 0) <= 0:
                    continue                      # its queue cleared meanwhile: nothing to recover
                ctx = self._context(now, self.cur)
                ctx.approaches = (a,)
                d = self.base.next_phase(ctx).green_s
            return a, d, "recovery"
        a, d = self._decide(now, self.cur)
        return a, d, "base"

    def _start_green(self, a: str, dur: float, source: str, now: float) -> None:
        self.stage = Stage.GREEN
        self.cur = a
        self.stage_start = now
        self.stage_dur = dur
        self.recovering = source == "recovery"
        self._source = source
        self._extended = False
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
