# Cycle 8 letter-x1 system benchmark detector (seed 980000, 64 pairs)

Measurement, not confirmation. Seed `980000` and topic `letter carrier system benchmark` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F space-x1 versus U+034F letter-x1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 62/64 | 62/64 | 0/64 | 128/128 | 0 | 0.70130 |
| u034f-space-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 44.93 | 0.55379 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 183.19 | 0.55407 |

Closest letter-x1 watermarked row: `cycle8-980000-04-general_explanatory-watermarked`, score 0.55407, gap 0.00303 below threshold 0.55710. This 0/64 has a thinner margin than independent exploratory `970000` n=64 (max 0.53039).

Do not rewrite frozen space-x1 `930000` 1/64 as zero. This corpus is a new seed; space-x1 also happened to be 0/64 here.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
