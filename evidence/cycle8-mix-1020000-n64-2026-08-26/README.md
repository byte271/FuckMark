# Cycle 8 letter-mix margin detector (seed 1020000, 64 pairs)

Measurement, not confirmation. Seed `1020000` and topic `letter mix margin development` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F/U+FE00 letter-alt v1 (ASCII-letter sites outside raw unmerged hard machine spans, even site index U+034F, odd site index U+FE00, selected-site cap 192). Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 64/64 | 64/64 | 0/64 | 128/128 | 0 | 0.68902 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 187.60 | 0.52739 |
| u034f-ufe00-letter-alt-v1 | **0/64** | 0/64 | 0/64 | 128/128 | 187.67 | 0.51369 |

Closest mix watermarked row geometry only: `cycle8-1020000-29-technical_explanation-watermarked`, 192 insertions, score 0.513691, gap 0.043407 below threshold 0.557099. Residual text was not inspected to write lexical rules.

On this reserved corpus letter-x1 also scored 0/64 with max 0.527389 (gap 0.029709). Mix is stronger on the worst-case score. The development target is a wider worst-case margin than the letter-x1 system-benchmark 980000 max 0.554066 (gap 0.003032). This fresh mix 0/64 meets that target. Independent reserved seed `1030000` later replicated 0/64 with mix max 0.513071. Combined fresh mix is 0/128.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Maximum transformed GPT-2 token count on scored mix watermarked rows is 604/1024.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
