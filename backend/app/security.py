"""Authentication and request hardening (NFR security, mid-report Section 4.5.4).

Roles
  operator   may change state: every POST / PUT / PATCH / DELETE under /api (priority, signal reset, SUMO control)
  viewer     may read: GET /api/*, the WebSocket streams (/ws, /ws/sumo) and the MJPEG video

Keys (environment variables win over config.yaml; keep them out of the repository):
  EQUIFLOW_API_KEY      / server.api_key            operator key   (or server.api_key_sha256: its SHA-256 hex)
  EQUIFLOW_VIEWER_KEY   / server.viewer_key         viewer key     (or server.viewer_key_sha256)
  EQUIFLOW_TOKEN_SECRET                             signs session tokens (random per start if unset)

How a client authenticates
  header  X-API-Key: <key>                  scripts and other services
  POST    /api/auth/login {"key": ...}      -> {"token", "role", "expires_in"}: a short-lived signed token, so a
                                               browser never stores the long-lived key
  header  Authorization: Bearer <token>
  query   ?token=<token>                    only for the WebSocket and MJPEG URLs (browsers cannot set headers
                                               there). Raw keys are never accepted in a URL.

Modes
  default            no key: everything open (local demo). Operator key set: writes need it, reads stay open
                     unless server.protect_reads is true.
  server.public      Internet deployment: refuses to start without an operator key of at least 24 characters,
                     forces protect_reads, and rejects wildcard CORS. Put it behind a TLS reverse proxy
                     (docs/DEPLOYMENT.md); HSTS is sent when the proxy reports https.

Also: failed logins lock the client IP out (server.max_failed_auth per minute), writes are rate-limited per IP
(server.write_rate_per_min), security headers on every response, and every write is published as an
`api_write` event (method, path, role, client, status) so it lands in the CSV event log. MQTT has its own
username/password (mqtt.username / mqtt.password)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
OPEN_PATHS = {"/api/health", "/api/auth/login", "/api/auth/whoami"}
MIN_PUBLIC_KEY_LEN = 24


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def resolve_key(configured: str | None) -> str | None:   # kept for callers of the Iteration 2 API
    key = os.environ.get("EQUIFLOW_API_KEY") or configured
    return key or None


class Auth:
    def __init__(self, server_cfg):
        s = server_cfg
        op = os.environ.get("EQUIFLOW_API_KEY") or s.api_key
        vw = os.environ.get("EQUIFLOW_VIEWER_KEY") or s.viewer_key
        self.op_hash = _sha(op) if op else (s.api_key_sha256 or None)
        self.vw_hash = _sha(vw) if vw else (s.viewer_key_sha256 or None)
        self._op_len = len(op) if op else None
        self.public = bool(s.public)
        self.protect_reads = bool(s.protect_reads or s.public)
        self.ttl = float(s.token_ttl_s)
        secret = os.environ.get("EQUIFLOW_TOKEN_SECRET")
        self.secret = secret.encode() if secret else secrets.token_bytes(32)
        self.max_failed = int(s.max_failed_auth)
        self.write_rate = int(s.write_rate_per_min)
        self._failed: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._writes: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ startup check
    def validate(self, cors_origins: list[str]) -> None:
        """Refuse an unsafe Internet deployment (raises RuntimeError with the reason)."""
        if not self.public:
            return
        problems = []
        if not self.op_hash:
            problems.append("no operator key (set EQUIFLOW_API_KEY)")
        elif self._op_len is not None and self._op_len < MIN_PUBLIC_KEY_LEN:
            problems.append(f"operator key shorter than {MIN_PUBLIC_KEY_LEN} characters")
        if self.vw_hash and self.vw_hash == self.op_hash:
            problems.append("viewer key equals the operator key")
        if any(o.strip() == "*" for o in cors_origins):
            problems.append("cors_origins contains '*'")
        if problems:
            raise RuntimeError("server.public is true but the deployment is not safe: " + "; ".join(problems))

    @property
    def enabled(self) -> bool:
        return bool(self.op_hash)

    # ------------------------------------------------------------------ keys and tokens
    def role_for_key(self, key: str) -> str | None:
        if not key:
            return None
        h = _sha(key)
        if self.op_hash and hmac.compare_digest(h, self.op_hash):
            return "operator"
        if self.vw_hash and hmac.compare_digest(h, self.vw_hash):
            return "viewer"
        return None

    def issue(self, role: str) -> dict:
        exp = int(time.time() + self.ttl)
        body = base64.urlsafe_b64encode(json.dumps({"r": role, "e": exp, "n": secrets.token_hex(6)}).encode())
        sig = base64.urlsafe_b64encode(hmac.new(self.secret, body, hashlib.sha256).digest())
        return {"token": (body + b"." + sig).decode().rstrip("="), "role": role, "expires_in": int(self.ttl)}

    def role_for_token(self, token: str) -> str | None:
        try:
            body, sig = token.split(".", 1)
            pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
            good = base64.urlsafe_b64encode(hmac.new(self.secret, pad(body).encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(pad(sig).encode(), good):
                return None
            data = json.loads(base64.urlsafe_b64decode(pad(body)))
            if data["e"] < time.time() or data["r"] not in ("operator", "viewer"):
                return None
            return data["r"]
        except Exception:  # noqa: BLE001 - any malformed token is simply not a token
            return None

    # ------------------------------------------------------------------ rate limits
    def locked(self, ip: str) -> bool:
        with self._lock:
            return self._locked_until.get(ip, 0) > time.time()

    def failed(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            q = self._failed[ip]
            q.append(now)
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= self.max_failed:
                self._locked_until[ip] = now + 60
                q.clear()

    def allow_write(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._writes[ip]
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= self.write_rate:
                return False
            q.append(now)
            return True


def _headers(scope) -> dict[str, str]:
    return {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}


def _client(scope, headers) -> str:
    fwd = headers.get("x-forwarded-for")
    if fwd:                                    # behind the reverse proxy: the first address is the client
        return fwd.split(",")[0].strip()
    c = scope.get("client")
    return c[0] if c else "?"


SECURITY_HEADERS = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"SAMEORIGIN"),
                    (b"referrer-policy", b"no-referrer"), (b"cross-origin-resource-policy", b"cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]


class AuthMiddleware:
    """Pure ASGI, so it covers WebSockets too (Starlette's BaseHTTPMiddleware does not)."""

    def __init__(self, app, auth: Auth, prefix: str = "/api"):
        self.app, self.auth, self.prefix = app, auth, prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path, method = scope.get("path", ""), scope.get("method", "GET")
        headers = _headers(scope)
        ip = _client(scope, headers)
        https = headers.get("x-forwarded-proto", scope.get("scheme", "http")) in ("https", "wss")
        a = self.auth

        async def send_h(msg):                 # security headers on every HTTP response
            if msg["type"] == "http.response.start":
                hs = list(msg.get("headers", [])) + SECURITY_HEADERS
                if https:
                    hs.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                msg["headers"] = hs
            await send(msg)

        is_ws = scope["type"] == "websocket"
        is_write = not is_ws and method in WRITE_METHODS and path.startswith(self.prefix)
        guarded = (path.startswith(self.prefix) or is_ws) and path not in OPEN_PATHS and method != "OPTIONS"
        need = "operator" if is_write else ("viewer" if a.protect_reads else None)
        if not a.enabled or not guarded or need is None:
            return await self.app(scope, receive, send_h)

        if a.locked(ip):
            return await self._deny(scope, send_h, 429, "too many failed attempts; try again in a minute")
        role = None
        key = headers.get("x-api-key", "")
        if key:
            role = a.role_for_key(key)
        bearer = headers.get("authorization", "")
        if role is None and bearer.lower().startswith("bearer "):
            role = a.role_for_token(bearer[7:].strip())
        if role is None and (is_ws or "/video/" in path):          # browsers cannot set headers here
            tok = parse_qs(scope.get("query_string", b"").decode()).get("token", [""])[0]
            role = a.role_for_token(tok) if tok else None
        if role is None:
            if key or bearer:
                a.failed(ip)
            return await self._deny(scope, send_h, 401, "authentication required (X-API-Key or Bearer token)")
        if need == "operator" and role != "operator":
            return await self._deny(scope, send_h, 403, "operator role required")
        if is_write and not a.allow_write(ip):
            return await self._deny(scope, send_h, 429, "too many requests")

        if not is_write:
            return await self.app(scope, receive, send_h)
        status = {"code": None}

        async def send_audit(msg):
            if msg["type"] == "http.response.start":
                status["code"] = msg["status"]
            await send_h(msg)
        try:
            await self.app(scope, receive, send_audit)
        finally:
            bus = getattr(getattr(scope.get("app"), "state", None), "bus", None)
            if bus is not None:
                bus.publish("api_write", method=method, path=path, role=role, client=ip, status=status["code"])

    @staticmethod
    async def _deny(scope, send, code: int, detail: str):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": detail}).encode()
        await send({"type": "http.response.start", "status": code,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


# Iteration 2 name, kept so older imports keep working
ApiKeyMiddleware = AuthMiddleware
