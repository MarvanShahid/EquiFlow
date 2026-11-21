# Results: held-out evaluation

1000 one-hour SUMO runs. Seeds 6, 7, 8, 9, 10 (the MARL controller was trained on seeds 1-5, so none of these were seen in training); 6 signalised networks x 4 demand levels per controller (the corridor ablation only on the two multi-junction networks). Values are mean ± 95% confidence interval over runs.

## Main comparison

| Metric | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| Car mean wait (s) | 16.87 ± 1.02 | 6.28 ± 1.01 | 10.38 ± 0.86 | 5.38 ± 0.44 | 5.39 ± 0.54 |
| All ordinary vehicles, mean wait (s) | 17.07 ± 1.05 | 6.23 ± 0.99 | 10.30 ± 0.84 | 5.36 ± 0.43 | 5.34 ± 0.54 |
| 95th-percentile wait (s) | 51.71 ± 1.61 | 17.87 ± 2.13 | 29.55 ± 1.69 | 18.45 ± 1.18 | 20.31 ± 1.58 |
| Longest single wait (s) | 72.17 ± 3.72 | 36.71 ± 4.45 | 58.98 ± 5.08 | 39.44 ± 3.11 | 42.67 ± 3.50 |
| Vehicles waiting > 60 s (share) | 0.030 ± 0.005 | 0.002 ± 0.001 | 0.002 ± 0.001 | 0.000 ± 0.000 | 0.001 ± 0.001 |
| Worst approach, mean wait (s) | 21.98 ± 1.37 | 7.95 ± 1.10 | 13.49 ± 1.02 | 6.92 ± 0.52 | 6.97 ± 0.61 |
| Jain fairness index across approaches (1 = equal) | 0.915 ± 0.025 | 0.888 ± 0.025 | 0.903 ± 0.025 | 0.909 ± 0.024 | 0.896 ± 0.027 |
| Ambulance mean wait (s) | 13.75 ± 1.16 | 7.42 ± 1.31 | 0.19 ± 0.08 | 0.10 ± 0.06 | 0.07 ± 0.04 |
| Ambulance mean travel time (s) | 59.14 ± 2.42 | 52.75 ± 2.40 | 43.11 ± 2.19 | 42.68 ± 2.20 | 42.72 ± 2.21 |
| Detection to green (s) | – | – | 2.58 ± 0.16 | 2.41 ± 0.12 | 2.51 ± 0.14 |
| Recovery interval after priority (s) | – | – | 0.00 ± 0.00 | 22.99 ± 0.96 | 22.70 ± 0.92 |
| Runs | 120 | 120 | 120 | 120 | 120 |

## Ablations (what each part of EquiFlow contributes)

| Metric | EquiFlow | EquiFlow, old recovery rule | EquiFlow, no recovery | EquiFlow, no gap-out | EquiFlow, no corridor |
|---|---|---|---|---|---|
| Car mean wait (s) | 5.38 ± 0.44 | 5.48 ± 0.48 | 5.35 ± 0.42 | 6.57 ± 0.54 | 4.80 ± 0.42 |
| All ordinary vehicles, mean wait (s) | 5.36 ± 0.43 | 5.46 ± 0.46 | 5.30 ± 0.41 | 6.51 ± 0.54 | 4.77 ± 0.41 |
| 95th-percentile wait (s) | 18.45 ± 1.18 | 19.08 ± 1.35 | 18.37 ± 1.16 | 20.68 ± 1.38 | 16.09 ± 0.91 |
| Longest single wait (s) | 39.44 ± 3.11 | 41.72 ± 3.41 | 38.83 ± 3.09 | 42.54 ± 3.34 | 32.00 ± 2.42 |
| Vehicles waiting > 60 s (share) | 0.000 ± 0.000 | 0.001 ± 0.000 | 0.000 ± 0.000 | 0.001 ± 0.000 | 0.000 ± 0.000 |
| Worst approach, mean wait (s) | 6.92 ± 0.52 | 6.97 ± 0.53 | 6.84 ± 0.49 | 8.30 ± 0.63 | 7.46 ± 0.61 |
| Jain fairness index across approaches (1 = equal) | 0.909 ± 0.024 | 0.910 ± 0.025 | 0.910 ± 0.025 | 0.907 ± 0.024 | 0.774 ± 0.053 |
| Ambulance mean wait (s) | 0.10 ± 0.06 | 0.11 ± 0.05 | 0.12 ± 0.07 | 0.12 ± 0.06 | 0.02 ± 0.02 |
| Ambulance mean travel time (s) | 42.68 ± 2.20 | 42.75 ± 2.19 | 42.73 ± 2.20 | 42.85 ± 2.20 | 55.14 ± 4.60 |
| Detection to green (s) | 2.41 ± 0.12 | 2.55 ± 0.12 | 2.43 ± 0.12 | 2.47 ± 0.12 | 2.49 ± 0.18 |
| Recovery interval after priority (s) | 22.99 ± 0.96 | 28.09 ± 1.37 | 0.00 ± 0.00 | 27.05 ± 1.12 | 20.43 ± 0.48 |
| Runs | 120 | 120 | 120 | 120 | 40 |

