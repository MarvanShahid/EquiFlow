"""Shared types for signal control. Pure Python (no web / ML deps) so the same
code can later be driven by SUMO/TraCI or a MARL training loop (Phases 1, 3, 4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

APPROACHES: tuple[str, ...] = ("North", "East", "South", "West")


class Lamp(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class Stage(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"


class Mode(str, Enum):
    NORMAL = "NORMAL"      # base controller is in charge
    PREEMPT = "PREEMPT"    # ambulance has priority
    RECOVERY = "RECOVERY"  # fair recovery for approaches that waited during preemption


@dataclass
class Timing:
    green_s: float = 15.0
    yellow_s: float = 3.0
    all_red_s: float = 2.0


@dataclass
class PreemptConfig:
    min_green_s: float = 3.0        # a green must have been shown this long before it can be cut
    clear_hold_s: float = 4.0       # ambulance counts as present this long after the last detection
    max_preempt_s: float = 60.0     # fail-safe: a stuck/false detection cannot hold the junction forever
    recovery_factor: float = 0.5    # extra green per second of preemption, given to approaches that waited
    recovery_max_s: float = 15.0    # cap on that extra green
    recovery: bool = True           # False = no fair recovery (back to the base controller at once). The app
                                    # config (config.py PreemptCfg) switches it off by default since Iteration 2b
    recovery_queue_weight: float = 0.5   # 0 = every waiting approach gets the same extra green; 1 = all of it
                                         # in proportion to its queue (FR-10: recovery uses queue length too)
    recovery_mode: str = "queue"    # "order": delayed approaches with a queue go first (longest wait first), but the
                                    # base controller sizes each green when it starts (re-order only);
                                    # "queue": green sized to each queue (headway x vehicles), empty approaches
                                    # skipped; "fixed": every waiting approach gets green_s + extra (Iteration 2 v1)
    recovery_headway_s: float = 2.0 # seconds of green per queued vehicle in "queue" mode
    gap_out: bool = True            # FR-07: end a green early when its approach is empty and another has demand
    gap_out_min_green_s: float = 5.0     # ... but never before this much green (and never during priority)
    stale_s: float = 2.0            # FR-05: external detection events older than this are rejected
    # actuated-style extension: a base-controller green that reaches its planned length keeps going while its
    # approach is still at least `extend_ratio` x as busy as every other one, up to extend_max_green_s, and
    # only while no other approach with a queue has waited extend_wait_cap_s. Never during priority/recovery.
    extend: bool = True
    extend_max_green_s: float = 45.0
    extend_ratio: float = 1.0
    extend_wait_cap_s: float = 30.0


@dataclass
class Context:
    """What a base controller sees when it must choose the next green."""
    now: float
    current: str | None                 # approach that just finished its green
    approaches: tuple[str, ...]
    vehicles: dict[str, int]
    waiting_s: dict[str, float]


@dataclass
class Decision:
    approach: str
    green_s: float


@dataclass
class Stats:
    preemptions: int = 0
    total_preempt_s: float = 0.0
    latencies_s: list[float] = field(default_factory=list)  # detection -> green for the ambulance
    extensions: int = 0                                      # greens kept past their planned length

    def to_dict(self) -> dict:
        lat = self.latencies_s
        return {
            "preemptions": self.preemptions,
            "total_preempt_s": round(self.total_preempt_s, 2),
            "latency_last_s": round(lat[-1], 2) if lat else None,
            "latency_avg_s": round(sum(lat) / len(lat), 2) if lat else None,
            "latency_max_s": round(max(lat), 2) if lat else None,
            "extensions": self.extensions,
        }


Emit = Callable[..., None]  # emit(type, **data)
