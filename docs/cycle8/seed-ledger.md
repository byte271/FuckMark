# Cycle 8 seed ledger

Current ledger identity: `cycle8-seed-ledger-v2` (`fuckmark/cycle8/ledger.py`).

The PR #97 snapshot `cycle8-seed-ledger-v1` remains frozen under `specs/cycle8/fuckmark-cycle8-seed-ledger-v1.json`. Do not rewrite it.

Seeds `890000`, `900000`, `910000`, and `920000` were assigned **before** any Cycle 8 text generation or detector look. Scale seeds `930000`, `940000`, and `950000` and their topics were reserved in `global-seed-ledger-v1` **before** any scale generation. Density seed `960000` and topic `carrier density follow-up` were reserved in `global-seed-ledger-v1` **before** density generation. Letter seed `970000` and topic `intra-word carrier follow-up` were reserved in `global-seed-ledger-v1` **before** letter generation. Benchmark seeds `980000` and `990000` and topics `letter carrier system benchmark` and `letter carrier benchmark replication` were reserved in `global-seed-ledger-v1` **before** benchmark generation. Margin seeds `1000000` and `1010000` were reserved before letter-space generation. Mix seeds `1020000` and `1030000` were reserved before letter-mix generation. Mix scale seeds `1040000` and `1050000` were reserved before mix scale generation.

See also `docs/seeds.md`.

## Spent or blocked (forbidden)

| Seed | Why |
| --- | --- |
| 760000, 770000, 780000 | Cycle 6 formal confirmation. Spent. |
| 720000, 730000 | Cycle 6 development. Spent. |
| 810000, 860000, 870000 | Cycle 7 exploratory. Spent for new rule construction. |
| 820000 | Cycle 7 Stage B3 validation. Spent. |
| 880000 | Cycle 7 Stage C reserved validation. **PUBLICLY_EXPOSED** by closed unmerged PR #98. Not eligible as unseen validation. |
| 830000, 840000, 850000 | Cycle 8 mix freeze confirmation. Generated once. Spent. Mix 0/192. Do not retune. Do not rerun looking for zero. |
| 890000, 900000, 910000 | Cycle 8 tiny n=4 already generated and scored. Spent as unseen validation. |

## Cycle 8 roles

| Role | Seed | Topic | May score detectors? |
| --- | --- | --- | --- |
| Tiny exploratory (spent) | 890000 | invisible carrier development | existing tiny evidence only |
| Tiny replication (spent) | 900000 | invisible carrier replication | existing tiny evidence only |
| Tiny validation (spent) | 910000 | invisible carrier validation | existing tiny evidence only |
| Secondary exploratory | 920000 | invisible carrier development | unused; development only |
| Scale exploratory | 930000 | carrier scaling | yes, development only, after reservation |
| Scale replication | 940000 | independent scale replication | yes, after 930000, development only |
| Scale validation | 950000 | clean scale validation | only after a U+034F x1 freeze; do not generate yet |
| Density exploratory | 960000 | carrier density follow-up | scored n=16; both arms 1/16; density did not beat space x1; letter-x1 diagnostic rescore 0/16; do not retune on residual text |
| Letter exploratory | 970000 | intra-word carrier follow-up | reserved before generation; independent letter-x1 n=16 is 0/16 then n=64 is 0/64; experimental 0/192 is 128 seen plus 64 independent; not confirmation |
| Letter benchmark primary | 980000 | letter carrier system benchmark | reserved before generation; n=64 letter-x1 0/64, space-x1 0/64; not confirmation |
| Letter benchmark replication | 990000 | letter carrier benchmark replication | reserved before generation; n=64 letter-x1 0/64, space-x1 1/64; combined letter 0/128; not confirmation |
| Margin primary | 1000000 | margin robustness development | reserved before generation; letter-space n=64 0/64; not confirmation |
| Margin replication | 1010000 | margin robustness replication | reserved before generation; letter-space n=64 1/64; combined letter-space 1/128; do not rewrite as zero |
| Mix primary | 1020000 | letter mix margin development | reserved before generation; letter-alt n=64 0/64, max 0.513691; not confirmation |
| Mix replication | 1030000 | letter mix margin replication | reserved before generation; letter-alt n=64 0/64, max 0.513071; combined mix 0/128 gap 0.043407; not confirmation |
| Mix scale primary | 1040000 | letter mix scale development | reserved before generation; letter-alt n=64 0/64, max 0.519522; not confirmation |
| Mix scale replication | 1050000 | letter mix scale replication | reserved before generation; letter-alt n=64 0/64, max 0.510505; combined mix 0/256; not confirmation |
| Mix freeze confirmation primary | 830000 | mix formal confirmation primary | generated once under cycle8-mix-freeze-v1; mix 0/64; combined 0/192; spent |
| Mix freeze confirmation replication | 840000 | mix formal confirmation replication | generated once; mix 0/64, max 0.524300; combined 0/192; spent |
| Mix freeze confirmation holdout | 850000 | mix formal confirmation holdout | generated once; mix 0/64; combined 0/192; spent |

Do not promote any of these seeds into confirmation after seeing scores.
