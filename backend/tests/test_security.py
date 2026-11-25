"""Authentication and hardening (app/security.py): roles, tokens, protected reads incl. WebSocket and video,
lockout, write rate limit, security headers, audit events, and the public-deployment startup check."""
import hashlib
import os
import sys
import time

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import router  # noqa: E402
from app.bus import EventBus  # noqa: E402
from app.config import ServerCfg  # noqa: E402
from app.security import Auth, AuthMiddleware, resolve_key  # noqa: E402

OP, VW = "operator-key-0123456789abcdef", "viewer-key-0123456789abcdef"


def client(**cfg):
    auth = Auth(ServerCfg(**cfg))
    app = FastAPI()
    app.state.auth, app.state.bus = auth, EventBus()
    app.state.runtime = type("RT", (), {"mode": "sim", "mode_reason": "test"})()   # for /api/health
    app.add_middleware(AuthMiddleware, auth=auth)

    @app.get("/api/thing")
    def read():
        return {"ok": True}

    @app.post("/api/thing")
    def write():
        return {"ok": True}

    @app.get("/api/video/J1/North")
    def video():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"hello": 1})
        await websocket.close()

    app.include_router(router, prefix="/api")          # the real /api/auth/login, /api/auth/whoami, /api/health
    return TestClient(app), app


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch):
    for k in ("EQUIFLOW_API_KEY", "EQUIFLOW_VIEWER_KEY", "EQUIFLOW_TOKEN_SECRET"):
        monkeypatch.delenv(k, raising=False)


# ------------------------------------------------------------------ Iteration 2 behaviour, unchanged
def test_writes_need_the_key_reads_do_not():
    c, _ = client(api_key="s3cret")
    assert c.get("/api/thing").status_code == 200
    assert c.post("/api/thing").status_code == 401
    assert c.post("/api/thing", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/api/thing", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_no_key_means_open_and_env_var_wins(monkeypatch):
    c, _ = client()
    assert c.post("/api/thing").status_code == 200
    monkeypatch.setenv("EQUIFLOW_API_KEY", "from-env")
    assert resolve_key("from-config") == "from-env"
    c, _ = client(api_key="from-config")
    assert c.post("/api/thing", headers={"X-API-Key": "from-env"}).status_code == 200
    assert c.post("/api/thing", headers={"X-API-Key": "from-config"}).status_code == 401


# ------------------------------------------------------------------ roles, tokens, protected reads
def test_viewer_reads_operator_writes():
    c, _ = client(api_key=OP, viewer_key=VW, protect_reads=True)
    assert c.get("/api/thing").status_code == 401
    assert c.get("/api/health").status_code == 200                       # health stays open for monitoring
    assert c.get("/api/thing", headers={"X-API-Key": VW}).status_code == 200
    assert c.post("/api/thing", headers={"X-API-Key": VW}).status_code == 403
    assert c.post("/api/thing", headers={"X-API-Key": OP}).status_code == 200


def test_login_token_works_for_headers_websocket_and_video_but_keys_never_in_urls():
    c, _ = client(api_key=OP, viewer_key=VW, protect_reads=True)
    assert c.post("/api/auth/login", json={"key": "nope"}).status_code == 401
    r = c.post("/api/auth/login", json={"key": VW}).json()
    assert r["role"] == "viewer" and r["expires_in"] > 0
    tok = r["token"]
    assert c.get("/api/thing", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert c.post("/api/thing", headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    assert c.get(f"/api/video/J1/North?token={tok}").status_code == 200
    assert c.get(f"/api/video/J1/North?token={VW}").status_code == 401        # a raw key in a URL is refused
    with c.websocket_connect(f"/ws?token={tok}") as ws:
        assert ws.receive_json() == {"hello": 1}
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws") as ws:
            ws.receive_json()
    op = c.post("/api/auth/login", json={"key": OP}).json()["token"]
    assert c.post("/api/thing", headers={"Authorization": f"Bearer {op}"}).status_code == 200


def test_tampered_or_expired_tokens_are_rejected():
    c, app = client(api_key=OP, protect_reads=True, token_ttl_s=1)
    tok = c.post("/api/auth/login", json={"key": OP}).json()["token"]
    body, sig = tok.split(".")
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + sig
    assert c.get("/api/thing", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    other = Auth(ServerCfg(api_key=OP)).issue("operator")["token"]         # signed with another secret
    assert c.get("/api/thing", headers={"Authorization": f"Bearer {other}"}).status_code == 401
    time.sleep(1.2)
    assert c.get("/api/thing", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_hashed_keys_in_config():
    c, _ = client(api_key_sha256=hashlib.sha256(OP.encode()).hexdigest())
    assert c.post("/api/thing", headers={"X-API-Key": OP}).status_code == 200
    assert c.post("/api/thing", headers={"X-API-Key": OP + "x"}).status_code == 401


# ------------------------------------------------------------------ abuse limits, headers, audit
def test_failed_attempts_lock_the_client_out():
    c, _ = client(api_key=OP, max_failed_auth=3)
    for _ in range(3):
        assert c.post("/api/thing", headers={"X-API-Key": "guess"}).status_code == 401
    assert c.post("/api/thing", headers={"X-API-Key": OP}).status_code == 429          # even the right key
    assert c.post("/api/auth/login", json={"key": OP}).status_code == 429


def test_write_rate_limit():
    c, _ = client(api_key=OP, write_rate_per_min=5)
    codes = [c.post("/api/thing", headers={"X-API-Key": OP}).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]


def test_security_headers_and_hsts_behind_https_proxy():
    c, _ = client(api_key=OP)
    r = c.get("/api/thing")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in r.headers
    r = c.get("/api/thing", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"].startswith("max-age=")


def test_every_write_is_audited():
    c, app = client(api_key=OP)
    c.post("/api/thing", headers={"X-API-Key": OP, "X-Forwarded-For": "203.0.113.9"})
    ev = [e for e in app.state.bus.recent(50) if e["type"] == "api_write"]
    assert ev and ev[0]["path"] == "/api/thing" and ev[0]["role"] == "operator"
    assert ev[0]["client"] == "203.0.113.9" and ev[0]["status"] == 200


# ------------------------------------------------------------------ Internet deployment check
def test_public_mode_refuses_an_unsafe_deployment():
    with pytest.raises(RuntimeError, match="no operator key"):
        Auth(ServerCfg(public=True)).validate([])
    with pytest.raises(RuntimeError, match="shorter"):
        Auth(ServerCfg(public=True, api_key="short")).validate([])
    with pytest.raises(RuntimeError, match=r"'\*'"):
        Auth(ServerCfg(public=True, api_key=OP)).validate(["*"])
    a = Auth(ServerCfg(public=True, api_key=OP, viewer_key=VW))
    a.validate(["https://dashboard.example.org"])
    assert a.protect_reads                                                # forced on in public mode
