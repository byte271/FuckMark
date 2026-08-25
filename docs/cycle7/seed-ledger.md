# Cycle 7 seed ledger

Ledger identity: `cycle7-seed-ledger-v4` (`fuckmark/cycle7/ledger.py`).

Seeds were assigned **before** Cycle 7 detector scoring. Seed `860000` and topic `independent replication` were frozen in the ledger **before** any Stage B generation or detector look. Seed `870000` and topic `measurement protocol` were frozen **before** any Stage C generation or detector look. Seed `880000` and topic `independent check` were frozen as the next unused validation split **before** any Stage C validation generation. Seed `890000` and topic `document structure` were frozen **before** any Stage D generation or detector look.

## Spent (forbidden)

| Seed | Why |
| --- | --- |
| 760000, 770000, 780000 | Cycle 6 formal confirmation. Spent. |
| 720000, 730000 | Cycle 6 development 0/16. Spent. |
| 401000, 402000, 500000, 61000 | Historic TinyDev / calibration / schedule bases |
| 1120000–1160000 | Frozen effectiveness-profile schedule bases |

## Cycle 7 roles

| Role | Seed | May score detectors? |
| --- | --- | --- |
| Exploratory development (Stage A) | 810000 | yes, development only; do not keep expanding rules against it |
| Exploratory development / rule construction (Stage B1) | 860000 | used; do not keep expanding rules against it |
| Exploratory development / rule construction (Stage C1) | 870000 | used; do not keep expanding rules against it |
| Exploratory development / rule construction (Stage D1) | 890000 | yes, development only; frozen topic `document structure` |
| Validation development (Stage B3) | 820000 | used as Stage B3 disjoint validation; do not retune on it |
| Validation development (Stage C/D, reserved) | 880000 | **not yet inspected**; reserved until a catalog freeze |
| Confirmation reserved | 830000, 840000, 850000 | **no** until a later frozen confirmation protocol |

Do not promote 810000, 820000, 860000, 870000, 880000, or 890000 into confirmation after seeing scores.

Stage A generation used 810000 with pair stride 32, matching TinyDev pairing, one pair per domain, topic `reproducibility` chosen without a detector look.

Stage B1 generation used 860000 with the same pairing rule and topic `independent replication`. Seed 810000 remains an exploratory seed for Stage A rescoring only.

Validation generation used 820000 with topic `held-out evaluation`. That topic was frozen before validation generation. Do not retune catalog v3 on 820000. A later revised mechanism must not recycle 820000; Stage C reserved 880000 instead.

Stage C1 generation used 870000 with topic `measurement protocol`. That seed is now used. Do not retune catalog v4 on 870000.

Stage D1 generation uses 890000 with topic `document structure`. Rule-construction generation must call `assert_rule_construction_seed(890000)`. Seed `880000` stays unseen until a catalog freeze.

