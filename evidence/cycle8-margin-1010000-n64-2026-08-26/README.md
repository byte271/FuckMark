# Cycle 8 letter-space margin detector (seed 1010000, 64 pairs)

Measurement, not confirmation. Seed `1010000` and topic `margin robustness replication` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F letter-space-x1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 64/64 | 64/64 | 1/64 | 128/128 | 0 | 0.69482 |
| u034f-letter-x1 | **1/64** | 1/64 | 0/64 | 128/128 | 187.34 | 0.58124 |
| u034f-letter-space-x1 | **1/64** | 1/64 | 0/64 | 128/128 | 189.91 | 0.58085 |

Do not rewrite 1/64 as zero.

Residual geometry only: `cycle8-1010000-56-general_explanatory-watermarked`. Letter-x1: 30 insertions, score 0.581239. Letter-space: 37 insertions, score 0.580847. Identity score 0.683502. Residual text was not inspected to write lexical rules.

Combined with independent primary seed `1000000`: letter-space **1/128** and letter-x1 **1/128** on the same reserved-before-generation pair. The residual is a short low-site row. This is not confirmation and is not a freeze.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
