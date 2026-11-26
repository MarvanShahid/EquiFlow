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
| `backend/app/sumo_live.py`, `sumo_api.py` | Live SUMO view: runs a `sumo/` network through TraCI with every signal driven by the same controller, and streams it to the dashboard |
| `dashboard/` | Next.js (App Router, TypeScript): Live network, Camera feeds, Results, How it works |
| `sumo/` | Islamabad junction networks, baseline runs (`run_sim.py`) and the EquiFlow evaluation (`run_equiflow.py`) |

## Run it

**Backend** (Python 3.10+)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
It starts in **simulation** by default (no GPU, weights or videos needed), so you can see the whole flow immediately.

On Windows machines where Smart App Control blocks torchvision's CUDA extension or the `lap` package, the live
pipeline still runs on the GPU: `backend/app/vision/gpu_compat.py` switches to Ultralytics' own NMS and ByteTrack's
SciPy matching only where needed (`python Projects/gpu_compat.py` shows what it applied).

(or `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`)

Where Windows blocks SUMO (Smart App Control), run the backend in WSL instead, so the Live network page works:
`wsl -d Ubuntu -- bash /mnt/c/<path to EquiFlow>/backend/run_wsl.sh` (needs `~/equiflow-venv` with
`requirements.lock.txt` installed; the dashboard still reaches it at http://localhost:8000).

**Dashboard** (Node 18.18+)
```bash
cd dashboard
copy .env.local.example .env.local      # Windows (cp on Linux/macOS); NEXT_PUBLIC_API_URL=http://localhost:8000
npm.cmd install
npm.cmd run dev                           # http://localhost:3000
```

## The website

| Page | What the traffic authority sees |
|---|---|
| **Live network** (`/`) | A live top-down view of a SUMO network (pick any of the 9 Islamabad junction types, the traffic level, and the controller: EquiFlow, fixed-time or actuated). Click a junction for its signals, queue and waiting time per approach, the phase it is serving, *why* it chose that green, and a virtual camera per approach showing the detector output (green box = vehicle, yellow = some ambulance votes, red = confirmed ambulance). Buttons send an ambulance from any approach or test priority without one. |
| **Camera feeds** (`/cameras`) | The four-camera pilot junction: annotated video from your two models (or simulated feeds), the signal heads and the event log |
| **Results** (`/results`) | Waiting time / time loss / trip time per vehicle class: fixed-time vs actuated vs EquiFlow, from `sumo/results/summary_by_class.csv` |
| **How it works** (`/how`) | The pipeline in six steps, for visitors |

The live view needs SUMO: either `SUMO_HOME` pointing at your SUMO install, or `pip install eclipse-sumo`. It starts by itself (`sumo.autostart` in `config.yaml`); without SUMO the rest of the backend still runs and the page says what is missing.

In the SUMO view each approach has a *virtual camera* (last 120 m before the stop line). The classifier score is simulated (ambulances score high, others low, with noise), but the confirmation rule is the real one from `vision:` (5 of the last 8 frames, mean >= 0.65), so an ambulance must be confirmed before it gets priority. The controller switches between the junction's signal-plan phases (`sumo.phasing: phases`, e.g. North+South together), so it has the same capacity as the SUMO baselines; an ambulance gets the phase that gives its approach a protected green.
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
- **Fair recovery (optional, off by default since Iteration 2b):** with `preempt.recovery: true`, approaches that waited and have a queue are served afterwards, longest-waiting first. `recovery_mode: order` only re-orders them (the base controller sizes each green; recommended), `queue` sizes each green to its queue (2 s per vehicle), `fixed` is the first rule. In the held-out evaluation none of them beat having no recovery (docs/RESULTS.md 3.2).
- **Gap-out:** a green that has run 5 s ends early (through yellow and all-red) when its approach is empty and another approach has demand (`gap_out`, `gap_out_min_green_s`). Never during priority.
- **Green extension:** a base green that reaches its planned length keeps going while its approach is still the busiest, up to 45 s, while no other queued approach has waited 30 s (`extend`, `extend_max_green_s`, `extend_wait_cap_s`). Never during priority or recovery.
- **Green corridor (SUMO, optional, off by default):** `sumo.corridor: true` asks signals further along a confirmed ambulance's route for priority just in time (`corridor_mode: just_in_time`). On the evaluated networks it did not make ambulances faster.
- **Stale events:** detections posted with a `ts` older than 2 s are rejected and logged (`stale_s`).

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
| Phase 3, MARL controller | Done: `controllers/marl.py` (registered as `marl`), trained with `marl/train_marl.py` |
| Phase 1/4, SUMO and route notification | `IntersectionController` takes `now` as an argument and never reads a clock, so it can run inside a SUMO step. Post SUMO's ambulance position to `/api/ambulances/events`, or call `runtime.ingest()` directly. The event schema has room for ETA and next-signal notifications |
| Phase 5, more intersections | Add entries under `intersections:` in the config. The backend, API and dashboard (tabs) already handle several. A map view needs only the `lat`/`lng` already in `/api/signals` |
| Phase 6, vision as a separate service | Run vision elsewhere and have it POST to `/api/ambulances/events` (or publish MQTT and add a subscriber) |
| Phase 7, evaluation | Done: every event goes to `backend/logs/events_*.csv` (`app/eventlog.py`, `log:` in the config); `scripts/preempt_report.py` turns a log into one row per preemption |

## Evaluation in SUMO

```bash
cd sumo
python run_sim.py --all                                   # fixed-time / actuated baselines (seed 1; --preempt for simple pre-emption)
python run_equiflow.py --all --seeds 1 2 3                # EquiFlow (adaptive) on every signalised network
python run_equiflow.py --all --seeds 1 2 3 --base marl    # EquiFlow with the MARL controller
python run_equiflow.py --all --controller fixed --seeds 2 3   # baselines for more seeds, same harness
python run_equiflow.py --all --no-corridor --label equiflow-nocorridor   # green-corridor ablation
python run_robustness.py                                  # camera miss / false-alarm sweep -> results/robustness.csv
python run_equiflow.py --all --event-log results/event_logs   # + per-run event log and preemption episodes
```
The full evaluation (every controller on the same 120 network x demand x seed runs, seeds 6-10, held out
from MARL training):
```bash
python run_matrix.py          # -> results/heldout/ (~20 min on 10 cores)
python aggregate.py           # means, 95% CIs, paired comparisons -> results/heldout/RESULTS_TABLES.md
python benchmark.py; python make_plots.py; python latex_tables.py     # performance, docs/figures, LaTeX tables
```

| Held-out, mean of 120 runs | Fixed-time | Actuated | Fixed + priority | **EquiFlow** | EquiFlow MARL |
|---|---|---|---|---|---|
| Ambulance wait at signals | 13.75 s | 7.42 s | 0.19 s | **0.10 s** | 0.10 s |
| Car wait | 16.87 s | 6.28 s | 10.36 s | **4.28 s** | 4.05 s |
| 95th-percentile wait | 51.7 s | 17.9 s | 29.4 s | **16.9 s** | 18.3 s |

Green extension and gap-out are the biggest gains for ordinary traffic. Fair recovery and the green corridor are
implemented but off by default: in 1 400 held-out runs and a 40-ambulance-per-hour stress test neither helped.
Full results, ablations and failure analysis:
[docs/RESULTS.md](docs/RESULTS.md). Requirement-by-requirement status: [docs/ITERATION2.md](docs/ITERATION2.md).
The Results page of the dashboard reads `results/heldout/` when it exists.

## What runs where

| Feature | Code |
|---|---|
| Ambulance detection (YOLO26s + ByteTrack + cls_v4, 5-of-8 vote) | `backend/app/vision/live.py`, `Projects/track_pipeline.py` |
| Adaptive base controller, preemption, safety timing, fair recovery | `backend/app/controllers/` |
| Green corridor (route-aware preemption across junctions) | `backend/app/sumo_live.py` (`sumo.corridor*` in the config) |
| Fairness-aware MARL controller | `backend/app/controllers/marl.py`, `marl/train_marl.py` ([marl/README.md](marl/README.md)) |
| Live SUMO view, virtual cameras, camera-noise model | `backend/app/sumo_live.py`, `sumo_api.py` |

## Tests

```bash
cd backend
pytest                      # 73 tests; or: python tests/test_controller.py
```
- `test_sumo.py`: SUMO geometry, signal phases, a headless run with ambulance priority, the green corridor and camera noise (skipped without SUMO)
- `test_marl.py`: MARL decisions, the 90 s fairness guard, learning updates, save/load
- `test_controller.py`: preemption, FIFO, fail-safe, recovery, adaptive fairness, randomized safety check (never two non-red lamps, yellow and all-red always honoured)
- `test_runtime.py`: end to end in simulation
- `test_live_pipeline.py`: your K-of-M voting rule and stationary filter, using stand-in models
- `test_eventlog.py`: the CSV event log, the preemption-episode table, and the scripted Iteration 2 scenario
- `test_requirements.py`: TC-03 stale events, TC-04 / FR-07 gap-out, FR-10 queue-sized and re-order recovery, recovery off, green extension
- `test_security.py`: operator / viewer roles, login tokens, protected reads incl. WebSocket and video, lockout, rate limit, headers, audit, public-mode startup check
- `test_signals.py`: signal output conflict monitor, fail-safe flash and reset, fault injection, one hour of the real controller
- `test_lanes.py`: calibrated lane-level queues (homography, lane membership, queue length in metres)
- `test_sumo.py::test_tc10_...`: same seed and configuration give identical results

## Deployment and field testing

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): keys and roles, `server.public`, TLS reverse proxy, the signal-output
  layer and its conflict monitor, and a deployment checklist.
- [docs/FIELD_TEST.md](docs/FIELD_TEST.md): shadow-mode test on live traffic with `Projects/field_record.py`, lane
  calibration with `Projects/calibrate_lanes.py`, and acceptance criteria.

## Iteration 2 evidence

See [docs/ITERATION2.md](docs/ITERATION2.md) for the status of every Iteration 2 item, the results and how to reproduce them.

```bash
cd backend
python scripts/scripted_scenario.py     # exit test: a scripted ambulance scenario -> logged preemption + recovery
cd ../Projects
python eval_detector.py                 # detector on the held-out test split + latency -> runs/eval_test/summary.md
```

## Things to know

- Vehicle counts are the number of tracked vehicles in the frame, a rough stand-in for queue length. Fine for the adaptive controller's demo; use lane zones if you want real queues.
- `min_move` is 0 in `config.live.yaml`, as in your tracking script. Raise it to about `0.01` to ignore stationary objects (your 7 false events on test12), at the cost of missing an ambulance that is stopped in traffic.
- The video-loop reset (`DirectionTracker.reset()`) relies on Ultralytics rebuilding its tracker when `predictor` is cleared. Check that track IDs restart when a video loops.
