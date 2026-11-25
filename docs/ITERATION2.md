# Iteration 2: tracking, control, integration and evaluation

Status of every item the FYP-1 mid-report promised (requirements Table 4.2-4.5, test cases Table 7.1,
deliverables Section 9.8), with the code, the evidence and the command that reproduces it.
Results and their discussion: [RESULTS.md](RESULTS.md). Report chapter: [latex/chapter7_iteration2.tex](latex/chapter7_iteration2.tex).

## Functional requirements

| ID | Requirement | Status | Code | Evidence |
|---|---|---|---|---|
| FR-01 | Video or simulated detection input | Done | `backend/app/vision/`, `POST /api/ambulances/events` | `tests/test_runtime.py` |
| FR-02 | Class, confidence, boxes | Done | `vision/live.py` | `tests/test_live_pipeline.py` |
| FR-03 | Log confidence + timestamp | Done | `app/eventlog.py` (CSV per run in `backend/logs/`) | `tests/test_eventlog.py` |
| FR-04 | Phase, queue, wait, ambulance approach | Done | SUMO: per-group queues; cameras: approach polygons (`zones:` in config) count vehicles inside and report stationary ones as the queue | `test_fr04_zone_...` |
| FR-05 | Missing / stale detections handled safely | Done | 5-of-8 vote (live config with `cls_v5_img128`: 3-of-8 and mean p >= 0.70, re-tuned below), 4 s release, 60 s fail-safe, external events older than 2 s rejected (`preempt.stale_s`) | `test_tc03_...` |
| FR-06 | Configurable phases, min/max green | Done | `config.yaml` | `tests/test_controller.py` |
| FR-07 | End an empty green early, safely | Done | gap-out in `controllers/intersection.py` (after 5 s, only if another approach has demand, never during priority, full yellow + all-red) | `test_tc04_...` (3 tests) |
| FR-08 | Priority for a confirmed ambulance | Done | `controllers/intersection.py` | `tests/test_controller.py` |
| FR-09 | Log preemption start, clearance, recovery | Done | event log + `scripts/preempt_report.py` | `scripts/scripted_scenario.py` (PASS) |
| FR-10 | Recovery uses queue and wait | Done | longest wait first, green sized to queue (2 s per vehicle, 5-30 s), empty approaches skipped | `test_fr10_...` (2 tests) |
| FR-11 | Compare with fixed-time and adaptive | Done | `sumo/run_matrix.py` | `sumo/results/heldout/` (1 000 runs) |
| FR-12 | Export metrics + configuration | Done | `run_manifest.csv`: full config, software versions, git commit, MARL weights hash per run | `sumo/results/heldout/run_manifest.csv` |

## Test cases (mid-report Table 7.1)

| Test | Status | Where |
|---|---|---|
| TC-01 / TC-02 detector on labelled test images | Done: pipeline model `cls_v5_img128` on the test split: acc 98.0%, precision 96.5%, recall 93.5%, F1 0.950, false alarms 0.9% (threshold 0.5). Mid-report model `cls_v4-2`: 97.7% / 95.7% / 92.8% / 0.942 | `Projects/runs/eval_test_v5_img128/`, `runs/eval_test/` |
| TC-03 stale event | Pass | `tests/test_requirements.py` |
| TC-04 empty approach during green | Pass | `tests/test_requirements.py` |
| TC-05 ambulance at red | Pass | `tests/test_controller.py` |
| TC-06 ambulance passes, recovery starts | Pass | `scripts/scripted_scenario.py`, `tests/test_eventlog.py` |
| TC-07 long wait served | Pass | `tests/test_controller.py` (90 s guard) |
| TC-08 conflicting phase request | Pass | randomized safety test in `tests/test_controller.py` |
| TC-09 baseline run | Pass | `sumo/results/heldout/` |
| TC-10 same seed, same result | Pass | `tests/test_sumo.py::test_tc10_...` |

**40 automated tests, all passing** (Linux / Python 3.10 and Windows / Python 3.14).

## Acceptance criteria (Table 4.5)

