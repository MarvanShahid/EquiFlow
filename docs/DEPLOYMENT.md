# Deploying EquiFlow beyond a local demo

Three things change when EquiFlow leaves the laptop: who may reach it (authentication), how it is reached
(TLS), and what it may drive (signal hardware). Each is below; everything here is implemented and tested in
the backend (`tests/test_security.py`, `tests/test_signals.py`), except the field work that needs hardware.

## 1. Authentication (backend/app/security.py)

| Role | May |
|---|---|
| operator | everything, including priority requests, SUMO control and the signal-output reset |
| viewer | read only: the REST API, the WebSocket streams and the camera video |

Generate two long random keys and give them to the backend through the environment (not the config file):

```
python -c "import secrets; print(secrets.token_urlsafe(32))"      # run twice: operator key, viewer key
```

```
EQUIFLOW_API_KEY=<operator key>
EQUIFLOW_VIEWER_KEY=<viewer key>
EQUIFLOW_TOKEN_SECRET=<a third random value>   # keeps session tokens valid across restarts
EQUIFLOW_CONFIG=config.live.yaml
```

and in the config:

```yaml
server:
  public: true                       # refuse to start unless the settings below are safe
  cors_origins: ["https://equiflow.example.org"]    # the dashboard's address, never "*"
  token_ttl_s: 3600
  max_failed_auth: 10                # per minute per client, then a 60 s lockout
  write_rate_per_min: 120
```

With `public: true` the backend **refuses to start** without an operator key of at least 24 characters, with a
viewer key equal to the operator key, or with wildcard CORS, and it protects every read. To keep no secret even
in the environment file, store only the hashes: `server.api_key_sha256` / `server.viewer_key_sha256`
(`python -c "import hashlib; print(hashlib.sha256(b'<key>').hexdigest())"`).

The dashboard asks for a key once, exchanges it at `POST /api/auth/login` for a short-lived token and keeps only
the token for the browser tab. Do **not** set `NEXT_PUBLIC_API_KEY` for an Internet deployment: anything with
`NEXT_PUBLIC_` is built into the page and readable by anyone. Scripts and other services send
`X-API-Key: <key>`. Every write is logged as an `api_write` event (method, path, role, client, status), and
failed logins as `auth_failed`, in the CSV event log.

## 2. TLS (HTTPS / WSS)

The backend speaks plain HTTP; put it behind a reverse proxy that terminates TLS and keep port 8000 closed to the
outside (bind uvicorn to 127.0.0.1). Example with Caddy (automatic certificates):

```
equiflow.example.org {
    reverse_proxy /api/* 127.0.0.1:8000
    reverse_proxy /ws* 127.0.0.1:8000
    reverse_proxy 127.0.0.1:3000            # the Next.js dashboard (npm run build && npm start)
}
```

Caddy passes `X-Forwarded-For` / `X-Forwarded-Proto`, which the backend uses for the client address (lockout,
rate limit, audit) and for HSTS. With nginx, set `proxy_set_header X-Forwarded-For $remote_addr;`,
`proxy_set_header X-Forwarded-Proto $scheme;` and the WebSocket upgrade headers for `/ws`. Build the dashboard
with `NEXT_PUBLIC_API_URL=https://equiflow.example.org`. MQTT: enable TLS on the broker and set
`mqtt.username` / `mqtt.password`.

The backend trusts `X-Forwarded-For`, so it must only be reachable through the proxy.

## 3. Signal hardware (backend/app/signals/)

The controller's lamp states pass through an independent **conflict monitor** before they reach a **signal
driver**:

```yaml
output:
  driver: none          # none (default) | simulated (a simulated field controller, for testing the chain)
  min_green_s: 1.0      # shortest green accepted
  watchdog_s: 1.0       # longest gap between commands
  mismatch_s: 0.5       # how long commanded and read-back lamps may differ
```

The monitor checks every command and every read-back: conflicting approaches non-red together, a green ending
without its full yellow, a new green before the full all-red, flicker greens, a stopped controller (watchdog, in
its own thread) and lamps that differ from what was commanded (a stuck load switch, a lost link). Any violation
latches **all-red flashing**; `POST /api/signals/{id}/output/reset` (operator) clears it only once the hardware
reads back all-red and the link is up. `GET /api/signals/{id}/output` shows the state; faults and resets are
events in the log.

There is no driver for real hardware yet, deliberately: driving real signals needs the traffic authority, the
controller's protocol (e.g. NTCIP 1202 over SNMP, or a vendor interface), hardware-in-the-loop testing on a bench,
and the cabinet's own hardware conflict monitor, which the software monitor adds to and never replaces.
`backend/app/signals/drivers.py` says what a driver must implement. Until then EquiFlow runs in **shadow mode**
on live traffic ([FIELD_TEST.md](FIELD_TEST.md)).

## 4. Checklist

- [ ] `server.public: true`, both keys from the environment, `cors_origins` = the dashboard address
- [ ] backend bound to 127.0.0.1, only the TLS proxy exposed; firewall closes everything else
- [ ] dashboard built without `NEXT_PUBLIC_API_KEY`
- [ ] MQTT with TLS and a password, or `mqtt.enabled: false`
- [ ] event log on (`log.enabled: true`) and backed up; review `api_write` and `auth_failed` events
- [ ] `output.driver: none` (shadow mode) until the hardware steps in Section 3 are done
