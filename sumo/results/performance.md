# Performance

Machine: x86_64, Linux-6.18.44-fc-v470-x86_64-with-glibc2.39, Python 3.13.18. One CPU core per measurement.

## Signal controller

| Measured | mean | median | p99 | max |
|---|---|---|---|---|
| tick (fixed_time) | 0.94 µs | 0.92 µs | 3.21 µs | 99.37 µs |
| decision (fixed_time) | 0.42 µs | 0.38 µs | 0.63 µs | 467.97 µs |
| tick (adaptive) | 1.07 µs | 0.95 µs | 3.77 µs | 680.95 µs |
| decision (adaptive) | 1.39 µs | 1.2 µs | 2.68 µs | 935.52 µs |
| tick (marl) | 1.35 µs | 0.94 µs | 5.07 µs | 173.0 µs |
| decision (marl) | 23.83 µs | 19.82 µs | 61.69 µs | 4408.28 µs |

The live backend ticks every 0.1 s (100 000 µs), so the controller uses well under 1% of that budget.

## Simulation throughput (1-hour SUMO runs, 1 s steps, from the run matrix)

| Controller | simulated s per wall-clock s (mean) | slowest run | runs |
|---|---|---|---|
| actuated | 1420.4 | 818.2 | 120 |
| equiflow | 1390.9 | 660.6 | 120 |
| equiflow-marl | 1341.5 | 661.8 | 120 |
| equiflow-nocorridor | 1107.6 | 707.3 | 40 |
| equiflow-nogapout | 1354.9 | 727.3 | 120 |
| equiflow-norecovery | 1278.4 | 653.4 | 120 |
| equiflow-recovery-v1 | 1280.9 | 672.9 | 120 |
| fixed | 1322.8 | 678.0 | 120 |
| fixed+preempt | 1332.2 | 659.3 | 120 |

Runs were executed two at a time, so per-run numbers include sharing the CPU.

Detector and classifier latency: see `Projects/runs/eval_test/summary.md` (run `Projects/eval_detector.py`).
