# Cycle 8 letter-space margin detector (seed 1000000, 64 pairs)

Measurement, not confirmation. Seed `1000000` and topic `margin robustness development` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F letter-space-x1 (ASCII-letter sites plus ASCII-space sites, visible-word invariants, quote-interior policy, selected-site cap 192). Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 63/64 | 63/64 | 0/64 | 128/128 | 0 | 0.70934 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 185.58 | 0.52346 |
| u034f-letter-space-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 189.23 | 0.52477 |

Closest letter-space watermarked row geometry only: `cycle8-1000000-60-general_explanatory-watermarked`, 192 insertions, score 0.524771, gap 0.032328 below threshold 0.557099. Residual text was not inspected to write lexical rules.

On this reserved corpus letter-x1 also scored 0/64 with max 0.523457. Letter-space is not claimed to beat letter-x1 on this particular seed. The development target is a wider worst-case margin than the letter-x1 system-benchmark 980000 max 0.554066 (gap 0.003032). This fresh letter-space 0/64 meets that target. Independent replication uses reserved seed `1010000`.

Per-domain letter-space raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Maximum transformed GPT-2 token count on scored letter-space watermarked rows is 611/1024.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
