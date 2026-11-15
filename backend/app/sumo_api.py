"""HTTP + WebSocket API for the live SUMO view.

  GET  /api/sumo/status          GET /api/sumo/networks       GET /api/sumo/results
  GET  /api/sumo/geometry        GET /api/sumo/frame
  GET  /api/sumo/robustness      GET /api/sumo/training     (camera-noise sweep, MARL training log)
  POST /api/sumo/start {network, scenario, controller, speed, seed}
  POST /api/sumo/stop            POST /api/sumo/speed {speed}     POST /api/sumo/pause {paused}
  POST /api/sumo/ambulance {tls?, approach?}       dispatch an ambulance into the simulation
  POST /api/sumo/preempt {tls, approach, duration_s}   operator test (EquiFlow controller only)
  WS   /ws/sumo                  {"type":"geometry"} on connect / new run, {"type":"frame"} ~6 Hz
"""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .sumo_live import list_networks, read_results, read_robustness, read_training

router = APIRouter()      # mounted under /api/sumo
ws_router = APIRouter()   # /ws/sumo


class StartIn(BaseModel):
    network: str
    scenario: Literal["low", "medium", "high", "asymmetric"] = "medium"
    controller: Literal["equiflow", "fixed", "actuated"] = "equiflow"
    speed: float | None = Field(None, gt=0, le=50)
    seed: int = 1
    base: Literal["adaptive", "marl", "fixed_time"] | None = None   # EquiFlow's base controller


class SpeedIn(BaseModel):
    speed: float = Field(..., gt=0, le=50)


class PauseIn(BaseModel):
    paused: bool


class AmbulanceIn(BaseModel):
    tls: str | None = None
    approach: str | None = None


class PreemptIn(BaseModel):
    tls: str
    approach: str
    duration_s: float = Field(20, gt=0, le=300)


def _sumo(request_or_ws):
    return request_or_ws.app.state.sumo


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e))


@router.get("/status")
def status(request: Request):
    return _sumo(request).status()


@router.get("/networks")
def networks(request: Request):
    return {"networks": list_networks(), "status": _sumo(request).status()}


@router.get("/results")
def results():
    return read_results()


@router.get("/robustness")
def robustness():
    return read_robustness()


@router.get("/training")
def training():
    return read_training()


@router.get("/geometry")
def geometry(request: Request):
    g = _sumo(request).public_geometry()
    if g is None:
        raise HTTPException(404, "no simulation has been started")
    return g


@router.get("/frame")
def frame(request: Request):
    f = _sumo(request).frame
    if f is None:
        raise HTTPException(404, "no frame yet")
    return f


@router.post("/start")
async def start(request: Request, body: StartIn):
    s = _sumo(request)
    # building the geometry and stopping the old run can take a moment: keep the event loop free
    return await asyncio.to_thread(_guard, s.start, body.network, body.scenario, body.controller, body.speed, body.seed,
                                   body.base)


@router.post("/stop")
async def stop(request: Request):
    s = _sumo(request)
    await asyncio.to_thread(s.stop)
    return s.status()


@router.post("/speed")
def speed(request: Request, body: SpeedIn):
    _sumo(request).set_speed(body.speed)
    return {"ok": True, "speed": body.speed}


@router.post("/pause")
def pause(request: Request, body: PauseIn):
    _sumo(request).pause(body.paused)
    return {"ok": True}


@router.post("/ambulance")
def ambulance(request: Request, body: AmbulanceIn):
    _guard(_sumo(request).dispatch_ambulance, body.tls, body.approach)
    return {"ok": True}


@router.post("/preempt")
def preempt(request: Request, body: PreemptIn):
    _guard(_sumo(request).preempt, body.tls, body.approach, body.duration_s)
    return {"ok": True}


@ws_router.websocket("/ws/sumo")
async def ws_sumo(websocket: WebSocket):
    await websocket.accept()
    s = _sumo(websocket)
    sent_run, sent_seq = -1, -1
    try:
        await websocket.send_json({"type": "status", "data": s.status()})
        while True:
            if s.run_id != sent_run and s.geometry is not None:
                g = s.public_geometry()
                if g is not None:
                    await websocket.send_json({"type": "geometry", "data": g})
                    await websocket.send_json({"type": "status", "data": s.status()})
                    sent_run = g["run_id"]
            f = s.frame
            if f is not None and s.frame_seq != sent_seq and f.get("run_id") == sent_run:
                sent_seq = s.frame_seq
                await websocket.send_json({"type": "frame", "data": f})
            await asyncio.sleep(0.1)
    except (WebSocketDisconnect, RuntimeError):
        return
