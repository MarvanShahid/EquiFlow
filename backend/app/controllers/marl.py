"""Fairness-aware multi-agent RL base controller (Phase 3).

Each signalised junction is one agent. All agents share one Q-network (parameter sharing), which
scores every candidate action (serve signal group g for d seconds) from features of that
candidate, so the same network works for junctions with 2, 3 or more phases.

  state/action features: queue on g, how long g has waited, the rest of the junction's queue and
  its longest wait, whether g just had green, the green length d, ...
  reward (between two decisions): -(halting vehicles x seconds) - a fairness penalty that grows
  with the longest wait at the junction beyond 45 s - (halted vehicles that have already waited more
  than 20 s x seconds), which aims the policy at the 95th-percentile wait
  guard: an approach that has waited max_wait_s (90 s) is served next, whatever the network says

It only answers "who gets the next green, and for how long". Ambulance preemption, yellow/all-red
and fair recovery stay in IntersectionController, on top of it, unchanged.

Pure numpy (no torch): a 2-layer MLP, Adam, experience replay and a target network.
Train with marl/train_marl.py; weights are an .npz file."""
from __future__ import annotations

import logging
import math
import random
from collections import deque
from pathlib import Path

import numpy as np

from .base import AdaptiveController, BaseController
from .types import Context, Decision, Timing

log = logging.getLogger("equiflow.marl")
DURATIONS = (8.0, 15.0, 25.0)
N_FEAT = 11


def features(ctx: Context, group: str, dur: float) -> list[float]:
    veh, wait = ctx.vehicles, ctx.waiting_s
    tot = float(sum(veh.values()))
    mw = max(wait.values()) if wait else 0.0
    v, w = float(veh.get(group, 0)), float(wait.get(group, 0.0))
    return [
        v / 20.0, w / 90.0, (tot - v) / 40.0, mw / 90.0,
        1.0 if group == ctx.current else 0.0,
        dur / 25.0, (v / 20.0) * (dur / 25.0), (tot - v) / 40.0 * (dur / 25.0),
        1.0 if w >= mw - 1e-6 else 0.0, len(ctx.approaches) / 6.0, 1.0,
    ]


class QNet:
    def __init__(self, n_in: int = N_FEAT, hidden: int = 64, seed: int = 0):
        r = np.random.default_rng(seed)
        self.p = {
            "W1": r.normal(0, math.sqrt(2 / n_in), (n_in, hidden)), "b1": np.zeros(hidden),
            "W2": r.normal(0, math.sqrt(2 / hidden), (hidden, hidden)), "b2": np.zeros(hidden),
            "W3": r.normal(0, 0.05, (hidden, 1)), "b3": np.zeros(1),
        }
        self.m = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.v = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.t = 0

    def forward(self, X: np.ndarray, cache: bool = False):
        p = self.p
        z1 = X @ p["W1"] + p["b1"]
        h1 = np.maximum(z1, 0)
        z2 = h1 @ p["W2"] + p["b2"]
        h2 = np.maximum(z2, 0)
        q = (h2 @ p["W3"] + p["b3"])[:, 0]
        return (q, (X, z1, h1, z2, h2)) if cache else q

    def train_step(self, X: np.ndarray, target: np.ndarray, lr: float = 1e-3) -> float:
        q, (X, z1, h1, z2, h2) = self.forward(X, cache=True)
        err = q - target
        d = np.clip(err, -1.0, 1.0)[:, None] / len(X)          # Huber loss gradient
        p = self.p
        g = {"W3": h2.T @ d, "b3": d.sum(0)}
        dh2 = d @ p["W3"].T * (z2 > 0)
        g["W2"], g["b2"] = h1.T @ dh2, dh2.sum(0)
        dh1 = dh2 @ p["W2"].T * (z1 > 0)
        g["W1"], g["b1"] = X.T @ dh1, dh1.sum(0)
        self.t += 1
        for k in p:                                              # Adam
            self.m[k] = 0.9 * self.m[k] + 0.1 * g[k]
            self.v[k] = 0.999 * self.v[k] + 0.001 * g[k] ** 2
            mh = self.m[k] / (1 - 0.9 ** self.t)
            vh = self.v[k] / (1 - 0.999 ** self.t)
            p[k] -= lr * mh / (np.sqrt(vh) + 1e-8)
        return float(np.mean(err ** 2))

    def copy_from(self, other: "QNet") -> None:
        self.p = {k: v.copy() for k, v in other.p.items()}

    def save(self, path: Path, **meta) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **{f"p_{k}": v for k, v in self.p.items()}, **{f"m_{k}": v for k, v in self.m.items()},
                 **{f"v_{k}": v for k, v in self.v.items()}, t=self.t, **{f"meta_{k}": v for k, v in meta.items()})

    @classmethod
    def load(cls, path: Path) -> tuple["QNet", dict]:
        z = np.load(path)
        net = cls(z["p_W1"].shape[0], z["p_W1"].shape[1])
        for k in net.p:
            net.p[k] = z[f"p_{k}"]
            if f"m_{k}" in z:
                net.m[k], net.v[k] = z[f"m_{k}"], z[f"v_{k}"]
        net.t = int(z["t"]) if "t" in z else 0
        meta = {k[5:]: z[k].item() if z[k].shape == () else z[k] for k in z.files if k.startswith("meta_")}
        return net, meta


