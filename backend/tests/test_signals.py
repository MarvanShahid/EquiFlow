"""Signal output (app/signals/): conflict monitor rules, fail-safe latch, operator reset, fault injection, and the
real controller driving a simulated field controller without ever tripping the monitor."""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.controllers import AdaptiveController, IntersectionController, PreemptConfig, Timing  # noqa: E402
from app.signals import ConflictMonitor, MonitorConfig, SignalOutput, SimulatedController  # noqa: E402

A = ("North", "East", "South", "West")
T = Timing(green_s=10, yellow_s=3, all_red_s=2)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(latency=0.05):
    clk = Clock()
    drv = SimulatedController(A, latency_s=latency, clock=clk)
    mon = ConflictMonitor(A, MonitorConfig(yellow_s=T.yellow_s, all_red_s=T.all_red_s, min_green_s=1.0,
                                           watchdog_s=1.0, mismatch_s=0.5, tolerance_s=0.15))
    ev = []
    out = SignalOutput("J1", A, drv, mon, emit=lambda t, **kw: ev.append((t, kw)))
    return out, drv, clk, ev


def lamps(**on):
    d = {a: "red" for a in A}
    d.update(on)
    return d


def step(out, clk, lam, until, dt=0.1):
    while clk.t < until - 1e-9:
        clk.t = round(clk.t + dt, 6)
        out.apply(lam, clk.t)


def test_normal_cycle_passes_and_reaches_the_hardware():
    out, drv, clk, _ = make()
    step(out, clk, lamps(North="green"), 10)
    step(out, clk, lamps(North="yellow"), 13)
    step(out, clk, lamps(), 15)
    step(out, clk, lamps(East="green"), 20)
    assert not out.flashing and out.status()["faults_total"] == 0
    assert drv.read() == lamps(East="green")


def test_conflicting_greens_latch_flash():
    out, drv, clk, ev = make()
    step(out, clk, lamps(North="green"), 5)
    out.apply(lamps(North="green", South="green"), 5.1)
    assert out.flashing and out.fault.kind == "conflict"
    assert drv.flashing and drv.read() == lamps()
    out.apply(lamps(North="green"), 5.2)                      # latched: nothing reaches the hardware any more
    assert out.flashing and drv.read() == lamps()
    assert ev[-1][0] == "signal_fault"


def test_skipped_or_short_yellow_and_short_all_red_are_faults():
    out, _, clk, _ = make()
    step(out, clk, lamps(North="green"), 5)
    out.apply(lamps(), 5.1)
    assert out.fault.kind == "no_yellow"

    out, _, clk, _ = make()
    step(out, clk, lamps(North="green"), 5)
    step(out, clk, lamps(North="yellow"), 6)                  # 1 s of yellow < 3 s
    out.apply(lamps(), 6.1)
    assert out.fault.kind == "short_yellow"

    out, _, clk, _ = make()
    step(out, clk, lamps(North="green"), 5)
    step(out, clk, lamps(North="yellow"), 8)
    step(out, clk, lamps(), 8.5)                              # 0.5 s all-red < 2 s
    out.apply(lamps(East="green"), 8.6)
    assert out.fault.kind == "short_all_red"


def test_flicker_green_is_a_fault():
    out, _, clk, _ = make()
    step(out, clk, lamps(North="green"), 0.3)
    out.apply(lamps(North="yellow"), 0.4)
    assert out.fault.kind == "short_green"


def test_watchdog_trips_when_commands_stop():
    out, _, clk, _ = make()
    step(out, clk, lamps(North="green"), 3)
    out.poll(3.9)
    assert not out.flashing
    out.poll(4.2)                                             # last command at 3.0, watchdog 1.0 s
    assert out.flashing and out.fault.kind == "watchdog"


def test_stuck_lamp_is_detected_and_reset_is_refused_until_it_is_fixed():
    out, drv, clk, _ = make()
    step(out, clk, lamps(North="green"), 5)
    drv.stuck["East"] = "green"                               # a load switch welded on
    step(out, clk, lamps(North="green"), 6)
    assert out.flashing and out.fault.kind == "mismatch"
    ok, msg = out.reset(6.5)
    assert not ok and out.flashing, msg
    drv.stuck.clear()
    ok, msg = out.reset(7.0)
    assert ok and not out.flashing, msg
    step(out, clk, lamps(), 9.1)                              # restarts from all-red
    step(out, clk, lamps(North="green"), 12)
    assert not out.flashing and drv.read() == lamps(North="green")


def test_lost_link_is_detected_and_blocks_reset():
    out, drv, clk, _ = make()
    step(out, clk, lamps(North="green"), 10)
    step(out, clk, lamps(North="yellow"), 13)
    drv.link_down = True
    step(out, clk, lamps(), 14)                               # command lost: hardware still shows yellow
    assert out.flashing and out.fault.kind == "mismatch"
    ok, _ = out.reset(14.5)
    assert not ok
    drv.link_down = False
    assert out.reset(15.0)[0]


def test_real_controller_never_trips_the_monitor():
    """Randomised traffic and ambulances for one simulated hour, through the full output chain."""
    rng = random.Random(7)
    out, drv, clk, _ = make(latency=0.08)
    ctl = IntersectionController("J1", AdaptiveController(T), T, PreemptConfig(), approaches=A, now=0.0)
    amb_until = {a: -1.0 for a in A}
    while clk.t < 3600:
        clk.t = round(clk.t + 0.1, 6)
        if rng.random() < 0.002:
            amb_until[rng.choice(A)] = clk.t + rng.uniform(3, 25)
        for a in A:
            ctl.observe(a, clk.t < amb_until[a], clk.t, vehicles=rng.randint(0, 12))
        ctl.tick(clk.t)
        out.apply(ctl.lamps(), clk.t)
    st = out.status()
    assert st["faults_total"] == 0, st
    assert ctl.stats.preemptions > 5 and st["commands"] > 30000


def test_runtime_sends_every_tick_through_the_output():
    from app.bus import EventBus
    from app.config import AppConfig, IntersectionCfg, SimCfg
    from app.runtime import Runtime
    cfg = AppConfig(mode="sim", controller="fixed_time", sim=SimCfg(auto_ambulance=False),
                    intersections=[IntersectionCfg(id="J1", name="Test")])
    cfg.output.driver = "simulated"
    cfg.timing.green_s, cfg.timing.yellow_s, cfg.timing.all_red_s = 2, 1, 1
    rt = Runtime(cfg, EventBus())
    rt.start()
    try:
        time.sleep(4.5)                                       # a full green / yellow / all-red cycle and more
        st = rt.get("J1").snapshot()["output"]
    finally:
        rt.stop()
    assert st["driver"]["driver"] == "simulated" and st["commands"] > 20
    assert not st["flashing"] and st["faults_total"] == 0, st
