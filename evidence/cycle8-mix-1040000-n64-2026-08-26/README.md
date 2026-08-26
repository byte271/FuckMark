# Cycle 8 letter-mix scale detector (seed 1040000, 64 pairs)

Measurement, not confirmation. Seed `1040000` and topic `letter mix scale development` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F/U+FE00 letter-alt v1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| identity | 62/64 | 62/64 | 0/64 | 128/128 | 0 | 0.69764 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.23 | 0.54390 |
| u034f-ufe00-letter-alt-v1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.29 | 0.51952 |

Closest mix watermarked row geometry only: `cycle8-1040000-29-technical_explanation-watermarked`, 31 insertions, score 0.519522, gap 0.037577 below threshold 0.557099. Residual text was not inspected to write lexical rules.

Combined with independent mix seeds `1020000` and `1030000`: mix **0/192** raw WM, mix UW **0/192**, worst mix max 0.519522 (gap 0.037577). This 0/192 is development evidence on three reserved-before-generation corpora. It is not formal confirmation and does not consume `830000` / `840000` / `850000`.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
