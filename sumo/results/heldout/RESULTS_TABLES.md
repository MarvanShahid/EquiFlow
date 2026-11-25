# Results: held-out evaluation

1400 one-hour SUMO runs. Seeds 6, 7, 8, 9, 10 (the MARL controller was trained on seeds 1-5, so none of these were seen in training); 6 signalised networks x 4 demand levels per controller (the corridor ablation only on the two multi-junction networks). Values are mean ± 95% confidence interval over runs.

## Main comparison

| Metric | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| Car mean wait (s) | 16.87 ± 1.02 | 6.28 ± 1.01 | 10.36 ± 0.86 | 4.28 ± 0.57 | 4.05 ± 0.53 |
| All ordinary vehicles, mean wait (s) | 17.07 ± 1.05 | 6.23 ± 0.99 | 10.29 ± 0.84 | 4.32 ± 0.56 | 4.10 ± 0.52 |
| 95th-percentile wait (s) | 51.71 ± 1.61 | 17.87 ± 2.13 | 29.44 ± 1.69 | 16.91 ± 1.31 | 18.34 ± 1.65 |
| Longest single wait (s) | 72.17 ± 3.72 | 36.71 ± 4.45 | 57.69 ± 5.03 | 39.84 ± 3.34 | 42.69 ± 3.72 |
| Vehicles waiting > 60 s (share) | 0.030 ± 0.005 | 0.002 ± 0.001 | 0.002 ± 0.001 | 0.001 ± 0.000 | 0.001 ± 0.001 |
| Worst approach, mean wait (s) | 21.98 ± 1.37 | 7.95 ± 1.10 | 13.40 ± 1.01 | 5.63 ± 0.59 | 5.49 ± 0.58 |
| Jain fairness index across approaches (1 = equal) | 0.915 ± 0.025 | 0.888 ± 0.025 | 0.904 ± 0.025 | 0.878 ± 0.030 | 0.879 ± 0.029 |
| Vehicles held by an ambulance, mean wait (s) | 36.17 ± 1.16 | 12.39 ± 1.37 | 25.22 ± 1.63 | 19.64 ± 1.35 | 19.55 ± 1.43 |
| Vehicles held by an ambulance, 95th-percentile wait (s) | 56.02 ± 2.19 | 22.53 ± 3.00 | 39.75 ± 3.26 | 29.47 ± 2.18 | 31.80 ± 3.17 |
| Ambulance mean wait (s) | 13.75 ± 1.16 | 7.42 ± 1.31 | 0.19 ± 0.08 | 0.10 ± 0.06 | 0.10 ± 0.05 |
| Ambulance mean travel time (s) | 59.14 ± 2.42 | 52.75 ± 2.40 | 43.19 ± 2.21 | 42.68 ± 2.22 | 42.54 ± 2.22 |
| Detection to green (s) | – | – | 2.57 ± 0.17 | 2.37 ± 0.13 | 2.39 ± 0.16 |
| Recovery interval after priority (s) | – | – | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Runs | 120 | 120 | 120 | 120 | 120 |

## Ablations (what each part of EquiFlow contributes)