class Learner:
    """Shared DQN learner for all agents (semi-MDP: one transition per decision of a junction)."""

    def __init__(self, net: QNet, gamma: float = 0.95, buffer: int = 50000, batch: int = 64,
                 target_every: int = 400, lr: float = 5e-4, epsilon: float = 0.2, seed: int = 0,
                 updates_per_step: int = 4):
        self.net, self.target = net, QNet(net.p["W1"].shape[0], net.p["W1"].shape[1])
        self.target.copy_from(net)
        self.gamma, self.batch, self.target_every, self.lr = gamma, batch, target_every, lr
        self.epsilon = epsilon
        self.updates_per_step = updates_per_step
        self.buf: deque = deque(maxlen=buffer)
        self.rng = random.Random(seed)
        self.updates = 0
        self.losses: deque = deque(maxlen=500)
        self.rewards: deque = deque(maxlen=2000)

    def add(self, x: np.ndarray, r: float, dt: float, x_next: np.ndarray | None) -> None:
        self.buf.append((x, r, dt, x_next))
        self.rewards.append(r)
        if len(self.buf) >= max(self.batch * 4, 256):
            for _ in range(self.updates_per_step):
                self._update()

    def _update(self) -> None:
        batch = self.rng.sample(self.buf, self.batch)
        X = np.stack([b[0] for b in batch])
        y = np.empty(len(batch))
        for i, (_, r, dt, xn) in enumerate(batch):
            boot = 0.0
            if xn is not None:
                boot = float(self.target.forward(xn).max()) * self.gamma ** (dt / 15.0)
            y[i] = r + boot
        self.losses.append(self.net.train_step(X, y, self.lr))
        self.updates += 1
        if self.updates % self.target_every == 0:
            self.target.copy_from(self.net)


class MarlController(BaseController):
    name = "marl"

    def __init__(self, timing: Timing, weights: str = "", max_wait_s: float = 90, epsilon: float = 0.0,
                 learner: Learner | None = None, fairness_from_s: float = 45.0, fairness_weight: float = 0.5,
                 long_wait_s: float = 20.0, long_weight: float = 1.0, seed: int = 0, **_):
        self.timing = timing
        self.max_wait_s = max_wait_s
        self.learner = learner
        self.fair_from, self.fair_w = fairness_from_s, fairness_weight
        self.long_wait_s, self.long_w = long_wait_s, long_weight
        self.rng = random.Random(seed)
        self.fallback = None
        if learner is not None:
            self.net = learner.net
            self.epsilon = learner.epsilon
        else:
            self.epsilon = epsilon
            path = Path(weights) if weights else None
            if path is not None and path.is_file():
                self.net, _ = QNet.load(path)
            else:
                log.warning("MARL weights not found (%s): using the adaptive controller instead. "
                            "Train with marl/train_marl.py", weights)
                self.net = None
                self.fallback = AdaptiveController(timing, min_green_s=6, max_green_s=30, per_vehicle_s=1.0)
                self.name = "marl (untrained: adaptive)"
        self._pending: np.ndarray | None = None
        self._cost = 0.0
        self._since = 0.0

    # called every simulation step by the SUMO runner while learning
    def accumulate(self, halting: int, max_wait: float, dt: float, long_waiting: int = 0) -> None:
        """long_waiting: halted vehicles that have already waited more than long_wait_s (about the 95th
        percentile), each costing long_weight extra per second - aims the policy at the tail of the waits."""
        self._cost += (halting + self.fair_w * max(0.0, max_wait - self.fair_from) / 5.0
                       + self.long_w * long_waiting) * dt
        self._since += dt

    def next_phase(self, ctx: Context) -> Decision:
        if self.fallback is not None:
            return self.fallback.next_phase(ctx)
        groups = list(ctx.approaches)
        if ctx.current in groups and len(groups) > 1:
            groups.remove(ctx.current)               # a new green, not the same one again
        starved = [g for g in groups if ctx.waiting_s.get(g, 0.0) >= self.max_wait_s]
        if starved:                                   # hard fairness guard
            groups = [max(starved, key=lambda g: ctx.waiting_s[g])]
        cands = [(g, d) for g in groups for d in DURATIONS]
        X = np.asarray([features(ctx, g, d) for g, d in cands], dtype=float)
        if self.epsilon > 0 and self.rng.random() < self.epsilon:
            i = self.rng.randrange(len(cands))
        else:
            i = int(np.argmax(self.net.forward(X)))
        if self.learner is not None:
            if self._pending is not None:
                self.learner.add(self._pending, -self._cost / 100.0, max(self._since, 1.0), X)
            self._pending, self._cost, self._since = X[i], 0.0, 0.0
        g, d = cands[i]
        return Decision(g, d)
