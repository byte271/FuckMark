# Cycle 8 letter-x1 system benchmark detector (seed 990000, 64 pairs)

Measurement, not confirmation. Seed `990000` and topic `letter carrier benchmark replication` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F space-x1 versus U+034F letter-x1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

This is an independent replication of seed `980000`, not a rescore.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 64/64 | 64/64 | 2/64 | 128/128 | 0 | 0.69680 |
| u034f-space-x1 | **1/64** | 1/64 | 0/64 | 128/128 | 47.41 | 0.57062 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 188.84 | 0.52727 |

Space-x1 residual geometry only: sample `cycle8-990000-14-conversational_prose-watermarked`, 18 insertions, score 0.57062. Residual text was not inspected to write lexical rules.

Closest letter-x1 watermarked row: `cycle8-990000-10-conversational_prose-watermarked`, score 0.52727, gap 0.02983 below threshold, 192 insertions (cap binds).

Together with seed `980000` n=64, fresh letter-x1 is **0/128** and fresh space-x1 is **1/128**. Do not rewrite frozen space-x1 `930000` 1/64 as zero.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