| Metric | EquiFlow | EquiFlow, no green extension | EquiFlow, no gap-out | EquiFlow, first tail settings | EquiFlow + recovery (queue) | EquiFlow + recovery (re-order) | EquiFlow + recovery (first rule) | EquiFlow + corridor (just in time) | EquiFlow + corridor (25 s ETA) |
|---|---|---|---|---|---|---|---|---|---|
| Car mean wait (s) | 4.28 ± 0.57 | 5.62 ± 0.49 | 5.43 ± 0.71 | 3.96 ± 0.48 | 4.36 ± 0.58 | 4.33 ± 0.58 | 4.42 ± 0.61 | 2.61 ± 0.37 | 2.61 ± 0.36 |
| All ordinary vehicles, mean wait (s) | 4.32 ± 0.56 | 5.61 ± 0.49 | 5.42 ± 0.69 | 3.97 ± 0.46 | 4.40 ± 0.57 | 4.39 ± 0.57 | 4.45 ± 0.60 | 2.61 ± 0.37 | 2.66 ± 0.37 |
| 95th-percentile wait (s) | 16.91 ± 1.31 | 18.07 ± 1.12 | 19.02 ± 1.41 | 17.35 ± 1.34 | 17.17 ± 1.32 | 17.16 ± 1.31 | 17.65 ± 1.49 | 13.63 ± 1.49 | 13.97 ± 1.54 |
| Longest single wait (s) | 39.84 ± 3.34 | 38.48 ± 3.82 | 42.21 ± 3.22 | 44.19 ± 3.08 | 39.78 ± 3.32 | 40.31 ± 3.60 | 41.99 ± 3.90 | 35.38 ± 3.75 | 39.52 ± 4.21 |
| Vehicles waiting > 60 s (share) | 0.001 ± 0.000 | 0.001 ± 0.000 | 0.001 ± 0.001 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.001 ± 0.000 | 0.001 ± 0.001 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| Worst approach, mean wait (s) | 5.63 ± 0.59 | 7.11 ± 0.55 | 6.79 ± 0.72 | 5.50 ± 0.53 | 5.71 ± 0.60 | 5.69 ± 0.61 | 5.85 ± 0.64 | 4.74 ± 0.64 | 4.89 ± 0.67 |
| Jain fairness index across approaches (1 = equal) | 0.878 ± 0.030 | 0.911 ± 0.025 | 0.889 ± 0.029 | 0.864 ± 0.032 | 0.881 ± 0.030 | 0.880 ± 0.030 | 0.877 ± 0.030 | 0.706 ± 0.053 | 0.703 ± 0.052 |
| Vehicles held by an ambulance, mean wait (s) | 19.64 ± 1.35 | 18.89 ± 1.00 | 20.50 ± 1.09 | 19.84 ± 1.17 | 19.66 ± 1.21 | 20.04 ± 1.32 | 19.77 ± 1.24 | 17.87 ± 1.02 | 22.20 ± 1.44 |
| Vehicles held by an ambulance, 95th-percentile wait (s) | 29.47 ± 2.18 | 28.78 ± 1.94 | 32.42 ± 2.50 | 30.95 ± 2.25 | 30.89 ± 2.31 | 31.43 ± 2.79 | 31.36 ± 2.68 | 26.48 ± 2.51 | 33.79 ± 2.82 |
| Ambulance mean wait (s) | 0.10 ± 0.06 | 0.13 ± 0.06 | 0.14 ± 0.08 | 0.10 ± 0.04 | 0.10 ± 0.05 | 0.10 ± 0.06 | 0.08 ± 0.03 | 0.03 ± 0.03 | 0.02 ± 0.02 |
| Ambulance mean travel time (s) | 42.68 ± 2.22 | 42.92 ± 2.22 | 42.82 ± 2.22 | 42.57 ± 2.22 | 42.65 ± 2.22 | 42.66 ± 2.22 | 42.63 ± 2.21 | 54.85 ± 4.62 | 54.80 ± 4.63 |
| Detection to green (s) | 2.37 ± 0.13 | 2.47 ± 0.13 | 2.31 ± 0.14 | 2.37 ± 0.14 | 2.42 ± 0.12 | 2.40 ± 0.13 | 2.39 ± 0.13 | 1.64 ± 0.13 | 2.34 ± 0.16 |
| Recovery interval after priority (s) | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 22.94 ± 0.94 | 21.61 ± 0.88 | 28.25 ± 1.35 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Runs | 120 | 120 | 120 | 120 | 120 | 120 | 120 | 40 | 40 |

The two corridor ablations run only on sector_grid and diamond; compare them with EquiFlow on those networks in paired.csv (the paired rows use matched runs only).

## Paired comparison: EquiFlow minus each controller, on identical runs

Negative = EquiFlow lower (for waits, better). * = the 95% CI excludes 0. Win share = runs where EquiFlow is better.

