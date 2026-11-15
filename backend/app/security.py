"""Optional API key for everything that changes state (NFR security, mid-report Section 4.5.4).

    server: {api_key: "some-long-random-string"}      # or the EQUIFLOW_API_KEY environment variable

With a key set, every POST / PUT / PATCH / DELETE under /api needs the header `X-API-Key: <key>`;
reading (GET, the WebSocket streams, MJPEG video) stays open so the dashboard can be shown on a
screen. Without a key (the default) nothing changes: fine for a local demo, not for a network
anyone else can reach. MQTT has its own username/password (mqtt.username / mqtt.password)."""
from __future__ import annotations

import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def resolve_key(configured: str | None) -> str | None:
    key = os.environ.get("EQUIFLOW_API_KEY") or configured
    return key or None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, key: str | None, prefix: str = "/api"):
        super().__init__(app)
        self.key = key
        self.prefix = prefix

    async def dispatch(self, request: Request, call_next):
        if self.key and request.method in WRITE_METHODS and request.url.path.startswith(self.prefix):
            given = request.headers.get("x-api-key", "")
            if not hmac.compare_digest(given.encode(), self.key.encode()):
                return JSONResponse({"detail": "missing or wrong X-API-Key"}, status_code=401)
        return await call_next(request)
