# Results: held-out evaluation

180 one-hour SUMO runs. Seeds 6, 7, 8, 9, 10 (the MARL controller was trained on seeds 1-5, so none of these were seen in training); 6 signalised networks x 4 demand levels per controller (the corridor ablation only on the two multi-junction networks). Values are mean ± 95% confidence interval over runs.

## Main comparison

| Metric | Actuated | Fixed-time + priority | EquiFlow |
|---|---|---|---|
| Car mean wait (s) | 7.19 ± 2.33 | 11.09 ± 1.87 | 6.53 ± 1.40 |
| All ordinary vehicles, mean wait (s) | 7.16 ± 2.31 | 11.14 ± 1.90 | 6.46 ± 1.39 |
| 95th-percentile wait (s) | 20.53 ± 4.83 | 33.93 ± 4.91 | 21.80 ± 2.86 |
| Longest single wait (s) | 45.43 ± 9.27 | 76.13 ± 18.74 | 57.30 ± 10.79 |
| Vehicles waiting > 60 s (share) | 0.003 ± 0.002 | 0.009 ± 0.006 | 0.002 ± 0.002 |
| Worst approach, mean wait (s) | 8.91 ± 2.56 | 13.95 ± 2.24 | 7.90 ± 1.47 |
| Jain fairness index across approaches (1 = equal) | 0.901 ± 0.050 | 0.909 ± 0.047 | 0.921 ± 0.050 |
| Vehicles held by an ambulance, mean wait (s) | 13.17 ± 2.99 | 26.23 ± 3.36 | 20.03 ± 1.93 |
| Vehicles held by an ambulance, 95th-percentile wait (s) | 27.93 ± 6.27 | 46.84 ± 6.90 | 37.29 ± 5.55 |
| Ambulance mean wait (s) | 7.67 ± 2.36 | 0.15 ± 0.06 | 0.13 ± 0.05 |
| Ambulance mean travel time (s) | 53.98 ± 4.82 | 44.29 ± 4.45 | 43.59 ± 4.53 |
| Detection to green (s) | – | 2.58 ± 0.21 | 2.67 ± 0.14 |
| Recovery interval after priority (s) | – | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Runs | 30 | 30 | 30 |

## Ablations (what each part of EquiFlow contributes)

| Metric | EquiFlow | EquiFlow + recovery (queue) | EquiFlow + recovery (re-order) | EquiFlow + recovery (first rule) |
|---|---|---|---|---|
| Car mean wait (s) | 6.53 ± 1.40 | 6.74 ± 1.43 | 6.57 ± 1.38 | 7.07 ± 1.51 |
| All ordinary vehicles, mean wait (s) | 6.46 ± 1.39 | 6.69 ± 1.43 | 6.54 ± 1.38 | 7.15 ± 1.59 |
| 95th-percentile wait (s) | 21.80 ± 2.86 | 23.06 ± 3.30 | 22.03 ± 2.89 | 25.84 ± 4.07 |
| Longest single wait (s) | 57.30 ± 10.79 | 54.77 ± 9.09 | 55.60 ± 10.73 | 59.83 ± 12.76 |
| Vehicles waiting > 60 s (share) | 0.002 ± 0.002 | 0.002 ± 0.002 | 0.002 ± 0.002 | 0.002 ± 0.002 |
| Worst approach, mean wait (s) | 7.90 ± 1.47 | 8.06 ± 1.52 | 7.80 ± 1.49 | 8.62 ± 1.67 |
| Jain fairness index across approaches (1 = equal) | 0.921 ± 0.050 | 0.925 ± 0.048 | 0.929 ± 0.045 | 0.920 ± 0.051 |
| Vehicles held by an ambulance, mean wait (s) | 20.03 ± 1.93 | 20.41 ± 2.10 | 19.84 ± 1.99 | 20.97 ± 2.13 |
| Vehicles held by an ambulance, 95th-percentile wait (s) | 37.29 ± 5.55 | 36.76 ± 4.96 | 35.88 ± 5.00 | 39.65 ± 5.87 |
| Ambulance mean wait (s) | 0.13 ± 0.05 | 0.12 ± 0.05 | 0.14 ± 0.06 | 0.18 ± 0.09 |
| Ambulance mean travel time (s) | 43.59 ± 4.53 | 43.59 ± 4.50 | 43.60 ± 4.51 | 43.65 ± 4.50 |
| Detection to green (s) | 2.67 ± 0.14 | 2.65 ± 0.13 | 2.66 ± 0.12 | 2.71 ± 0.20 |
| Recovery interval after priority (s) | 0.00 ± 0.00 | 25.45 ± 2.74 | 23.64 ± 2.42 | 30.83 ± 3.55 |
| Runs | 30 | 30 | 30 | 30 |

The two corridor ablations run only on sector_grid and diamond; compare them with EquiFlow on those networks in paired.csv (the paired rows use matched runs only).

## Paired comparison: EquiFlow minus each controller, on identical runs

