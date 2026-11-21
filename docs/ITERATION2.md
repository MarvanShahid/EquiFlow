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
| FR-05 | Missing / stale detections handled safely | Done | 5-of-8 vote, 4 s release, 60 s fail-safe, external events older than 2 s rejected (`preempt.stale_s`) | `test_tc03_...` |
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
| TC-01 / TC-02 detector on labelled test images | **Script ready, run on DELL** | `Projects/eval_detector.py` |
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
| Dataset documented, no duplicates across splits | **Script ready, run on DELL**: `Projects/make_split_manifest.py` (manifest with SHA-1 + dHash, exact and near-duplicate check) |
| Detection on test split, precision/recall/F1, errors | **Script ready, run on DELL**: `Projects/eval_detector.py` |
| Safety tests | Done |
| Scripted emergency trip logged | Done |
| Recovery interval and waiting-time distribution recorded | Done: `recovery_s_mean`, p50/p95/p99/max wait, share > 60 s, worst approach, Jain index per run |
| 3+ repeatable runs per scenario | Done: 5 seeds (6-10) per network x demand x controller |
| Reproducible by another member | Done: `run_manifest.csv`, `backend/requirements.lock.txt`, one command per step |

## Non-functional requirements

| | Status |
|---|---|
| Safety | Tested (randomized: never two non-red lamps; yellow and all-red always honoured) |
| Performance | `sumo/results/performance.md`: controller tick ~1 µs, MARL decision ~24 µs; 1 h of SUMO in ~3 s. Detector latency: `eval_detector.py` on DELL |
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
| Tracking on real video | `Projects/tracking_out/tracking_scores.md` (8 of 13 videos processed) |

## Still to run on the DELL machine (needs the crops dataset / GPU / videos)

```bash
cd Projects
python make_split_manifest.py --data <crops folder>            # split manifest + leakage check
python eval_detector.py --data <crops folder> --split val      # should reproduce 98.2% acc, 91.0% recall
python eval_detector.py --data <crops folder>                  # TEST split + latency -> runs/eval_test/summary.md
python eval_detector.py --data <crops folder> --target-recall 0.95   # threshold chosen on val, reported on test
python train_cls_v5.py --data <crops folder> --name cls_v5_img128 --imgsz 128     # recall improvement runs
python train_cls_v5.py --data <crops folder> --name cls_v5_os2 --oversample 2
python train_cls_v5.py --compare cls_v4-2 cls_v5_img128 cls_v5_os2
python track_pipeline.py      # on test6, test7, test8, test11, v2, then:  python score_tracking.py
```
Also check the ground truth of `test5` (9 confirmations in a clip labelled "no ambulance").

## Commands for everything else

```bash
cd backend && pytest                                  # 40 tests
python scripts/scripted_scenario.py                   # exit test (PASS)
cd ../sumo
python run_matrix.py && python aggregate.py           # ~45 min on 2 cores
python benchmark.py && python make_plots.py && python latex_tables.py
```
