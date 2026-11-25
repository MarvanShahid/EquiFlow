# Ambulance recogniser: val split

Weights `best.pt`, threshold 0.5, device cpu, 2026-11-25T21:04:18.

Images: 429 ambulance, 2755 other vehicle.

| | true ambulance | true other |
|---|---|---|
| predicted ambulance | 394 (TP) | 18 (FP) |
| predicted other | 35 (FN) | 2737 (TN) |

| Metric | Value |
|---|---|
| Accuracy | 98.3% (majority-class baseline 86.5%) |
| Ambulance precision | 95.6% |
| Ambulance recall | 91.8% |
| F1 | 0.937 |
| False-alarm rate | 0.7% |
| Balanced accuracy | 95.6% |
| ROC-AUC | 0.992 |
| PR-AUC (average precision) | 0.973 |

Best F1 over thresholds: 0.939 at 0.6 (precision 96.3%, recall 91.6%).

| Source | ambulance | other | recall | false-alarm rate |
|---|---|---|---|---|
| local | 0 | 153 | n/a | 0.0% |
| pub | 429 | 2602 | 91.8% | 0.7% |
