# Tracking pipeline on the Islamabad videos

Ground truth: `ground_truth.csv`. A pass is detected if a confirmation falls between 1 s before and 1 s after its labelled window.

| Video | processed | crops from this video in | ambulance passes | detected | missed | false events | latency (s) |
|---|---|---|---|---|---|---|---|
| test1 | yes | no | 1 | 1 | 0 | 0 | 0.48 |
| test11 | yes | test | 0 | 0 | 0 | 0 |  |
| test12 | yes | no | 3 | 3 | 0 | 2 (76.64 76.8) | 2.00 0.00 0.60 |
| test2 | yes | no | 1 | 1 | 0 | 0 | 0.07 |
| test3 | yes | no | 1 | 1 | 0 | 0 | 3.37 |
| test4 | yes | no | 1 | 1 | 0 | 1 (8.08) | 0.07 |
| test5 | yes | no | 0 | 0 | 0 | 3 (0.07 9.1 10) |  |
| test6 | yes | train | 0 | 0 | 0 | 0 |  |
| test8 | yes | train | 0 | 0 | 0 | 0 |  |
| test9 | yes | val | 0 | 0 | 0 | 0 |  |
| v1 | yes | train | 0 | 0 | 0 | 0 |  |
| v2 | yes | train | 0 | 0 | 0 | 0 |  |

**Processed videos: 12 of 12.** Ambulance passes detected: 7 of 7 (100%); strict (no early confirmation): 7 of 7.
False events: 6 in 12 processed videos; 3 of them in the 7 processed videos that contain no ambulance.
Confirmation latency after the window starts: mean 0.94 s, max 3.37 s.
Note: crops from test6, test8, v1, v2 were used to train the classifier, so results on them are optimistic.
