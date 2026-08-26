# Global seed provenance ledger

Ledger identity: `global-seed-ledger-v1` (`fuckmark/seeds/ledger.py`).

This ledger is the cross-cycle source of truth for seed reuse. A seed must be reserved here before any new generation.

## Hard rules

- Do not generate, tokenize, score, or inspect content of confirmation reserves `830000`, `840000`, `850000`.
- Seed `880000` is **PUBLICLY_EXPOSED**. Closed unmerged [PR #98](https://github.com/byte271/FuckMark/pull/98) generated and scored it as Cycle 7 Stage D validation. It is **not** eligible as unseen validation.
- Seed `890000` is Cycle 8 tiny exploratory on `main`. The same identifier was also used on unmerged PR #98 for Cycle 7 Stage D. Do not treat it as unseen.
- Do not generate `950000` until the U+034F x1 mechanism is frozen.

## Cycle 8 scale reservation (before generation)

| Seed | Role | Topic | Status |
| --- | --- | --- | --- |
| 930000 | scale exploratory | `carrier scaling` | generated and scored: 0/16, 0/32, then 1/64 U+034F x1 raw WM; do not rewrite 1/64 as zero |
| 940000 | scale replication | `independent scale replication` | reserved; not generated |
| 950000 | scale validation | `clean scale validation` | reserved; do not generate until freeze |

## Historical v1 Cycle 8 ledger

`specs/cycle8/fuckmark-cycle8-seed-ledger-v1.json` remains frozen as the PR #97 snapshot. It still says `880000` was unseen. That claim is historical and is superseded by this ledger and `cycle8-seed-ledger-v2`.
