# Ambulance recogniser: test split

Weights `best.pt`, threshold 0.0511, device cpu, 2026-11-25T21:02:32.

Images: 768 ambulance, 2953 other vehicle.

Threshold 0.0511 was chosen on the **val** split as the highest giving ambulance recall >= 0.95 there (val recall 0.952, precision 0.813); the test split was not used to choose it.

| | true ambulance | true other |
|---|---|---|
| predicted ambulance | 735 (TP) | 103 (FP) |
| predicted other | 33 (FN) | 2850 (TN) |

| Metric | Value |
|---|---|
| Accuracy | 96.3% (majority-class baseline 79.4%) |
| Ambulance precision | 87.7% |
| Ambulance recall | 95.7% |
| F1 | 0.915 |
| False-alarm rate | 3.5% |
| Balanced accuracy | 96.1% |
| ROC-AUC | 0.993 |
| PR-AUC (average precision) | 0.981 |

Best F1 over thresholds: 0.943 at 0.55 (precision 96.1%, recall 92.6%).

| Source | ambulance | other | recall | false-alarm rate |
|---|---|---|---|---|
| local | 0 | 89 | n/a | 1.1% |
| pk | 235 | 0 | 92.3% | n/a |
| pub | 533 | 2864 | 97.2% | 3.6% |
