"""Event log (app/eventlog.py), the preemption-episode table and the scripted Iteration 2 scenario."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bus import EventBus  # noqa: E402
from app.eventlog import EventLogger, episodes, read_log  # noqa: E402


def test_logger_writes_events_and_skips_excluded(tmp_path):
    bus = EventBus()
    log = EventLogger(tmp_path, filename="e.csv")
    bus.add_listener(log)
    bus.publish("phase_changed", intersection_id="J1", approach="North", source="base", green_s=15)
    bus.publish("ambulance_position", intersection_id="J1", approach="West", cx=0.5)
    bus.publish("corridor_request", origin="sumo", intersection_id="sumo/B1", approach="East", sim_time=12.0)
    log.close()
    rows = read_log(tmp_path / "e.csv")
    assert [r["type"] for r in rows] == ["phase_changed", "corridor_request"]
    assert rows[0]["data"] == {"source": "base", "green_s": 15}
    assert rows[1]["t"] == 12.0 and rows[1]["origin"] == "sumo"
    bus.publish("phase_changed", intersection_id="J1", approach="East")   # after close: ignored, no error


def _ev(t, type, a="West", iid="J1", **data):
    return {"ts": t, "t": t, "type": type, "intersection_id": iid, "approach": a, "data": data}


def test_episodes_follow_detection_green_end_recovery():
    rows = [
        _ev(0, "phase_changed", "North", source="base"),
        _ev(10, "ambulance_detected"),
        _ev(10.1, "preempt_started"),
        _ev(14, "preempt_green", latency_s=3.9),
        _ev(14, "phase_changed", source="preempt"),
        _ev(25, "preempt_ended", duration_s=14.9, served=["West"]),
        _ev(25, "recovery_planned", plan=["North", "East", "South"]),
        _ev(30, "phase_changed", "North", source="recovery"),
        _ev(48, "phase_changed", "East", source="recovery"),
        _ev(60, "manual_preempt", "South"),
        _ev(60, "preempt_started", "South"),
        _ev(61, "preempt_timeout", "South"),
    ]
    a, b = episodes(rows)
    assert a["trigger"] == "camera" and a["completed"] and a["ended_reason"] == "cleared"
    assert a["detection_to_green_s"] == 4.0 and a["green_latency_s"] == 3.9
    assert a["served"] == "West" and a["recovery_plan"] == "North; East; South" and a["recovery_greens"] == 2
    assert b["trigger"] == "manual" and b["ended_reason"] == "timeout" and not b["completed"]


def test_scripted_scenario_completes_logged_preemptions_with_recovery(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import scripted_scenario
    eps, log_path = scripted_scenario.run(tmp_path, fast=True, quiet=True)
    assert log_path.is_file() and (tmp_path / "scenario_episodes.csv").is_file()
    assert scripted_scenario.check(eps) == [], eps
