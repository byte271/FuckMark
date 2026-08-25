# Cycle 7 seed ledger

Ledger identity: `cycle7-seed-ledger-v1` (`fuckmark/cycle7/ledger.py`).

Seeds were assigned **before** Cycle 7 detector scoring.

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
| Exploratory development (Stage A) | 810000 | yes, development only |
| Validation development (Stage B) | 820000 | only after Stage A family freeze; not in this PR's detector run |
| Confirmation reserved | 830000, 840000, 850000 | **no** until a later frozen confirmation protocol |

Do not promote 810000 or 820000 into confirmation after seeing scores.

Stage A generation uses 810000 with pair stride 32, matching TinyDev pairing, one pair per domain, topic `reproducibility` chosen without a detector look.