| Area | Status |
|---|---|
| Dataset documented, no duplicates across splits | Done: `Projects/split_report.md`, `crops_manifest.csv` (32 593 crops). Test split has no exact duplicates of train; 134 same-class near duplicates (3.6%). Removed: 4 mislabelled `- Copy` files in val/ambulance and 35 duplicate `- Copy` files in train. 19 same-label exact duplicates remain in val |
| Detection on test split, precision/recall/F1, errors | Done: `Projects/runs/eval_test_v5_img128/` (pipeline model), `runs/eval_test/` (`cls_v4-2`, threshold 0.5) and `runs/eval_test_r95/` (threshold 0.051 chosen on val for 95% recall: test recall 95.7%, precision 87.7%) |
| Safety tests | Done |
| Scripted emergency trip logged | Done |
| Recovery interval and waiting-time distribution recorded | Done: `recovery_s_mean`, p50/p95/p99/max wait, share > 60 s, worst approach, Jain index per run |
| 3+ repeatable runs per scenario | Done: 5 seeds (6-10) per network x demand x controller |
| Reproducible by another member | Done: `run_manifest.csv`, `backend/requirements.lock.txt`, one command per step |

## Non-functional requirements

| | Status |
|---|---|
| Safety | Tested (randomized: never two non-red lamps; yellow and all-red always honoured) |
| Performance | `sumo/results/performance.md`: controller tick ~1 µs, MARL decision ~24 µs; 1 h of SUMO in ~3 s. RTX 4050 laptop: vehicle detector 27.7 ms per 1280 px frame, classifier 1.7 ms per crop (batch 16, `cls_v4-2`); full pipeline ~45 ms per frame with 10 vehicles (`runs/eval_test/summary.md`). Measured back to back on battery power, `cls_v5_img128` (128 px) costs 2.3 ms per crop vs 2.0-2.3 ms for `cls_v4-2`: no real difference |
| Security | Optional API key on every write (`server.api_key` / `EQUIFLOW_API_KEY`, `app/security.py`); MQTT username/password. Off by default for local demos |
| Reproducibility | Pinned versions in `backend/requirements.lock.txt`; seeds, config and versions saved per run |
| Portability | Tests pass on Linux and Windows |

## Evaluation (mid-report Chapter 7)

| Promise | Where |
|---|---|
| Held-out scenarios for learned policies (7.5) | Seeds 6-10 for every controller; MARL trained on 1-5. `marl_heldout.csv` also splits trained vs unseen network/demand |
| Mean and variation across seeds (7.1) | Mean, SD and 95% CI: `summary_stats.csv`; paired differences on identical runs: `paired.csv` |
| Emergency-only preemption baseline (7.2) | `fixed+preempt` |
| No-recovery comparison on max / high-percentile wait (1.9) | `equiflow-norecovery` ablation (result: no significant difference; see RESULTS.md Section 3) |
| Sensitivity analysis (7.6) | 4 demand levels; camera miss / false-alarm sweep `results/robustness.csv` |
| Plots | `docs/figures/` (PNG + PDF), from `sumo/make_plots.py` |
| Failure-case analysis | `RESULTS.md` Section 7 |
| Tracking on real video | `Projects/tracking_out/tracking_scores.md` (`cls_v5_img128`, re-tuned votes): all 12 available videos (test7 has no source video and is not scored); **7 of 7 ambulance passes detected**, 6 false events, mean confirmation 0.94 s after the window starts. Leave-one-video-out estimate: 7 of 7, 11 false events. With `cls_v4-2` (`tracking_scores_cls_v4-2.md`): 6 of 7, 13 false events, 0.26 s |
| Recall improvement (mid-report 6.10, 7.7) | `train_cls_v5.py --compare`, val split (below) |

## Classifier runs on the GPU (RTX 4050 laptop, cleaned crops, val split)

All runs: yolo26n-cls, 30 epochs, batch 128. `cls_v4-2` is the mid-report model (trained before the
duplicate clean-up); `cls_v5_base` repeats its settings on the cleaned data.