Negative = EquiFlow lower (for waits, better). * = the 95% CI excludes 0. Win share = runs where EquiFlow is better.

| Versus | Metric | Mean difference ± 95% CI | EquiFlow wins | Runs |
|---|---|---|---|---|
| Actuated | Car mean wait (s) | -0.66 ± 1.24 | 47% | 30 |
| Actuated | 95th-percentile wait (s) | 1.27 ± 2.53 | 33% | 30 |
| Actuated | Longest single wait (s) | 11.87 ± 6.86 * | 33% | 30 |
| Actuated | Jain fairness index across approaches (1 = equal) | 0.020 ± 0.014 * | 70% | 30 |
| Actuated | Vehicles held by an ambulance, mean wait (s) | 6.86 ± 1.60 * | 17% | 30 |
| Actuated | Ambulance mean wait (s) | -7.54 ± 2.34 * | 100% | 30 |
| Fixed-time + priority | Car mean wait (s) | -4.55 ± 0.65 * | 100% | 30 |
| Fixed-time + priority | 95th-percentile wait (s) | -12.12 ± 2.38 * | 100% | 30 |
| Fixed-time + priority | Longest single wait (s) | -18.83 ± 9.80 * | 80% | 30 |
| Fixed-time + priority | Jain fairness index across approaches (1 = equal) | 0.012 ± 0.008 * | 73% | 30 |
| Fixed-time + priority | Vehicles held by an ambulance, mean wait (s) | -6.20 ± 1.64 * | 100% | 30 |
| Fixed-time + priority | Ambulance mean wait (s) | -0.02 ± 0.05 | 53% | 30 |
| Fixed-time + priority | Recovery interval after priority (s) | 0.00 ± 0.00 | 0% | 30 |
| EquiFlow + recovery (queue) | Car mean wait (s) | -0.20 ± 0.21 | 70% | 30 |
| EquiFlow + recovery (queue) | 95th-percentile wait (s) | -1.26 ± 0.86 * | 50% | 30 |
| EquiFlow + recovery (queue) | Longest single wait (s) | 2.53 ± 5.55 | 37% | 30 |
| EquiFlow + recovery (queue) | Jain fairness index across approaches (1 = equal) | -0.004 ± 0.005 | 43% | 30 |
| EquiFlow + recovery (queue) | Vehicles held by an ambulance, mean wait (s) | -0.38 ± 0.74 | 47% | 30 |
| EquiFlow + recovery (queue) | Ambulance mean wait (s) | 0.00 ± 0.03 | 43% | 30 |
| EquiFlow + recovery (queue) | Recovery interval after priority (s) | -25.45 ± 2.74 * | 100% | 30 |
| EquiFlow + recovery (re-order) | Car mean wait (s) | -0.03 ± 0.17 | 47% | 30 |
| EquiFlow + recovery (re-order) | 95th-percentile wait (s) | -0.22 ± 0.49 | 37% | 30 |
| EquiFlow + recovery (re-order) | Longest single wait (s) | 1.70 ± 4.40 | 30% | 30 |
| EquiFlow + recovery (re-order) | Jain fairness index across approaches (1 = equal) | -0.008 ± 0.006 * | 27% | 30 |
| EquiFlow + recovery (re-order) | Vehicles held by an ambulance, mean wait (s) | 0.19 ± 0.52 | 37% | 30 |
| EquiFlow + recovery (re-order) | Ambulance mean wait (s) | -0.01 ± 0.04 | 33% | 30 |
| EquiFlow + recovery (re-order) | Recovery interval after priority (s) | -23.64 ± 2.42 * | 100% | 30 |
| EquiFlow + recovery (first rule) | Car mean wait (s) | -0.54 ± 0.31 * | 77% | 30 |
| EquiFlow + recovery (first rule) | 95th-percentile wait (s) | -4.03 ± 1.53 * | 87% | 30 |
| EquiFlow + recovery (first rule) | Longest single wait (s) | -2.53 ± 5.28 | 47% | 30 |
| EquiFlow + recovery (first rule) | Jain fairness index across approaches (1 = equal) | 0.002 ± 0.005 | 57% | 30 |
| EquiFlow + recovery (first rule) | Vehicles held by an ambulance, mean wait (s) | -0.94 ± 0.65 * | 67% | 30 |
| EquiFlow + recovery (first rule) | Ambulance mean wait (s) | -0.05 ± 0.06 | 43% | 30 |
| EquiFlow + recovery (first rule) | Recovery interval after priority (s) | -30.83 ± 3.55 * | 100% | 30 |

## By demand level (car mean wait, s)

| Demand | Actuated | Fixed-time + priority | EquiFlow |
|---|---|---|---|
| emergency | 7.19 ± 2.33 | 11.09 ± 1.87 | 6.53 ± 1.40 |

## By demand level (95th-percentile wait, s)

| Demand | Actuated | Fixed-time + priority | EquiFlow |
|---|---|---|---|
| emergency | 20.53 ± 4.83 | 33.93 ± 4.91 | 21.80 ± 2.86 |
