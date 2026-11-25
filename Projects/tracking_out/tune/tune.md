# Re-tuning the tracker's voting thresholds

Videos: test1, test11, test12, test2, test3, test4, test5, test6, test8, test9, v1, v2.
Grid: th_frame 0.3-0.75, mean_min 0.4-0.8, k [3, 4, 5, 6] of m [8]: 360 settings.

| setting | th_frame | mean_min | k/m | passes detected | false events | mean latency (s) |
|---|---|---|---|---|---|---|
| current | 0.6 | 0.65 | 5/8 | 5 of 7 | 6 | 0.99 |
| best in-sample | 0.3 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |
| next best | 0.35 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |
| next best | 0.4 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |
| next best | 0.45 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |
| next best | 0.5 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |
| next best | 0.55 | 0.7 | 3/8 | 7 of 7 | 6 | 0.94 |

**Leave-one-video-out** (setting chosen without the scored video): 7 of 7 passes, 11 false events, mean latency 1.15 s.

| held-out video | setting chosen on the others (th_frame / mean_min / k) | detected | false |
|---|---|---|---|
| test1 | 0.3 / 0.7 / 3 | 1 of 1 | 0 |
| test11 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
| test12 | 0.75 / 0.6 / 3 | 3 of 3 | 2 |
| test2 | 0.3 / 0.7 / 3 | 1 of 1 | 0 |
| test3 | 0.3 / 0.7 / 3 | 1 of 1 | 0 |
| test4 | 0.3 / 0.7 / 3 | 1 of 1 | 1 |
| test5 | 0.5 / 0.45 / 3 | 0 of 0 | 8 |
| test6 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
| test8 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
| test9 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
| v1 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
| v2 | 0.3 / 0.7 / 3 | 0 of 0 | 0 |
