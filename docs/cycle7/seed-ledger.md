# Cycle 7 seed ledger

Ledger identity: `cycle7-seed-ledger-v2` (`fuckmark/cycle7/ledger.py`).

Seeds were assigned **before** Cycle 7 detector scoring. Seed `860000` and topic `independent replication` were frozen in the ledger **before** any Stage B generation or detector look.

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
| Exploratory development / rule construction (Stage B1) | 860000 | yes, development only; frozen topic `independent replication` |
| Validation development | 820000 | only after a Stage B catalog freeze; unused at catalog-v3 construction |
| Confirmation reserved | 830000, 840000, 850000 | **no** until a later frozen confirmation protocol |

Do not promote 810000, 820000, or 860000 into confirmation after seeing scores.

Stage A generation used 810000 with pair stride 32, matching TinyDev pairing, one pair per domain, topic `reproducibility` chosen without a detector look.

Stage B1 generation uses 860000 with the same pairing rule and topic `independent replication`. Rule-construction generation must call `assert_rule_construction_seed(860000)`. Seed 810000 remains an exploratory seed for Stage A rescoring only.

Validation generation, if run, uses 820000 with topic `held-out evaluation` and `assert_development_seed(820000, role=validation_development)`. That topic was frozen before validation generation.
