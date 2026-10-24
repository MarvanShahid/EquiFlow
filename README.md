# EquiFlow: ambulance-aware signal control

```
cameras / videos ──► vision worker ──► signal controller ──► event bus ──► REST + WebSocket ──► Next.js dashboard
 (one per approach)   yolo26s + ByteTrack   base controller          │
                      + cls_v4 + K-of-M     + ambulance preemption   ├──► MQTT bridge (optional)
                      voting                + fair recovery          └──► event history
```

| Folder | What it is |
|---|---|
| `backend/app/vision/` | Your two-model pipeline (`live.py`), plus a simulated camera (`sim.py`) |
| `backend/app/controllers/` | Signal logic: base controllers, preemption, safety timing, fair recovery. No web or ML dependencies |
| `backend/app/runtime.py` | Wires cameras → controller → events. One entry point for in-process cameras and external producers |
| `backend/app/api.py` | REST, WebSocket, MJPEG video |
| `backend/app/comms/mqtt_bridge.py` | Optional MQTT topics from the roadmap |
| `dashboard/` | Next.js (App Router, TypeScript) |

## Run it

**Backend** (Python 3.10+)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
It starts in **simulation** by default (no GPU, weights or videos needed), so you can see the whole flow immediately.

**Dashboard** (Node 18.18+)
```bash
cd dashboard
cp .env.local.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm.cmd install
npm.cmd run dev                           # http://localhost:3000
```
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
## Use your two models

1. `pip install ultralytics torch` in the same environment you ran the tracking script in.
2. Edit `backend/config.live.yaml`: the `cls_weights` path (your `cls_v4`), the four video paths (or RTSP URLs / webcam indexes).
3. Start the backend with that config:
   - PowerShell: `$env:EQUIFLOW_CONFIG="config.live.yaml"; uvicorn app.main:app --port 8000`
   - cmd: `set EQUIFLOW_CONFIG=config.live.yaml` then `uvicorn app.main:app --port 8000`

`mode: auto` falls back to simulation if the weights or `ultralytics` are missing. The reason is shown in the dashboard (hover the "Simulated cameras" pill) and in `GET /api/health`.
Any approach set to `sim` in the config stays simulated, so you can run one real camera and three simulated ones.

If four feeds are too slow: lower `imgsz` (960 or 640), set `process_every: 2`, or run the video at lower resolution.

## How the signals behave

Each approach has a four-lamp head: **ambulance (blue)** plus red, yellow, green.

- **Normal:** a base controller chooses who gets the next green. `fixed_time` cycles N→E→S→W. `adaptive` serves the busiest approach (from the vehicle counts the detector produces), with green length growing with the count and a hard maximum-wait bound (`max_wait_s`, default 90 s) so no approach starves.
- **Ambulance confirmed on approach A:** after the current green's minimum time, it goes yellow, then all-red, then **A turns green and the other three stay red** with A's blue lamp lit. Yellow and all-red are never skipped. Two ambulances are served first come, first served.
- **Release:** the junction is released 4 s after the ambulance was last seen (`clear_hold_s`). A fail-safe (`max_preempt_s`, 60 s) releases a stuck detection.
- **Fair recovery:** approaches that waited get extra green afterwards, longest-waiting first (`recovery_factor`, `recovery_max_s`).

The "detection to green" metric is the key demo number for Phase 6: how long after the vision confirmed an ambulance did its approach turn green.

## API

| | |
|---|---|
| `GET /api/signals`, `/api/signals/{id}` | Lamps, mode, countdown, vehicle counts, waiting times, source health |
| `POST /api/signals/{id}/preempt` `{approach, duration_s}` | Operator test: act as if an ambulance were there. `DELETE /api/signals/{id}/preempt/{approach}` cancels |
| `GET /api/ambulances` | Active and recent ambulances with approach, track id, confidence, position |
| `POST /api/ambulances/events` | **Ingest from another process** (a separate vision service, SUMO ground truth). Send a heartbeat about once a second while the ambulance is visible |
| `GET /api/metrics` | Detections, priority runs, detection-to-green latency, longest wait |
| `GET /api/events` | Event history (add `?positions=true` for position events) |
| `GET /api/video/{id}/{approach}` | MJPEG of the annotated feed |
| `WS /ws` | `{"type":"snapshot"}` at 2 Hz and `{"type":"event"}` as they happen |

MQTT (`mqtt.enabled: true` in the config): `equiflow/signal/{id}/preempt`, `equiflow/signal/{id}/state` (retained), `equiflow/ambulance/{id}/position`.
`docker compose up mosquitto` in this folder starts a local broker.

## Where later phases plug in

| Roadmap phase | Where it goes |
|---|---|
| Phase 3, MARL controller | Implement `BaseController.next_phase()` in `controllers/base.py` and add it to `REGISTRY`. Preemption, safety timing and recovery stay on top of it unchanged. The context already includes vehicle counts and waiting times |
| Phase 1/4, SUMO and route notification | `IntersectionController` takes `now` as an argument and never reads a clock, so it can run inside a SUMO step. Post SUMO's ambulance position to `/api/ambulances/events`, or call `runtime.ingest()` directly. The event schema has room for ETA and next-signal notifications |
| Phase 5, more intersections | Add entries under `intersections:` in the config. The backend, API and dashboard (tabs) already handle several. A map view needs only the `lat`/`lng` already in `/api/signals` |
| Phase 6, vision as a separate service | Run vision elsewhere and have it POST to `/api/ambulances/events` (or publish MQTT and add a subscriber) |
| Phase 7, evaluation | Every event is timestamped on the bus; add a listener that writes CSV |

## Tests

```bash
cd backend
pytest                      # or: python tests/test_controller.py
```
- `test_controller.py`: preemption, FIFO, fail-safe, recovery, adaptive fairness, randomized safety check (never two non-red lamps, yellow and all-red always honoured)
- `test_runtime.py`: end to end in simulation
- `test_live_pipeline.py`: your K-of-M voting rule and stationary filter, using stand-in models

## Things to know

- Vehicle counts are the number of tracked vehicles in the frame, a rough stand-in for queue length. Fine for the adaptive controller's demo; use lane zones if you want real queues.
- `min_move` is 0 in `config.live.yaml`, as in your tracking script. Raise it to about `0.01` to ignore stationary objects (your 7 false events on test12), at the cost of missing an ambulance that is stopped in traffic.
- The video-loop reset (`DirectionTracker.reset()`) relies on Ultralytics rebuilding its tracker when `predictor` is cleared. Check that track IDs restart when a video loops.
