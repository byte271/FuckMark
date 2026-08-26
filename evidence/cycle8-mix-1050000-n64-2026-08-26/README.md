# Cycle 8 letter-mix scale detector (seed 1050000, 64 pairs)

Measurement, not confirmation. Seed `1050000` and topic `letter mix scale replication` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on the frozen GPT-2 / SynthID protocol: identity versus U+034F letter-x1 versus U+034F/U+FE00 letter-alt v1. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Sanitizer matrix WM | Raw UW | Visible | Mean insertions | Max raw WM score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 60/64 | 60/64 | 2/64 | 128/128 | 0 | 0.69993 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 128/128 | 186.80 | 0.52746 |
| u034f-ufe00-letter-alt-v1 | **0/64** | 0/64 | 0/64 | 128/128 | 187.29 | 0.51051 |

Closest mix watermarked row geometry only: `cycle8-1050000-44-general_explanatory-watermarked`, 192 insertions, score 0.510505, gap 0.046593 below threshold 0.557099. Residual text was not inspected to write lexical rules.

Identity unwatermarked detections are 2/64 on this corpus. Mix unwatermarked detections are 0/64. Identity unwatermarked noise is control noise, not mix leakage.

Combined with independent mix seeds `1020000`, `1030000`, and `1040000`: mix **0/256** raw WM, mix UW **0/256**, worst mix max 0.519522 from `1040000` (gap 0.037577). This 0/256 is development-scale evidence on four reserved-before-generation corpora. It is not the later mix freeze confirmation result. The two-corpus 0/128 scorecard on `1020000`+`1030000` is not rewritten.

Per-domain mix raw WM is 0/16 on all four domains. Fail-closed identity count is 0. Maximum transformed GPT-2 token count on scored mix watermarked rows is 614/1024.

U+034F and U+FE00 are not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
