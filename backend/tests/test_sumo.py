"""SUMO live view: geometry, signal groups and a short headless run of the EquiFlow controller.
Skipped when SUMO (SUMO_HOME or pip install eclipse-sumo) is not available."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bus import EventBus  # noqa: E402
from app.config import AppConfig, SumoCfg  # noqa: E402
from app.sumo_live import SUMO_DIR, SumoLive, _control_groups, _green_phases, build_geometry  # noqa: E402

NET = SUMO_DIR / "networks" / "cross_signal_fixed.net.xml"
ROU = SUMO_DIR / "routes" / "cross_signal_high.rou.xml"
sumo_ok = SumoLive(AppConfig(), EventBus()).available and NET.is_file() and ROU.is_file()
needs_sumo = pytest.mark.skipif(not sumo_ok, reason="SUMO or the built networks are not available")


@needs_sumo
def test_geometry_names_the_four_approaches():
    g = build_geometry(NET)
    (tls,) = g["tls"]
    assert sorted(a["id"] for a in tls["approaches"]) == ["East", "North", "South", "West"]
    assert all(a["links"] and a["lanes"] for a in tls["approaches"])


@needs_sumo
def test_phases_pair_opposite_approaches_and_every_approach_has_an_ambulance_phase():
    g = build_geometry(NET)
    (tls,) = g["tls"]
    groups, amb = _control_groups(tls, _green_phases(NET)["C"], "phases")
    assert sorted(sorted(p["approaches"]) for p in groups) == [["East", "West"], ["North", "South"]]
    assert set(amb) == {"North", "East", "South", "West"}
    assert amb["North"] == amb["South"] != amb["East"]
    one, amb1 = _control_groups(tls, [], "approach")
    assert len(one) == 4 and amb1["West"] == "West"


@needs_sumo
def test_headless_run_gives_ambulances_priority_safely():
    cfg = AppConfig(sumo=SumoCfg(controller_params={"min_green_s": 6, "max_green_s": 30, "per_vehicle_s": 1.0}))
    sim = SumoLive(cfg, EventBus(history=50))
    sim.headless, sim.step_override, sim.end_s = True, 1.0, 900
    sim.run = {"network": "cross_signal", "scenario": "high", "controller": "equiflow", "seed": 1, "speed": 1.0}
    sim._worker(NET, ROU, build_geometry(NET), dict(sim.run), sim._stop)
    assert sim.state == "finished", sim.error
    (ctrl,) = sim._ctrls.values()
    assert ctrl.stats.preemptions >= 1                      # ambulances in the first 15 minutes were served
    assert max(ctrl.stats.latencies_s) <= 10                # min green 3 s + yellow 3 s + all-red 2 s, plus a step
    types = [e["type"] for e in sim.events]
    assert "ambulance_detected" in types and "preempt_green" in types


@needs_sumo
def test_green_corridor_and_camera_noise_on_the_sector_grid():
    net = SUMO_DIR / "networks" / "sector_grid_fixed.net.xml"
    rou = SUMO_DIR / "routes" / "sector_grid_high.rou.xml"
    cfg = AppConfig(sumo=SumoCfg(controller_params={"min_green_s": 6, "max_green_s": 30, "per_vehicle_s": 1.0},
                                 corridor=True, camera_fp_prob=0.4))
    sim = SumoLive(cfg, EventBus(history=50))
    sim.headless, sim.step_override, sim.end_s = True, 1.0, 1200
    sim.run = {"network": "sector_grid", "scenario": "high", "controller": "equiflow", "seed": 1, "speed": 1.0}
    sim._worker(net, rou, build_geometry(net), dict(sim.run), sim._stop)
    assert sim.state == "finished", sim.error
    assert sim.corridor_requests >= 1                              # signals ahead were told the ambulance is coming
    assert sum(c.false_confirms for c in sim._cams.values()) >= 1  # a very noisy classifier does cause false priority


@needs_sumo
def test_tc10_same_seed_and_config_gives_identical_results(tmp_path):
    """TC-10: a repeated run with the same seed and configuration reproduces its results, and another
    seed changes them (so the seed really is used)."""
    sys.path.insert(0, str(SUMO_DIR))
    import run_equiflow as rq
    runs = []
    for seed in (4, 4, 5):
        d = tmp_path / f"r{len(runs)}"
        d.mkdir()
        rows, st = rq.simulate("cross_signal", "high", seed, quiet=True, trip_dir=d, end_s=600, label="tc10")
        runs.append(([(r["vehicle_type"], r["completed"], r["mean_waiting_s"], r["mean_time_loss_s"]) for r in rows],
                     st["fairness"], st["priority_runs"]))
    assert runs[0] == runs[1]
    assert runs[0] != runs[2]
