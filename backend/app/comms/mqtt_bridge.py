"""Optional MQTT bridge (roadmap Phase 5/6). Mirrors bus events onto topics:

  equiflow/signal/{id}/state            retained, every phase change   {lamps, mode, ...}
  equiflow/signal/{id}/preempt          preemption start/switch/end    {active, approach, ...}
  equiflow/ambulance/{id}/position      ~1 Hz while an ambulance is seen {approach, cx, cy, ...}

Publishing is non-blocking and the broker may be down: the app keeps running
and paho reconnects on its own."""
from __future__ import annotations

import json
import logging
import time

from ..bus import EventBus
from ..config import MqttCfg

log = logging.getLogger("equiflow.mqtt")


class MqttBridge:
    def __init__(self, cfg: MqttCfg, bus: EventBus, runtime):
        self.cfg, self.bus, self.runtime = cfg, bus, runtime
        self.client = None

    def start(self) -> None:
        import paho.mqtt.client as mqtt  # lazy: only needed when enabled
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="equiflow-backend")
        except AttributeError:  # paho-mqtt 1.x
            self.client = mqtt.Client(client_id="equiflow-backend")
        if self.cfg.username:
            self.client.username_pw_set(self.cfg.username, self.cfg.password)
        self.client.reconnect_delay_set(1, 30)
        self.client.connect_async(self.cfg.host, self.cfg.port, keepalive=30)
        self.client.loop_start()
        self.bus.add_listener(self._on_event)
        log.info("MQTT bridge -> %s:%s (prefix '%s')", self.cfg.host, self.cfg.port, self.cfg.prefix)

    def stop(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _pub(self, topic: str, payload: dict, retain: bool = False, qos: int = 1) -> None:
        if self.client:
            self.client.publish(f"{self.cfg.prefix}/{topic}", json.dumps(payload), qos=qos, retain=retain)

    def _on_event(self, e: dict) -> None:
        t, iid = e["type"], e.get("intersection_id")
        if t in ("preempt_started", "preempt_switched", "preempt_ended", "preempt_green", "preempt_timeout",
                 "recovery_planned"):
            self._pub(f"signal/{iid}/preempt", {**e, "active": t in ("preempt_started", "preempt_switched", "preempt_green")})
        elif t == "ambulance_position":
            self._pub(f"ambulance/{e['ambulance_id']}/position", e, qos=0)
        elif t in ("phase_changed", "mode_changed"):
            try:
                snap = self.runtime.get(iid).snapshot()
            except Exception:  # noqa: BLE001
                return
            self._pub(f"signal/{iid}/state", {"ts": time.time(), **{k: snap[k] for k in (
                "mode", "stage", "current", "lamps", "active_preempt")}}, retain=True)