| run | change | PR-AUC | recall@0.5 | precision@0.5 | F1@0.5 |
|---|---|---|---|---|---|
| cls_v4-2 | mid-report model | 0.973 | 0.918 | 0.956 | 0.937 |
| cls_v5_base | same settings, cleaned data | 0.975 | 0.918 | 0.945 | 0.931 |
| cls_v5_img128 | input 128 px | **0.979** | 0.928 | 0.950 | **0.939** |
| cls_v5_os2 | ambulance crops x2 | 0.975 | **0.937** | 0.928 | 0.933 |

Val recall of `cls_v4-2` rose from 91.0% to 91.8% after removing the 4 mislabelled copies (all 4 had been
counted as missed ambulances).

`cls_v5_img128` was chosen on val and then run once on the test split, where it beats `cls_v4-2` on every
metric (above). It is now the pipeline model: `Projects/track_pipeline.py`, `ambulance_4way_monitor.py`,
`eval_detector.py` defaults and `backend/config.live.yaml` (`cls_imgsz: 128`).

With the old voting thresholds (tuned for `cls_v4-2`: `TH_FRAME` 0.6, `MEAN_MIN` 0.65, 5 of 8 votes) it halved
false events on the real videos (13 -> 6) but detected one pass fewer (5 of 7).

### Re-tuning the voting thresholds (`Projects/tune_tracking.py`)

`tune_tracking.py dump` records every track's per-frame ambulance probability once (GPU);
`tune_tracking.py sweep` replays track_pipeline.py's voting rule offline for 360 settings
(`TH_FRAME` 0.30-0.75, `MEAN_MIN` 0.40-0.80, K 3-6 of M 8). The replay reproduces the pipeline's
confirmations exactly on all 12 videos at the old setting. Results: `Projects/tracking_out/tune/tune.md`, `sweep.csv`.

| setting | TH_FRAME | MEAN_MIN | K of M | passes detected | false events | mean latency |
|---|---|---|---|---|---|---|
| old | 0.6 | 0.65 | 5 of 8 | 5 of 7 | 6 | 0.99 s |
| **new** | 0.6 | **0.70** | **3 of 8** | **7 of 7** | 6 | 0.94 s |

K is what matters: every K = 3 setting with `MEAN_MIN` 0.70-0.75 detects 7 of 7 with 6 false events, whatever
`TH_FRAME` is (0.30-0.75); K = 4 or 5 detect 5 of 7. `TH_FRAME` stays at 0.6 and `MEAN_MIN` 0.70 is inside that
range, not at its edge. Applied in `track_pipeline.py`, `ambulance_4way_monitor.py` and `backend/config.live.yaml`
(the backend's built-in default stays 5 of 8). The re-run of the real pipeline gives the same numbers.

The same videos choose and score the setting, so the in-sample 7 of 7 is optimistic. Leave-one-video-out (setting
chosen on the other 11 videos, scored on the held-out one) gives 7 of 7 passes and 11 false events: when test5 is
held out, the setting chosen without it is looser and fires 8 times on test5. Remaining false events: test5
(3, confirmed clip with no ambulance), test12 (2, at 76.6 s, 1.4 s before the labelled pass) and test4 (1).

Environment note (this laptop): Windows Smart App Control blocks torchvision's CUDA extension and `lap`'s
`_lapjv.pyd`. Runs used torch 2.14.1+cu126 with torchvision 0.29.1+cpu, Ultralytics' own `TorchNMS.nms` as the
CUDA NMS kernel, and ByteTrack's SciPy assignment (`use_lap=False`) instead of lap.

Ground truth: `test5` checked, it has no ambulance, so its confirmations are real false events. `test7` has no
source video and was removed from `ground_truth.csv`.

## Commands for everything else

```bash
cd backend && pytest                                  # 40 tests
python scripts/scripted_scenario.py                   # exit test (PASS)
cd ../sumo
python run_matrix.py && python aggregate.py           # ~45 min on 2 cores
python benchmark.py && python make_plots.py && python latex_tables.py
```