The corridor ablation runs only on sector_grid and diamond; compare it with EquiFlow on those networks in paired.csv (the paired rows use matched runs only).

## Paired comparison: EquiFlow minus each controller, on identical runs

Negative = EquiFlow lower (for waits, better). * = the 95% CI excludes 0. Win share = runs where EquiFlow is better.

| Versus | Metric | Mean difference ± 95% CI | EquiFlow wins | Runs |
|---|---|---|---|---|
| Fixed-time | Car mean wait (s) | -11.49 ± 0.68 * | 100% | 120 |
| Fixed-time | 95th-percentile wait (s) | -33.26 ± 1.02 * | 100% | 120 |
| Fixed-time | Longest single wait (s) | -32.73 ± 3.28 * | 98% | 120 |
| Fixed-time | Jain fairness index across approaches (1 = equal) | -0.005 ± 0.004 * | 40% | 120 |
| Fixed-time | Ambulance mean wait (s) | -13.64 ± 1.13 * | 100% | 120 |
| Actuated | Car mean wait (s) | -0.90 ± 0.74 * | 38% | 120 |
| Actuated | 95th-percentile wait (s) | 0.58 ± 1.34 | 31% | 120 |
| Actuated | Longest single wait (s) | 2.73 ± 3.33 | 32% | 120 |
| Actuated | Jain fairness index across approaches (1 = equal) | 0.021 ± 0.006 * | 73% | 120 |
| Actuated | Ambulance mean wait (s) | -7.32 ± 1.30 * | 99% | 120 |
| Fixed-time + priority | Car mean wait (s) | -5.00 ± 0.49 * | 100% | 120 |
| Fixed-time + priority | 95th-percentile wait (s) | -11.09 ± 0.74 * | 100% | 120 |
| Fixed-time + priority | Longest single wait (s) | -19.53 ± 2.96 * | 92% | 120 |
| Fixed-time + priority | Jain fairness index across approaches (1 = equal) | 0.007 ± 0.004 * | 60% | 120 |
| Fixed-time + priority | Ambulance mean wait (s) | -0.09 ± 0.08 * | 28% | 120 |
| Fixed-time + priority | Recovery interval after priority (s) | 22.99 ± 0.96 * | 0% | 120 |
| EquiFlow (MARL) | Car mean wait (s) | -0.00 ± 0.17 | 43% | 120 |
| EquiFlow (MARL) | 95th-percentile wait (s) | -1.85 ± 0.56 * | 53% | 120 |
| EquiFlow (MARL) | Longest single wait (s) | -3.23 ± 2.00 * | 58% | 120 |
| EquiFlow (MARL) | Jain fairness index across approaches (1 = equal) | 0.014 ± 0.006 * | 62% | 120 |
| EquiFlow (MARL) | Ambulance mean wait (s) | 0.03 ± 0.04 | 10% | 120 |
| EquiFlow (MARL) | Recovery interval after priority (s) | 0.30 ± 0.22 * | 35% | 120 |
| EquiFlow, no recovery | Car mean wait (s) | 0.03 ± 0.09 | 48% | 120 |
| EquiFlow, no recovery | 95th-percentile wait (s) | 0.08 ± 0.23 | 30% | 120 |
| EquiFlow, no recovery | Longest single wait (s) | 0.61 ± 1.58 | 35% | 120 |
| EquiFlow, no recovery | Jain fairness index across approaches (1 = equal) | -0.000 ± 0.004 | 47% | 120 |
| EquiFlow, no recovery | Ambulance mean wait (s) | -0.02 ± 0.06 | 12% | 120 |
| EquiFlow, no recovery | Recovery interval after priority (s) | 22.99 ± 0.96 * | 0% | 120 |
| EquiFlow, no gap-out | Car mean wait (s) | -1.18 ± 0.16 * | 97% | 120 |
| EquiFlow, no gap-out | 95th-percentile wait (s) | -2.22 ± 0.34 * | 84% | 120 |
| EquiFlow, no gap-out | Longest single wait (s) | -3.10 ± 1.70 * | 62% | 120 |
| EquiFlow, no gap-out | Jain fairness index across approaches (1 = equal) | 0.003 ± 0.004 | 52% | 120 |
| EquiFlow, no gap-out | Ambulance mean wait (s) | -0.02 ± 0.04 | 20% | 120 |
| EquiFlow, no gap-out | Recovery interval after priority (s) | -4.06 ± 0.40 * | 99% | 120 |
| EquiFlow, no corridor | Car mean wait (s) | 0.16 ± 0.11 * | 32% | 40 |
| EquiFlow, no corridor | 95th-percentile wait (s) | 0.54 ± 0.32 * | 12% | 40 |
| EquiFlow, no corridor | Longest single wait (s) | 8.22 ± 3.86 * | 20% | 40 |
| EquiFlow, no corridor | Jain fairness index across approaches (1 = equal) | 0.005 ± 0.007 | 60% | 40 |
| EquiFlow, no corridor | Ambulance mean wait (s) | 0.00 ± 0.02 | 5% | 40 |
| EquiFlow, no corridor | Recovery interval after priority (s) | 0.79 ± 0.32 * | 12% | 40 |
| EquiFlow, old recovery rule | Car mean wait (s) | -0.10 ± 0.09 * | 53% | 120 |
| EquiFlow, old recovery rule | 95th-percentile wait (s) | -0.62 ± 0.31 * | 48% | 120 |
| EquiFlow, old recovery rule | Longest single wait (s) | -2.27 ± 1.73 * | 56% | 120 |
| EquiFlow, old recovery rule | Jain fairness index across approaches (1 = equal) | -0.001 ± 0.003 | 47% | 120 |
| EquiFlow, old recovery rule | Ambulance mean wait (s) | -0.01 ± 0.05 | 15% | 120 |
| EquiFlow, old recovery rule | Recovery interval after priority (s) | -5.10 ± 0.60 * | 100% | 120 |

