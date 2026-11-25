# Tracking pipeline on the Islamabad videos

Ground truth: `ground_truth.csv`. A pass is detected if a confirmation falls between 1 s before and 1 s after its labelled window.

| Video | processed | crops from this video in | ambulance passes | detected | missed | false events | latency (s) |
|---|---|---|---|---|---|---|---|
| test1 | yes | no | 1 | 1 | 0 | 0 | 0.20 |
| test11 | yes | test | 0 | 0 | 0 | 0 |  |
| test12 | yes | no | 3 | 2 | 1 | 0 | 0.00 0.68 |
| test2 | yes | no | 1 | 1 | 0 | 0 | 0.13 |
| test3 | yes | no | 1 | 1 | 0 | 0 | 0.43 |
| test4 | yes | no | 1 | 1 | 0 | 1 (12.16) | 0.13 |
| test5 | yes | no | 0 | 0 | 0 | 9 (0.83 3.03 4.9 6.67 8.8 9.37 10 10.8 11.47) |  |
| test6 | yes | train | 0 | 0 | 0 | 0 |  |
| test7 | **no** | train | 0 |  |  |  |  |
| test8 | yes | train | 0 | 0 | 0 | 0 |  |
| test9 | yes | val | 0 | 0 | 0 | 1 (1.16) |  |
| v1 | yes | train | 0 | 0 | 0 | 2 (1.18 2.36) |  |
| v2 | yes | train | 0 | 0 | 0 | 0 |  |

**Processed videos: 12 of 13.** Ambulance passes detected: 6 of 7 (86%); strict (no early confirmation): 5 of 7.
False events: 13 in 12 processed videos; 12 of them in the 7 processed videos that contain no ambulance.
Confirmation latency after the window starts: mean 0.26 s, max 0.68 s.
Not processed yet (run `python track_pipeline.py test7`): test7.
Note: crops from test6, test8, v1, v2 were used to train the classifier, so results on them are optimistic.
