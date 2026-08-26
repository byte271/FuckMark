# Cycle 8 letter-mix margin detector (seed 1030000, 64 pairs)

Measurement, not confirmation. Seed `1030000` and topic `letter mix margin replication` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F/U+FE00 letter-alt v1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 64/64 | 64/64 | 1/64 | 128/128 | 0 | 0.71292 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.66 | 0.52725 |
| u034f-ufe00-letter-alt-v1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.84 | 0.51307 |

Do not rewrite identity unwatermarked 1/64 as mix leakage. Mix unwatermarked detections are 0/64.

Closest mix watermarked row geometry only: `cycle8-1030000-48-general_explanatory-watermarked`, 144 insertions, score 0.513071, gap 0.044027 below threshold 0.557099. Residual text was not inspected to write lexical rules.

Combined with independent primary seed `1020000`: mix **0/128** raw WM, mix UW **0/128**, worst mix max 0.513691 (gap 0.043407). Letter-x1 on the same mix corpora is also 0/128 with worst max 0.527389. This is not confirmation and is not a freeze.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Maximum transformed GPT-2 token count on scored mix watermarked rows is 603/1024.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
