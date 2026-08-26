# Cycle 8 seed ledger

Ledger identity: `cycle8-seed-ledger-v1` (`fuckmark/cycle8/ledger.py`).

Seeds were assigned **before** any Cycle 8 text generation or detector look.

## Spent or blocked (forbidden)

| Seed | Why |
| --- | --- |
| 760000, 770000, 780000 | Cycle 6 formal confirmation. Spent. |
| 720000, 730000 | Cycle 6 development. Spent. |
| 810000, 860000, 870000 | Cycle 7 exploratory. Spent for new rule construction. |
| 820000 | Cycle 7 Stage B3 validation. Spent. |
| 880000 | Cycle 7 Stage D disjoint validation of catalog v5 (`independent check`). Do not inspect from Cycle 8. Do not retune Cycle 7 or Cycle 8 on it. |
| 830000, 840000, 850000 | Confirmation reserved. Do not inspect. |

## Cycle 8 roles

| Role | Seed | Topic | May score detectors? |
| --- | --- | --- | --- |
| Exploratory development | 890000 | invisible carrier development | yes, development only; Cycle 7 Stage D also used this seed base with a different topic (`document structure`) and disjoint texts |
| Exploratory replication | 900000 | invisible carrier replication | yes, after freeze of a mechanism from 890000 |
| Validation | 910000 | invisible carrier validation | only after a freeze; do not retune |
| Secondary exploratory | 920000 | unused unless 890000 is exhausted | yes, development only |

Do not promote 890000, 900000, 910000, or 920000 into confirmation after seeing scores.
