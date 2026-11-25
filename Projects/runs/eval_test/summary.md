# Ambulance recogniser: test split

Weights `best.pt`, threshold 0.5, device 0, 2026-11-25T21:41:55.

Images: 768 ambulance, 2953 other vehicle.

| | true ambulance | true other |
|---|---|---|
| predicted ambulance | 713 (TP) | 32 (FP) |
| predicted other | 55 (FN) | 2921 (TN) |

| Metric | Value |
|---|---|
| Accuracy | 97.7% (majority-class baseline 79.4%) |
| Ambulance precision | 95.7% |
| Ambulance recall | 92.8% |
| F1 | 0.942 |
| False-alarm rate | 1.1% |
| Balanced accuracy | 95.9% |
| ROC-AUC | 0.993 |
| PR-AUC (average precision) | 0.981 |

Best F1 over thresholds: 0.943 at 0.55 (precision 96.1%, recall 92.6%).

| Source | ambulance | other | recall | false-alarm rate |
|---|---|---|---|---|
| local | 0 | 89 | n/a | 0.0% |
| pk | 235 | 0 | 88.9% | n/a |
| pub | 533 | 2864 | 94.6% | 1.1% |

## Latency (0)

| Stage | mean | median | p95 |
|---|---|---|---|
| classifier_batch1 | 7.9 ms | 7.5 ms | 10.7 ms |
| classifier_batch16 | 27.4 ms (1.71 ms per crop) | 26.8 ms | 33.7 ms |
| detector_frame | 27.7 ms | 26.9 ms | 32.0 ms |

Estimated time per frame for the full pipeline (detector + classifier per vehicle): 5 vehicles 36.3 ms, 10 vehicles 44.8 ms, 20 vehicles 62.0 ms.
