"""EquiFlow backend entry point:  uvicorn app.main:app --port 8000"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router, ws_router
from .bus import EventBus
from .comms.mqtt_bridge import MqttBridge
from .config import load_config
from .eventlog import EventLogger
from .runtime import Runtime
from .security import Auth, AuthMiddleware
from .sumo_api import router as sumo_router
from .sumo_api import ws_router as sumo_ws_router
from .sumo_live import SumoLive

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    elog = None
    if cfg.log.enabled:
        try:
            elog = EventLogger(cfg.log.dir, exclude=tuple(cfg.log.exclude))
            bus.add_listener(elog)
            logging.getLogger("equiflow").info("Event log: %s", elog.path)
        except OSError as e:  # a read-only folder must not stop the backend
            logging.getLogger("equiflow").warning("Event log disabled: %s", e)
    app.state.event_log = elog
    runtime = Runtime(cfg, bus)
    sumo = SumoLive(cfg, bus)
    app.state.cfg, app.state.bus, app.state.runtime, app.state.sumo = cfg, bus, runtime, sumo
    if not sumo.available:
        logging.getLogger("equiflow").warning("SUMO live view disabled: %s", sumo.reason)
    elif cfg.sumo.autostart:
        try:
            await asyncio.to_thread(sumo.start, cfg.sumo.network, cfg.sumo.scenario, cfg.sumo.controller)
        except Exception as e:  # noqa: BLE001 - the rest of the backend must still come up
            logging.getLogger("equiflow").warning("SUMO autostart failed: %s", e)

    mqtt = None
    if cfg.mqtt.enabled:
        mqtt = MqttBridge(cfg.mqtt, bus, runtime)
        mqtt.start()
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()
        sumo.stop()
        if mqtt:
            mqtt.stop()
        if elog:
            elog.close()


app = FastAPI(title="EquiFlow", version="0.1.0", lifespan=lifespan)
# Auth and CORS come from config; read once at import so the middleware can be installed
_server_cfg = load_config().server
auth = Auth(_server_cfg)
auth.validate(_server_cfg.cors_origins)     # server.public: refuse to start an unsafe Internet deployment
app.state.auth = auth
app.add_middleware(AuthMiddleware, auth=auth)
app.add_middleware(CORSMiddleware, allow_origins=_server_cfg.cors_origins,   # added last = outermost, so a
                   allow_methods=["*"], allow_headers=["*"])                  # 401 still carries CORS headers
app.include_router(router, prefix="/api")
app.include_router(ws_router)  # WebSocket at /ws, outside /api so a reverse proxy can route it separately
app.include_router(sumo_router, prefix="/api/sumo")
app.include_router(sumo_ws_router)  # /ws/sumo
