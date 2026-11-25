"""HTTP + WebSocket API.

  GET    /api/health
  GET    /api/config
  GET    /api/signals            GET /api/signals/{id}
  POST   /api/signals/{id}/preempt     DELETE /api/signals/{id}/preempt/{approach}
  GET    /api/ambulances         POST /api/ambulances/events   (external producers)
  GET    /api/metrics
  GET    /api/events
  GET    /api/video/{id}/{approach}    MJPEG stream of the annotated feed
  WS     /ws                     snapshots (2 Hz) + events
"""
from __future__ import annotations

import asyncio
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .controllers.types import APPROACHES

router = APIRouter()      # mounted under /api
ws_router = APIRouter()   # mounted at the root: /ws
Approach = Literal["North", "East", "South", "West"]


class PreemptRequest(BaseModel):
    approach: Approach
    duration_s: float = Field(20, gt=0, le=300)


class AmbulanceEventIn(BaseModel):
    intersection_id: str
    approach: Approach
    present: bool = True
    track_id: int | None = None
    confidence: float = Field(1.0, ge=0, le=1)
    cx: float | None = Field(None, ge=0, le=1)
    cy: float | None = Field(None, ge=0, le=1)
    ts: float | None = Field(None, description="when the producer saw it, unix seconds; stale events are rejected")


def _rt(request_or_ws):
    return request_or_ws.app.state.runtime


def _inter(request: Request, iid: str):
    try:
        return _rt(request).get(iid)
    except KeyError:
        raise HTTPException(404, f"unknown intersection '{iid}'")


class LoginIn(BaseModel):
    key: str = Field(min_length=1, max_length=512)


@router.post("/auth/login")
def login(request: Request, body: LoginIn):
    """Exchange an operator or viewer key for a short-lived signed token (app/security.py)."""
    auth = request.app.state.auth
    headers = {k.lower(): v for k, v in request.headers.items()}
    ip = headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    if auth.locked(ip):
        raise HTTPException(429, "too many failed attempts; try again in a minute")
    if not auth.enabled:
        return {"token": "", "role": "operator", "expires_in": 0, "auth": "disabled"}
    role = auth.role_for_key(body.key)
    if role is None:
        auth.failed(ip)
        bus = getattr(request.app.state, "bus", None)
        if bus is not None:
            bus.publish("auth_failed", client=ip)
        raise HTTPException(401, "wrong key")
    return auth.issue(role)


@router.get("/auth/whoami")
def whoami(request: Request):
    auth = request.app.state.auth
    return {"auth": "enabled" if auth.enabled else "disabled", "protect_reads": auth.protect_reads,
            "public": auth.public}


@router.get("/health")
def health(request: Request):
    rt = _rt(request)
    return {"status": "ok", "mode": rt.mode, "mode_reason": rt.mode_reason, "time": time.time()}


@router.get("/config")
def config(request: Request):
    rt = _rt(request)
    return {
        "mode": rt.mode,
        "controller": rt.cfg.controller,
        "approaches": list(APPROACHES),
        "intersections": [{"id": i.id, "name": i.name or i.id, "lat": i.lat, "lng": i.lng}
                          for i in rt.cfg.intersections],
    }


@router.get("/signals")
def signals(request: Request):
    return [i.snapshot() for i in _rt(request).intersections.values()]


@router.get("/signals/{iid}")
def signal(request: Request, iid: str):
    return _inter(request, iid).snapshot()


@router.post("/signals/{iid}/preempt")
def preempt(request: Request, iid: str, body: PreemptRequest):
    """Operator override: act as if an ambulance were on this approach."""
    _inter(request, iid).manual_preempt(body.approach, body.duration_s)
    return {"ok": True, "intersection_id": iid, "approach": body.approach, "duration_s": body.duration_s}


@router.delete("/signals/{iid}/preempt/{approach}")
def cancel_preempt(request: Request, iid: str, approach: Approach):
    _inter(request, iid).cancel_preempt(approach)
    return {"ok": True}


@router.get("/signals/{iid}/output")
def signal_output(request: Request, iid: str):
    """Signal output status: driver, fail-safe flash, latched fault (app/signals/)."""
    return _inter(request, iid).output.status()


@router.post("/signals/{iid}/output/reset")
def signal_output_reset(request: Request, iid: str):
    """Operator reset after a signal fault. Refused while the cause is still present."""
    ok, msg = _inter(request, iid).reset_output()
    request.app.state.bus.publish("signal_reset_requested", intersection_id=iid, ok=ok, message=msg)
    if not ok:
        raise HTTPException(409, msg)
    return {"ok": True, "message": msg}


@router.get("/ambulances")
def ambulances(request: Request):
    return _rt(request).snapshot()["ambulances"]


@router.post("/ambulances/events")
def ambulance_event(request: Request, body: AmbulanceEventIn):
    """Ingest from an external producer (a separate vision process, SUMO ground truth, ...).
    Send it as a heartbeat (about once a second) while the ambulance is visible."""
    ok = _inter(request, body.intersection_id).ingest(
        body.approach, body.present, body.track_id, body.confidence, body.cx, body.cy, ts=body.ts)
    return {"ok": ok} if ok else {"ok": False, "rejected": "stale"}


@router.get("/metrics")
def metrics(request: Request):
    return _rt(request).metrics()


@router.get("/events")
def events(request: Request, limit: int = 100, positions: bool = False):
    """Newest first. High-rate ambulance_position events are left out unless positions=true."""
    exclude = () if positions else ("ambulance_position",)
    return request.app.state.bus.recent(max(1, min(limit, 500)), exclude)


@router.get("/video/{iid}/{approach}")
async def video(request: Request, iid: str, approach: Approach):
    src = _inter(request, iid).sources.get(approach)
    if src is None:
        raise HTTPException(404, "no such source")

    async def gen():
        last = None
        while not await request.is_disconnected():
            jpg = src.latest_jpeg()
            if jpg is not None and jpg is not last:
                last = jpg
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            await asyncio.sleep(0.05)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})


@ws_router.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    rt, bus = _rt(websocket), websocket.app.state.bus
    try:
        with bus.subscribe() as q:
            await websocket.send_json({"type": "snapshot", "data": rt.snapshot()})
            last = time.monotonic()
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=0.5)
                    await websocket.send_json({"type": "event", "data": event})
                except asyncio.TimeoutError:
                    pass
                if time.monotonic() - last >= 0.5:
                    last = time.monotonic()
                    await websocket.send_json({"type": "snapshot", "data": rt.snapshot()})
    except (WebSocketDisconnect, RuntimeError):
        return
