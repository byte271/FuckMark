# Cycle 8 scale independent replication (seed 940000, 64 pairs)

Development-only. Not confirmation. Seed `940000` and topic `independent scale replication` were reserved in `global-seed-ledger-v1` before generation. Frozen mechanism: the same U+034F space-carrier x1 used on seed `930000`, including hard-invariant fail-closed site skipping. Detector-blind placement. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

## Result

| Arm | Pristine WM | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | Combined WM | NFC WM | Raw UW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 62/64 | 62/64 | 62/64 | 62/64 | 62/64 | 62/64 | 62/64 | 2/64 |
| u034f-space-x1 | 62/64 | **0/64** | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 |

Visible projection: 128/128 PASS on the U+034F x1 arm. Artifact `visible_pass_rate` `256/256` counts identity and U+034F arms together.

U+034F x1 mean insertions 47.65625; mean UTF-8 overhead 95.3125 bytes. Fail-closed identity count 0. Hard-invariant blocked sites 0.

Raw transformed WM mean score 0.51113, median 0.51139, max 0.557052. The maximum is 0.000047 below the frozen threshold. That 0/64 is legitimate under the frozen comparison rule and must not be dressed up as a wide margin.

This independently designated 0/64 does not erase seed `930000` n=64 **1/64**. Combined large-N U+034F x1 on these two 64-pair corpora is **1/128** transformed WM, matched transformed UW **0/128**, visible projection **256/256** on the U+034F arms.

This is `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. It is not 0/192, not product authorization, and not a reason to generate `950000` or to inspect `830000` / `840000` / `850000`.
