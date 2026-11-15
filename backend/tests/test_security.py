"""API key on write endpoints (app/security.py)."""
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.security import ApiKeyMiddleware, resolve_key  # noqa: E402


def client(key):
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, key=key)

    @app.get("/api/signals")
    def read():
        return {"ok": True}

    @app.post("/api/signals/J1/preempt")
    def write():
        return {"ok": True}
    return TestClient(app)


def test_writes_need_the_key_reads_do_not():
    c = client("s3cret")
    assert c.get("/api/signals").status_code == 200
    assert c.post("/api/signals/J1/preempt").status_code == 401
    assert c.post("/api/signals/J1/preempt", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/api/signals/J1/preempt", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_no_key_means_open_and_env_var_wins(monkeypatch):
    assert client(None).post("/api/signals/J1/preempt").status_code == 200
    monkeypatch.setenv("EQUIFLOW_API_KEY", "from-env")
    assert resolve_key("from-config") == "from-env"
    monkeypatch.delenv("EQUIFLOW_API_KEY")
    assert resolve_key("") is None