| Versus | Metric | Mean difference ± 95% CI | EquiFlow wins | Runs |
|---|---|---|---|---|
| Fixed-time | Car mean wait (s) | -12.59 ± 0.66 * | 100% | 120 |
| Fixed-time | 95th-percentile wait (s) | -34.80 ± 1.19 * | 100% | 120 |
| Fixed-time | Longest single wait (s) | -32.33 ± 3.77 * | 97% | 120 |
| Fixed-time | Jain fairness index across approaches (1 = equal) | -0.036 ± 0.013 * | 36% | 120 |
| Fixed-time | Vehicles held by an ambulance, mean wait (s) | -17.38 ± 1.72 * | 97% | 106 |
| Fixed-time | Ambulance mean wait (s) | -13.64 ± 1.13 * | 100% | 120 |
| Actuated | Car mean wait (s) | -2.00 ± 0.61 * | 68% | 120 |
| Actuated | 95th-percentile wait (s) | -0.96 ± 1.32 | 48% | 120 |
| Actuated | Longest single wait (s) | 3.13 ± 3.28 | 30% | 120 |
| Actuated | Jain fairness index across approaches (1 = equal) | -0.010 ± 0.013 | 47% | 120 |
| Actuated | Vehicles held by an ambulance, mean wait (s) | 6.42 ± 1.49 * | 19% | 104 |
| Actuated | Ambulance mean wait (s) | -7.32 ± 1.29 * | 99% | 120 |
| Fixed-time + priority | Car mean wait (s) | -6.08 ± 0.42 * | 100% | 120 |
| Fixed-time + priority | 95th-percentile wait (s) | -12.53 ± 0.82 * | 100% | 120 |
| Fixed-time + priority | Longest single wait (s) | -17.85 ± 3.19 * | 85% | 120 |
| Fixed-time + priority | Jain fairness index across approaches (1 = equal) | -0.026 ± 0.013 * | 38% | 120 |
| Fixed-time + priority | Vehicles held by an ambulance, mean wait (s) | -6.17 ± 1.32 * | 85% | 103 |
| Fixed-time + priority | Ambulance mean wait (s) | -0.09 ± 0.06 * | 28% | 120 |
| Fixed-time + priority | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 120 |
| EquiFlow (MARL) | Car mean wait (s) | 0.23 ± 0.18 * | 48% | 120 |
| EquiFlow (MARL) | 95th-percentile wait (s) | -1.43 ± 0.55 * | 60% | 120 |
| EquiFlow (MARL) | Longest single wait (s) | -2.85 ± 1.97 * | 62% | 120 |
| EquiFlow (MARL) | Jain fairness index across approaches (1 = equal) | -0.001 ± 0.008 | 54% | 120 |
| EquiFlow (MARL) | Vehicles held by an ambulance, mean wait (s) | 0.10 ± 1.48 | 53% | 104 |
| EquiFlow (MARL) | Ambulance mean wait (s) | 0.01 ± 0.05 | 12% | 120 |
| EquiFlow (MARL) | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 120 |
| EquiFlow, no gap-out | Car mean wait (s) | -1.15 ± 0.18 * | 99% | 120 |
| EquiFlow, no gap-out | 95th-percentile wait (s) | -2.11 ± 0.27 * | 91% | 120 |
| EquiFlow, no gap-out | Longest single wait (s) | -2.37 ± 1.94 * | 60% | 120 |
| EquiFlow, no gap-out | Jain fairness index across approaches (1 = equal) | -0.010 ± 0.006 * | 38% | 120 |
| EquiFlow, no gap-out | Vehicles held by an ambulance, mean wait (s) | -0.88 ± 1.37 | 57% | 105 |
| EquiFlow, no gap-out | Ambulance mean wait (s) | -0.04 ± 0.05 | 17% | 120 |
| EquiFlow, no gap-out | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 120 |
| EquiFlow, no green extension | Car mean wait (s) | -1.33 ± 0.18 * | 95% | 120 |
| EquiFlow, no green extension | 95th-percentile wait (s) | -1.16 ± 0.38 * | 59% | 120 |
| EquiFlow, no green extension | Longest single wait (s) | 1.36 ± 2.00 | 32% | 120 |
| EquiFlow, no green extension | Jain fairness index across approaches (1 = equal) | -0.033 ± 0.013 * | 34% | 120 |
| EquiFlow, no green extension | Vehicles held by an ambulance, mean wait (s) | 0.19 ± 1.05 | 52% | 106 |
| EquiFlow, no green extension | Ambulance mean wait (s) | -0.03 ± 0.04 | 21% | 120 |
| EquiFlow, no green extension | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 120 |
| EquiFlow, first tail settings | Car mean wait (s) | 0.32 ± 0.13 * | 34% | 120 |
| EquiFlow, first tail settings | 95th-percentile wait (s) | -0.44 ± 0.29 * | 41% | 120 |
| EquiFlow, first tail settings | Longest single wait (s) | -4.35 ± 2.09 * | 62% | 120 |
| EquiFlow, first tail settings | Jain fairness index across approaches (1 = equal) | 0.014 ± 0.006 * | 65% | 120 |
| EquiFlow, first tail settings | Vehicles held by an ambulance, mean wait (s) | -0.53 ± 0.94 | 46% | 100 |
| EquiFlow, first tail settings | Ambulance mean wait (s) | 0.00 ± 0.05 | 11% | 120 |
| EquiFlow, first tail settings | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 120 |
| EquiFlow + recovery (queue) | Car mean wait (s) | -0.08 ± 0.07 * | 59% | 120 |
| EquiFlow + recovery (queue) | 95th-percentile wait (s) | -0.26 ± 0.21 * | 46% | 120 |
| EquiFlow + recovery (queue) | Longest single wait (s) | 0.06 ± 1.72 | 42% | 120 |
| EquiFlow + recovery (queue) | Jain fairness index across approaches (1 = equal) | -0.003 ± 0.005 | 42% | 120 |
| EquiFlow + recovery (queue) | Vehicles held by an ambulance, mean wait (s) | -0.21 ± 0.84 | 50% | 103 |
| EquiFlow + recovery (queue) | Ambulance mean wait (s) | 0.00 ± 0.03 | 9% | 120 |
| EquiFlow + recovery (queue) | Recovery interval after priority (s) | -22.94 ± 0.94 * | 100% | 120 |
| EquiFlow + recovery (re-order) | Car mean wait (s) | -0.05 ± 0.06 | 53% | 120 |
| EquiFlow + recovery (re-order) | 95th-percentile wait (s) | -0.25 ± 0.18 * | 40% | 120 |
| EquiFlow + recovery (re-order) | Longest single wait (s) | -0.47 ± 1.58 | 33% | 120 |
| EquiFlow + recovery (re-order) | Jain fairness index across approaches (1 = equal) | -0.001 ± 0.004 | 41% | 120 |
| EquiFlow + recovery (re-order) | Vehicles held by an ambulance, mean wait (s) | -0.19 ± 0.80 | 43% | 103 |
| EquiFlow + recovery (re-order) | Ambulance mean wait (s) | 0.00 ± 0.04 | 3% | 120 |
| EquiFlow + recovery (re-order) | Recovery interval after priority (s) | -21.61 ± 0.88 * | 100% | 120 |
| EquiFlow + recovery (first rule) | Car mean wait (s) | -0.14 ± 0.09 * | 59% | 120 |
| EquiFlow + recovery (first rule) | 95th-percentile wait (s) | -0.74 ± 0.34 * | 45% | 120 |
| EquiFlow + recovery (first rule) | Longest single wait (s) | -2.15 ± 1.81 * | 48% | 120 |
| EquiFlow + recovery (first rule) | Jain fairness index across approaches (1 = equal) | 0.001 ± 0.004 | 42% | 120 |
| EquiFlow + recovery (first rule) | Vehicles held by an ambulance, mean wait (s) | -0.41 ± 0.68 | 51% | 104 |
| EquiFlow + recovery (first rule) | Ambulance mean wait (s) | 0.02 ± 0.05 | 8% | 120 |
| EquiFlow + recovery (first rule) | Recovery interval after priority (s) | -28.25 ± 1.35 * | 100% | 120 |
| EquiFlow + corridor (just in time) | Car mean wait (s) | -0.06 ± 0.07 | 40% | 40 |
| EquiFlow + corridor (just in time) | 95th-percentile wait (s) | -0.37 ± 0.32 * | 32% | 40 |
| EquiFlow + corridor (just in time) | Longest single wait (s) | -0.17 ± 1.30 | 22% | 40 |
| EquiFlow + corridor (just in time) | Jain fairness index across approaches (1 = equal) | -0.003 ± 0.008 | 28% | 40 |
| EquiFlow + corridor (just in time) | Vehicles held by an ambulance, mean wait (s) | -2.43 ± 1.31 * | 63% | 35 |
| EquiFlow + corridor (just in time) | Ambulance mean wait (s) | -0.02 ± 0.03 | 8% | 40 |
| EquiFlow + corridor (just in time) | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 40 |
| EquiFlow + corridor (25 s ETA) | Car mean wait (s) | -0.06 ± 0.07 | 55% | 40 |
| EquiFlow + corridor (25 s ETA) | 95th-percentile wait (s) | -0.71 ± 0.47 * | 52% | 40 |
| EquiFlow + corridor (25 s ETA) | Longest single wait (s) | -4.33 ± 2.17 * | 60% | 40 |
| EquiFlow + corridor (25 s ETA) | Jain fairness index across approaches (1 = equal) | -0.000 ± 0.012 | 40% | 40 |
| EquiFlow + corridor (25 s ETA) | Vehicles held by an ambulance, mean wait (s) | -6.76 ± 1.91 * | 91% | 35 |
| EquiFlow + corridor (25 s ETA) | Ambulance mean wait (s) | -0.01 ± 0.02 | 2% | 40 |
| EquiFlow + corridor (25 s ETA) | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 40 |

