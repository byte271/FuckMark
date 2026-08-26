# Global seed provenance ledger

Ledger identity: `global-seed-ledger-v1` (`fuckmark/seeds/ledger.py`).

This ledger is the cross-cycle source of truth for seed reuse. A seed must be reserved here before any new generation.

## Hard rules

- Do not generate, tokenize, score, or inspect content of confirmation reserves `830000`, `840000`, `850000`.
- Seed `880000` is **PUBLICLY_EXPOSED**. Closed unmerged [PR #98](https://github.com/byte271/FuckMark/pull/98) generated and scored it as Cycle 7 Stage D validation. It is **not** eligible as unseen validation.
- Seed `890000` is Cycle 8 tiny exploratory on `main`. The same identifier was also used on unmerged PR #98 for Cycle 7 Stage D. Do not treat it as unseen.
- Do not generate `950000` until the U+034F x1 mechanism is frozen.
- Seed `960000` is reserved for detector-blind U+034F space plus word-final letter density follow-up. Do not inspect `930000` residual text to write lexical rules.
- Seed `970000` is reserved for detector-blind intra-word letter-carrier follow-up. It was reserved in `global-seed-ledger-v1` before generation.
- Seeds `980000` and `990000` are reserved for the letter-x1 system benchmark. They were reserved in `global-seed-ledger-v1` before generation.
- Seeds `1000000` and `1010000` are reserved for letter-space margin follow-up. Combined letter-space is 1/128.
- Seeds `1020000` and `1030000` are reserved for U+034F/U+FE00 letter-mix margin follow-up. Combined mix is 0/128.
- Seeds `1040000` and `1050000` are reserved for letter-mix scale follow-up. Combined with `1020000`+`1030000`, mix is 0/256. That 0/256 is development scale, not confirmation.

## Cycle 8 scale reservation (before generation)

| Seed | Role | Topic | Status |
| --- | --- | --- | --- |
| 930000 | scale exploratory | `carrier scaling` | generated and scored: 0/16, 0/32, then 1/64 U+034F space x1 raw WM; letter-x1 diagnostic rescore of this seen corpus is 0/64; do not rewrite space 1/64 as zero |
| 940000 | scale replication | `independent scale replication` | generated and scored: independent 0/64 U+034F space x1 raw WM; max score 0.557052 vs threshold 0.557099; letter-x1 diagnostic rescore of this seen corpus is 0/64 |
| 950000 | scale validation | `clean scale validation` | reserved; do not generate until freeze |
| 960000 | density exploratory | `carrier density follow-up` | generated and scored n=16: space-x1 1/16 and space-wordfinal 1/16 on the same residual row; density did not beat space x1; letter-x1 diagnostic rescore of this seen corpus is 0/16; do not rewrite space 1/16 as zero |
| 970000 | letter exploratory | `intra-word carrier follow-up` | reserved before generation; independent letter-x1 n=16 is 0/16 then n=64 is 0/64; experimental 0/192 is 128 seen plus 64 independent; not confirmation |
| 980000 | letter benchmark primary | `letter carrier system benchmark` | reserved before generation; system-benchmark n=64: letter-x1 0/64, space-x1 0/64, identity 62/64; letter max 0.554066; not confirmation |
| 990000 | letter benchmark replication | `letter carrier benchmark replication` | reserved before generation; independent system-benchmark n=64: letter-x1 0/64, space-x1 1/64, identity 64/64; combined with 980000 letter 0/128 and space 1/128; not confirmation |
| 1000000 | margin primary | `margin robustness development` | reserved before generation; letter-space n=64 0/64; not confirmation |
| 1010000 | margin replication | `margin robustness replication` | reserved before generation; letter-space n=64 1/64; combined letter-space 1/128; do not rewrite as zero |
| 1020000 | mix primary | `letter mix margin development` | reserved before generation; letter-alt n=64 0/64, max 0.513691, gap 0.043407; not confirmation |
| 1030000 | mix replication | `letter mix margin replication` | reserved before generation; letter-alt n=64 0/64, max 0.513071; combined mix 0/128; not confirmation |
| 1040000 | mix scale primary | `letter mix scale development` | reserved before generation; letter-alt n=64 0/64, max 0.519522, gap 0.037577; not confirmation |
| 1050000 | mix scale replication | `letter mix scale replication` | reserved before generation; letter-alt n=64 0/64, max 0.510505; combined mix 0/256; not confirmation |

## Historical v1 Cycle 8 ledger

`specs/cycle8/fuckmark-cycle8-seed-ledger-v1.json` remains frozen as the PR #97 snapshot. It still says `880000` was unseen. That claim is historical and is superseded by this ledger and `cycle8-seed-ledger-v2`.
