"""Base (non-emergency) controllers.

A base controller only answers one question: "who gets the next green, and for
how long?". Emergency preemption, yellow/all-red safety timing and fair recovery
live in IntersectionController and sit on top of whichever base controller is
configured. To add the MARL agent (Phase 3), implement BaseController and
register it in REGISTRY."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import Context, Decision, Timing


class BaseController(ABC):
    name = "base"

    @abstractmethod
    def next_phase(self, ctx: Context) -> Decision: ...


def _rotated_after(order: tuple[str, ...], current: str | None) -> list[str]:
    if current in order:
        i = order.index(current)
        return list(order[i + 1:] + order[: i + 1])
    return list(order)


class FixedTimeController(BaseController):
    """Classic cycle N -> E -> S -> W with a constant green. The Phase 1 baseline."""
    name = "fixed_time"

    def __init__(self, timing: Timing, **_):
        self.timing = timing

    def next_phase(self, ctx: Context) -> Decision:
        return Decision(_rotated_after(ctx.approaches, ctx.current)[0], self.timing.green_s)


class AdaptiveController(BaseController):
    """Vehicle-count driven: serves the busiest approach, green length grows with
    the number of vehicles, and a hard maximum-waiting-time bound guarantees no
    approach starves (the same idea as the roadmap's W_max fairness bound)."""
    name = "adaptive"

    def __init__(self, timing: Timing, min_green_s: float = 8, max_green_s: float = 30,
                 per_vehicle_s: float = 1.5, max_wait_s: float = 90, wait_weight: float = 0.1, **_):
        self.timing = timing
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.per_vehicle_s = per_vehicle_s
        self.max_wait_s = max_wait_s
        self.wait_weight = wait_weight

    def next_phase(self, ctx: Context) -> Decision:
        rot = _rotated_after(ctx.approaches, ctx.current)
        cands = rot[:-1] if ctx.current in ctx.approaches and len(rot) > 1 else rot
        starved = [a for a in cands if ctx.waiting_s.get(a, 0.0) >= self.max_wait_s]
        if starved:
            pick = max(starved, key=lambda a: ctx.waiting_s[a])
        else:
            # max() keeps the first of equal scores, and `cands` starts right after the
            # current approach, so ties fall back to round-robin.
            pick = max(cands, key=lambda a: ctx.vehicles.get(a, 0) + self.wait_weight * ctx.waiting_s.get(a, 0.0))
        green = self.min_green_s + self.per_vehicle_s * ctx.vehicles.get(pick, 0)
        return Decision(pick, max(self.min_green_s, min(self.max_green_s, green)))


REGISTRY: dict[str, type[BaseController]] = {
    "fixed_time": FixedTimeController,
    "adaptive": AdaptiveController,
    # "marl": MarlController,   # Phase 3
}


def create_base(name: str, timing: Timing, params: dict | None = None) -> BaseController:
    if name not in REGISTRY:
        raise ValueError(f"unknown controller '{name}'. Available: {sorted(REGISTRY)}")
    return REGISTRY[name](timing, **(params or {}))
