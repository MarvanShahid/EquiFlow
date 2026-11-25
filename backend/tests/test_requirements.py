"""Tests named after the mid-report requirements / test cases that had no automated check yet:
TC-03 (stale detection), TC-04 / FR-07 (empty green ends early, only when safe),
FR-10 (recovery uses queue length), and the no-recovery switch used for the ablation."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.controllers import FixedTimeController, IntersectionController, PreemptConfig, Timing  # noqa: E402
from test_controller import DT, T, green, run  # noqa: E402

P = dict(min_green_s=3, clear_hold_s=4, max_preempt_s=30, recovery_factor=0.5, recovery_max_s=10)


def make(**over):
    ev = []
    ctl = IntersectionController("J1", FixedTimeController(T), T, PreemptConfig(**{**P, **over}),
                                 emit=lambda t, **kw: ev.append((t, kw)))
    return ctl, ev


# ------------------------------------------------------------------ TC-04 / FR-07 gap-out
def test_tc04_empty_green_ends_early_after_minimum_with_yellow_and_all_red():
    ctl, ev = make(gap_out=True, gap_out_min_green_s=5)
    first = ctl.cur
    ctl.vehicles.update({a: 0 for a in ctl.approaches})
    ctl.vehicles["South"] = 6                       # demand elsewhere, nothing on the green approach
    t = run(ctl, 0, 4.9)
    assert green(ctl) == [first], "must not cut before gap_out_min_green_s"
    while ctl.lamps()[first] == "green":
        t = run(ctl, t, DT)
    y0 = t
    assert ctl.lamps()[first] == "yellow" and y0 <= 5.2, (y0, ctl.lamps())
    early = [kw for k, kw in ev if k == "green_ended_early"]
    assert early and early[0]["approach"] == first and early[0]["after_s"] >= 5
    t = run(ctl, t, T.yellow_s - 2 * DT)
    assert ctl.lamps()[first] == "yellow"             # full yellow kept
    t = run(ctl, t, 3 * DT)
    assert all(lamp == "red" for lamp in ctl.lamps().values())   # then all-red
    t = run(ctl, t, T.all_red_s - 4 * DT)
    assert all(lamp == "red" for lamp in ctl.lamps().values())


def test_tc04_green_is_not_cut_when_nobody_else_waits_or_when_disabled():
    for over, others in (({"gap_out": True}, 0), ({"gap_out": False}, 5)):
        ctl, ev = make(gap_out_min_green_s=2, **over)
        first = ctl.cur
        ctl.vehicles.update({a: others for a in ctl.approaches})
        ctl.vehicles[first] = 0
        run(ctl, 0, T.green_s - 0.5)
        assert green(ctl) == [first], (over, ctl.lamps())
        assert not any(k == "green_ended_early" for k, _ in ev)


def test_tc04_priority_green_is_never_gapped_out():
    ctl, ev = make(gap_out=True, gap_out_min_green_s=2)
    ctl.vehicles.update({"North": 9, "East": 0, "South": 9, "West": 9})
    t = run(ctl, 0, 1)
    t = run(ctl, t, 25, lambda x: ctl.observe("East", True, x) if x < 22 else None)   # empty approach, ambulance
    assert not any(k == "green_ended_early" and kw["approach"] == "East" for k, kw in ev)


# ------------------------------------------------------------------ FR-10 queue-aware recovery
def test_fr10_fixed_mode_recovery_gives_more_extra_green_to_longer_queues():
    ctl, ev = make(recovery_mode="fixed", recovery_queue_weight=1.0, gap_out=False)
    ctl.vehicles.update({"North": 2, "East": 0, "South": 10, "West": 5})
    t = run(ctl, 0, 1)
    run(ctl, t, 26, lambda x: ctl.observe("East", True, x) if x < 20 else None)
    plan = next(kw for k, kw in ev if k == "recovery_planned")
    g = plan["greens_s"]
    assert g["South"] > g["West"] > g["North"] >= T.green_s, g
    assert abs(g["South"] - (T.green_s + plan["extra_green_s"])) < 0.05     # longest queue gets all of it


def test_fr10_queue_mode_sizes_greens_to_queues_and_skips_empty_approaches():
    ctl, ev = make(recovery_mode="queue", recovery_headway_s=2.0, gap_out=False, gap_out_min_green_s=5)
    ctl.vehicles.update({"North": 0, "East": 0, "South": 9, "West": 3})
    t = run(ctl, 0, 1)
    t = run(ctl, t, 26, lambda x: ctl.observe("East", True, x) if x < 20 else None)
    plan = next(kw for k, kw in ev if k == "recovery_planned")
    g = plan["greens_s"]
    assert "North" not in g and "East" not in g, g          # empty approach skipped, ambulance approach served
    assert g["South"] > g["West"] >= 5, g                    # longer queue, longer green; never below the minimum
    assert g["South"] <= T.green_s + P["recovery_max_s"]
    run(ctl, t, 80)
    rec = [kw["approach"] for k, kw in ev if k == "phase_changed" and kw["source"] == "recovery"]
    assert rec and set(rec) <= {"South", "West"}


def test_recovery_off_goes_straight_back_to_the_base_controller():
    ctl, ev = make(recovery=False)
    t = run(ctl, 0, 1)
    run(ctl, t, 60, lambda x: ctl.observe("East", True, x) if x < 15 else None)
    kinds = [k for k, _ in ev]
    assert "preempt_ended" in kinds and "recovery_planned" not in kinds
    assert not any(k == "phase_changed" and kw["source"] == "recovery" for k, kw in ev)


# ------------------------------------------------------------------ TC-03 / FR-05 stale events
def test_tc03_stale_or_future_external_event_is_rejected_and_logged():
    from app.bus import EventBus
    from app.config import AppConfig, IntersectionCfg, SimCfg
    from app.runtime import Runtime
    cfg = AppConfig(mode="sim", controller="fixed_time", sim=SimCfg(auto_ambulance=False),
                    intersections=[IntersectionCfg(id="J1")])
    bus = EventBus()
    rt = Runtime(cfg, bus)          # not started: ingest works on the controller directly
    j = rt.get("J1")
    assert j.ingest("West", True, 5, 0.9, 0.5, 0.5, ts=time.time() - 10) is False      # replayed old event
    assert j.ingest("West", True, 5, 0.9, 0.5, 0.5, ts=time.time() + 30) is False      # clock skew
    rej = [e for e in bus.recent(50) if e["type"] == "stale_event_rejected"]
    assert len(rej) == 2 and rej[-1]["age_s"] >= 9                # newest first
    assert not j.controller.is_ambulance_active("West", time.monotonic())
    assert not any(e["type"] == "ambulance_detected" for e in bus.recent(50))
    assert j.ingest("West", True, 5, 0.9, 0.5, 0.5, ts=time.time()) is True            # fresh: accepted
    assert any(e["type"] == "ambulance_detected" for e in bus.recent(50))


def test_tc03_detection_that_stops_expires_within_clear_hold():
    ctl, ev = make()
    t = run(ctl, 0, 1)
    ctl.observe("West", True, t)
    assert ctl.is_ambulance_active("West", t)
    assert not ctl.is_ambulance_active("West", t + P["clear_hold_s"] + DT)


# ------------------------------------------------------------------ green extension (heavy traffic, Iteration 2b)
EXT = dict(extend=True, extend_max_green_s=25, extend_ratio=1.0, extend_wait_cap_s=60, gap_out=False)


def _green_length(ctl, t, limit=120):
    """run until the current green ends; return (approach, seconds of green)"""
    a, t0 = ctl.cur, t
    while ctl.lamps().get(a) == "green" and t - t0 < limit:
        t = run(ctl, t, DT)
    return a, t - t0, t


def test_extension_keeps_the_busiest_green_up_to_its_maximum():
    ctl, ev = make(**EXT)
    first = ctl.cur
    ctl.vehicles.update({a: 2 for a in ctl.approaches})
    ctl.vehicles[first] = 9                         # still the busiest when the planned green ends
    a, g, _ = _green_length(ctl, 0)
    assert a == first and abs(g - EXT["extend_max_green_s"]) <= 2 * DT, g
    assert [kw for k, kw in ev if k == "green_extended"] and ctl.stats.extensions == 1


def test_extension_stops_when_another_approach_is_busier_or_has_waited_too_long():
    ctl, _ = make(**EXT)
    first = ctl.cur
    ctl.vehicles.update({a: 9 for a in ctl.approaches})
    ctl.vehicles[first] = 3                         # not the busiest: no extension
    a, g, _ = _green_length(ctl, 0)
    assert abs(g - T.green_s) <= 2 * DT, g

    ctl, _ = make(**{**EXT, "extend_max_green_s": 120, "extend_wait_cap_s": 20})
    first = ctl.cur
    ctl.vehicles.update({a: 1 for a in ctl.approaches})
    ctl.vehicles[first] = 9                         # busiest, but the others' wait reaches the cap
    a, g, _ = _green_length(ctl, 0)
    assert T.green_s < g <= 20 + 2 * DT, g


def test_extension_off_or_during_priority_and_recovery_changes_nothing():
    ctl, ev = make(**{**EXT, "extend": False})
    first = ctl.cur
    ctl.vehicles.update({a: 1 for a in ctl.approaches})
    ctl.vehicles[first] = 9
    _, g, _ = _green_length(ctl, 0)
    assert abs(g - T.green_s) <= 2 * DT and not any(k == "green_extended" for k, _ in ev)

    ctl, ev = make(**EXT)
    ctl.vehicles.update({"North": 9, "East": 9, "South": 1, "West": 1})
    t = run(ctl, 0, 30, lambda x: ctl.observe("East", True, x) if x < 20 else None)   # ambulance on East
    t = run(ctl, t, 60)                                                               # recovery greens follow
    rec = [kw for k, kw in ev if k == "phase_changed" and kw["source"] == "recovery"]
    assert rec, "expected recovery greens"
    assert not any(k == "green_extended" and kw["approach"] == "East" and kw["planned_s"] > T.green_s
                   for k, kw in ev)
    for k, kw in ev:                                      # an extension is only ever of a base green
        if k == "green_extended":
            assert kw["planned_s"] <= T.green_s + 0.1


def test_fr10_order_mode_only_reorders_and_lets_the_base_controller_size_greens():
    ctl, ev = make(recovery_mode="order", gap_out=False, extend=False)
    ctl.vehicles.update({"North": 0, "East": 0, "South": 9, "West": 3})
    t = run(ctl, 0, 1)
    t = run(ctl, t, 26, lambda x: ctl.observe("East", True, x) if x < 20 else None)
    plan = next(kw for k, kw in ev if k == "recovery_planned")
    assert set(plan["plan"]) == {"South", "West"}, plan            # empty approaches skipped
    assert all(v is None for v in plan["greens_s"].values())        # lengths not fixed by recovery
    run(ctl, t, 80)
    rec = [kw for k, kw in ev if k == "phase_changed" and kw["source"] == "recovery"]
    assert [kw["approach"] for kw in rec][:1] in (["South"], ["West"])
    assert all(abs(kw["green_s"] - T.green_s) < 0.05 for kw in rec)  # FixedTime base: its own green length


def test_fr10_order_mode_skips_an_approach_whose_queue_cleared():
    ctl, ev = make(recovery_mode="order", gap_out=False, extend=False)
    ctl.vehicles.update({"North": 4, "East": 0, "South": 4, "West": 4})
    t = run(ctl, 0, 1)
    t = run(ctl, t, 26, lambda x: ctl.observe("East", True, x) if x < 20 else None)
    ctl.vehicles.update({"North": 0, "South": 0, "West": 0})     # queues gone before their turn
    run(ctl, t, 60)
    assert not any(k == "phase_changed" and kw["source"] == "recovery" for k, kw in ev)
