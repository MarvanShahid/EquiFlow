"""MARL base controller: decisions, the fairness guard, learning updates, save/load."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.controllers import create_base  # noqa: E402
from app.controllers.marl import DURATIONS, Learner, MarlController, QNet  # noqa: E402
from app.controllers.types import Context, Timing  # noqa: E402

G = ("North + South", "East + West", "Turns")


def ctx(veh, wait, current=None):
    return Context(now=100.0, current=current, approaches=G, vehicles=dict(zip(G, veh)), waiting_s=dict(zip(G, wait)))


def test_untrained_falls_back_to_adaptive():
    c = create_base("marl", Timing(), {"weights": "does/not/exist.npz"})
    d = c.next_phase(ctx([2, 9, 0], [10, 20, 5], current="North + South"))
    assert d.approach == "East + West" and "untrained" in c.name


def test_decision_is_valid_and_never_repeats_the_current_green():
    c = MarlController(Timing(), learner=Learner(QNet(seed=1), epsilon=0.0))
    for k in range(20):
        cur = G[k % 3]
        d = c.next_phase(ctx([k % 5, 3, 1], [5, 30, 2], current=cur))
        assert d.approach in G and d.approach != cur and d.green_s in DURATIONS


def test_fairness_guard_serves_a_starved_group_whatever_the_network_says():
    c = MarlController(Timing(), learner=Learner(QNet(seed=2), epsilon=0.0), max_wait_s=90)
    d = c.next_phase(ctx([30, 0, 0], [0, 10, 95], current="East + West"))
    assert d.approach == "Turns"


def test_learning_stores_transitions_and_updates(tmp_path):
    net = QNet(seed=3)
    learner = Learner(net, batch=16, epsilon=0.5)
    c = MarlController(Timing(), learner=learner, seed=3)
    rng = np.random.default_rng(0)
    for _ in range(400):
        c.accumulate(int(rng.integers(0, 10)), float(rng.uniform(0, 80)), 15.0)
        c.next_phase(ctx(list(rng.integers(0, 15, 3)), list(rng.uniform(0, 80, 3)), current=G[int(rng.integers(0, 3))]))
    assert len(learner.buf) == 399 and learner.updates > 0
    path = tmp_path / "w.npz"
    net.save(path, episodes=7)
    loaded, meta = QNet.load(path)
    x = np.random.default_rng(1).random((5, net.p["W1"].shape[0]))
    assert np.allclose(loaded.forward(x), net.forward(x)) and int(meta["episodes"]) == 7
    trained = create_base("marl", Timing(), {"weights": str(path)})
    assert trained.name == "marl" and trained.next_phase(ctx([1, 8, 0], [5, 40, 0], current="Turns")).approach in G
