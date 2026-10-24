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
from .runtime import Runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    bus = EventBus()
    bus.bind_loop(asyncio.get_running_loop())
    runtime = Runtime(cfg, bus)
    app.state.cfg, app.state.bus, app.state.runtime = cfg, bus, runtime

    mqtt = None
    if cfg.mqtt.enabled:
        mqtt = MqttBridge(cfg.mqtt, bus, runtime)
        mqtt.start()
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()
        if mqtt:
            mqtt.stop()


app = FastAPI(title="EquiFlow", version="0.1.0", lifespan=lifespan)
# CORS origins come from config; read once at import so the middleware can be installed
app.add_middleware(CORSMiddleware, allow_origins=load_config().server.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
app.include_router(ws_router)  # WebSocket at /ws, outside /api so a reverse proxy can route it separately