## By demand level (car mean wait, s)

| Demand | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| low | 16.13 ± 2.00 | 5.32 ± 1.76 | 9.45 ± 1.66 | 2.54 ± 0.68 | 2.15 ± 0.50 |
| medium | 16.70 ± 2.09 | 6.09 ± 2.08 | 10.11 ± 1.71 | 3.88 ± 1.01 | 3.59 ± 0.78 |
| high | 17.67 ± 2.19 | 7.25 ± 2.35 | 11.48 ± 1.99 | 6.15 ± 1.46 | 6.26 ± 1.50 |
| asymmetric | 16.99 ± 2.16 | 6.47 ± 2.12 | 10.41 ± 1.71 | 4.57 ± 1.06 | 4.22 ± 0.78 |

## By demand level (95th-percentile wait, s)

| Demand | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| low | 50.81 ± 3.25 | 15.69 ± 3.79 | 28.16 ± 3.24 | 12.66 ± 2.35 | 13.17 ± 2.51 |
| medium | 51.24 ± 3.35 | 16.98 ± 4.36 | 28.64 ± 3.31 | 15.86 ± 2.44 | 17.24 ± 2.65 |
| high | 52.43 ± 3.42 | 20.76 ± 4.93 | 31.50 ± 4.17 | 21.10 ± 2.99 | 23.83 ± 4.48 |
| asymmetric | 52.36 ± 3.36 | 18.07 ± 4.40 | 29.47 ± 3.19 | 18.03 ± 2.04 | 19.13 ± 2.34 |

## MARL on network/demand combinations it was and was not trained on

MARL minus adaptive EquiFlow on identical runs (negative = MARL better). All seeds are unseen.

| Metric | trained combinations | unseen combinations |
|---|---|---|
| Car mean wait (s) | -0.23 ± 0.27 (n=40) | -0.23 ± 0.24 (n=80) |
| 95th-percentile wait (s) | 0.84 ± 0.54 (n=40) | 1.73 ± 0.77 (n=80) |
| Jain fairness index across approaches (1 = equal) | 0.001 ± 0.011 (n=40) | 0.001 ± 0.010 (n=80) |
| Ambulance mean wait (s) | 0.00 ± 0.03 (n=40) | -0.01 ± 0.07 (n=80) |
