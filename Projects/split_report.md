# Crops dataset: split manifest and leakage check

Folder `crops`; 32593 images. Full list with SHA-1 and dHash: `crops_manifest.csv`.

| Split | ambulance | other_vehicle | total | ambulance share |
|---|---|---|---|---|
| train | 4506 | 21182 | 25688 | 17.5% |
| val | 429 | 2755 | 3184 | 13.5% |
| test | 768 | 2953 | 3721 | 20.6% |

| Split | class | source | images |
|---|---|---|---|
| test | ambulance | pk | 235 |
| test | ambulance | pub | 533 |
| test | other_vehicle | local | 89 |
| test | other_vehicle | pub | 2864 |
| train | ambulance | local | 157 |
| train | ambulance | pub | 4081 |
| train | ambulance | web | 268 |
| train | other_vehicle | local | 6402 |
| train | other_vehicle | pub | 14780 |
| val | ambulance | pub | 429 |
| val | other_vehicle | local | 153 |
| val | other_vehicle | pub | 2602 |

## Leakage

- Exact duplicate files shared between splits: **19**
- Identical files with different labels: **1**
- Near duplicates of a train image (dHash distance <= 4, mirror included, exact ones included): **140** in val, **134** in test (3.6% of test)

Details: `split_duplicates.csv`. Near duplicates are candidates: open a few pairs to confirm they are the same vehicle and frame before removing them from val/test.