## By demand level (car mean wait, s)

| Demand | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| low | 16.13 ± 2.00 | 5.32 ± 1.76 | 9.47 ± 1.66 | 4.34 ± 0.70 | 3.90 ± 0.86 |
| medium | 16.70 ± 2.09 | 6.09 ± 2.08 | 10.10 ± 1.73 | 4.93 ± 0.75 | 5.01 ± 1.03 |
| high | 17.67 ± 2.19 | 7.25 ± 2.35 | 11.49 ± 1.99 | 6.92 ± 1.14 | 7.11 ± 1.30 |
| asymmetric | 16.99 ± 2.16 | 6.47 ± 2.12 | 10.45 ± 1.72 | 5.34 ± 0.70 | 5.53 ± 0.93 |

## By demand level (95th-percentile wait, s)

| Demand | Fixed-time | Actuated | Fixed-time + priority | EquiFlow | EquiFlow (MARL) |
|---|---|---|---|---|---|
| low | 50.81 ± 3.25 | 15.69 ± 3.79 | 28.26 ± 3.24 | 15.50 ± 1.88 | 17.21 ± 2.79 |
| medium | 51.24 ± 3.35 | 16.98 ± 4.36 | 28.69 ± 3.34 | 17.31 ± 2.02 | 19.38 ± 3.10 |
| high | 52.43 ± 3.42 | 20.76 ± 4.93 | 31.57 ± 4.17 | 22.44 ± 3.05 | 23.82 ± 3.67 |
| asymmetric | 52.36 ± 3.36 | 18.07 ± 4.40 | 29.67 ± 3.18 | 18.57 ± 1.92 | 20.81 ± 3.06 |

## MARL on network/demand combinations it was and was not trained on

MARL minus adaptive EquiFlow on identical runs (negative = MARL better). All seeds are unseen.

| Metric | trained combinations | unseen combinations |
|---|---|---|
| Car mean wait (s) | 0.13 ± 0.30 (n=40) | -0.06 ± 0.22 (n=80) |
| 95th-percentile wait (s) | 1.77 ± 0.93 (n=40) | 1.89 ± 0.71 (n=80) |
| Jain fairness index across approaches (1 = equal) | -0.008 ± 0.007 (n=40) | -0.017 ± 0.008 (n=80) |
| Ambulance mean wait (s) | -0.03 ± 0.02 (n=40) | -0.03 ± 0.07 (n=80) |
