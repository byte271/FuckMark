# Cycle 8 letter-x1 diagnostic rescore (seed 960000, 16 pairs)

Development-only diagnostic rescore of a **seen** density corpus. Not unseen validation. Not confirmation. Seed `960000` was generated for space versus word-final density. This artifact reapplies detector-blind U+034F after ASCII letters (`u034f-letter-x1`) to the same stored samples.

Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

Space x1 and space-wordfinal on this corpus remain **1/16**. Do not rewrite those frozen density results as zero.

## Result

| Arm | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | NFC WM | Raw UW | Visible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 0/16 | 32/32 |
| u034f-letter-x1 | **0/16** | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 32/32 |

Fail-closed identity count 0. Mean insertions 190.125. Raw transformed WM max score 0.51699 versus threshold 0.55710.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
