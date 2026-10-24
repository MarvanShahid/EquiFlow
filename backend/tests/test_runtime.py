"""Integration test of the runtime in simulation mode (no GPU / models / web framework)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bus import EventBus  # noqa: E402
from app.config import AppConfig, IntersectionCfg, SimCfg  # noqa: E402
from app.runtime import Runtime  # noqa: E402


def make_runtime(**over):
    cfg = AppConfig(mode="sim", controller="fixed_time",
                    sim=SimCfg(auto_ambulance=False),
                    intersections=[IntersectionCfg(id="J1", name="Test")], **over)
    cfg.timing.green_s = 4
    cfg.timing.yellow_s = 1
    cfg.timing.all_red_s = 1
    cfg.preempt.min_green_s = 1
    cfg.preempt.clear_hold_s = 1.5
    bus = EventBus()
    return Runtime(cfg, bus), bus


def wait_for(pred, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


def types(bus):
    return [e["type"] for e in bus.recent(500)]


def test_sim_feeds_produce_frames_and_vehicle_counts():
    rt, bus = make_runtime()
    rt.start()
    try:
        i = rt.get("J1")
        assert wait_for(lambda: all(s.latest_jpeg() for s in i.sources.values()))
        assert rt.mode == "sim"
        assert wait_for(lambda: sum(i.snapshot()["vehicles"].values()) > 0)
        snap = rt.snapshot()
        assert len(snap["intersections"]) == 1 and snap["metrics"]["mode"] == "sim"
    finally:
        rt.stop()


def test_manual_preempt_turns_ambulance_approach_green_and_logs_events():
    rt, bus = make_runtime()
    rt.start()
    try:
        i = rt.get("J1")
        time.sleep(0.5)
        i.manual_preempt("South", 8)
        assert wait_for(lambda: i.snapshot()["lamps"]["South"] == "green", 12)
        lamps = i.snapshot()["lamps"]
        assert [a for a, l in lamps.items() if l != "red"] == ["South"]
        assert i.snapshot()["mode"] == "PREEMPT"
        # the simulated camera also sees the ambulance, confirms it, and it shows up in the registry
        assert wait_for(lambda: any(a["approach"] == "South" for a in i.ambulances()), 15)
        assert wait_for(lambda: "preempt_ended" in types(bus), 30)
        t = types(bus)
        for expected in ("manual_preempt", "preempt_started", "preempt_green", "ambulance_detected",
                         "phase_changed", "preempt_ended"):
            assert expected in t, (expected, t)
        m = rt.metrics()
        assert m["preemptions"] == 1 and m["preempt_latency_last_s"] is not None
    finally:
        rt.stop()


def test_external_ingest_triggers_preemption():
    rt, bus = make_runtime()
    rt.start()
    try:
        i = rt.get("J1")
        def beat():
            i.ingest("West", True, 7, 0.9, 0.4, 0.5)
        end = time.time() + 12
        got = False
        while time.time() < end:
            beat()
            if i.snapshot()["lamps"]["West"] == "green":
                got = True
                break
            time.sleep(0.2)
        assert got
        assert any(e["type"] == "ambulance_detected" and e["approach"] == "West" for e in bus.recent(500))
    finally:
        rt.stop()


def test_mqtt_topics():
    from app.comms.mqtt_bridge import MqttBridge
    from app.config import MqttCfg
    rt, bus = make_runtime()
    b = MqttBridge(MqttCfg(enabled=True), bus, rt)
    sent = []
    b.client = type("C", (), {"publish": lambda self, t, p, qos=0, retain=False: sent.append((t, retain))})()
    b._on_event({"type": "preempt_started", "intersection_id": "J1", "approach": "North"})
    b._on_event({"type": "ambulance_position", "intersection_id": "J1", "ambulance_id": "J1-North-3",
                 "approach": "North", "cx": 0.5, "cy": 0.5})
    b._on_event({"type": "phase_changed", "intersection_id": "J1", "approach": "North"})
    topics = [t for t, _ in sent]
    assert "equiflow/signal/J1/preempt" in topics
    assert "equiflow/ambulance/J1-North-3/position" in topics
    assert "equiflow/signal/J1/state" in topics


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                fails += 1
                print("FAIL", name, "->", repr(e))
    sys.exit(1 if fails else 0)
