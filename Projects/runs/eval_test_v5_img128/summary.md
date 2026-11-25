# Ambulance recogniser: test split

Weights `best.pt`, threshold 0.5, device 0, 2026-11-25T22:43:45.

Images: 768 ambulance, 2953 other vehicle.

| | true ambulance | true other |
|---|---|---|
| predicted ambulance | 718 (TP) | 26 (FP) |
| predicted other | 50 (FN) | 2927 (TN) |

| Metric | Value |
|---|---|
| Accuracy | 98.0% (majority-class baseline 79.4%) |
| Ambulance precision | 96.5% |
| Ambulance recall | 93.5% |
| F1 | 0.950 |
| False-alarm rate | 0.9% |
| Balanced accuracy | 96.3% |
| ROC-AUC | 0.995 |
| PR-AUC (average precision) | 0.985 |

Best F1 over thresholds: 0.950 at 0.6 (precision 97.3%, recall 92.8%).

| Source | ambulance | other | recall | false-alarm rate |
|---|---|---|---|---|
| local | 0 | 89 | n/a | 0.0% |
| pk | 235 | 0 | 88.1% | n/a |
| pub | 533 | 2864 | 95.9% | 0.9% |

## Latency (0)

| Stage | mean | median | p95 |
|---|---|---|---|
| classifier_batch1 | 14.2 ms | 12.8 ms | 24.6 ms |
| classifier_batch16 | 44.2 ms (2.76 ms per crop) | 42.4 ms | 53.5 ms |
| detector_frame | 58.5 ms | 61.7 ms | 72.3 ms |

Estimated time per frame for the full pipeline (detector + classifier per vehicle): 5 vehicles 72.3 ms, 10 vehicles 86.1 ms, 20 vehicles 113.7 ms.
