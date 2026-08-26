# Cycle 8 letter-x1 diagnostic rescore (seed 940000, 64 pairs)

Development-only diagnostic rescore of a **seen** independent scale corpus. Not unseen validation. Not confirmation. Seed `940000` space-carrier x1 remains **0/64** (max 0.557052 versus threshold 0.557099). This artifact reapplies detector-blind U+034F after ASCII letters to the same stored samples.

Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. No detector access during selection. No watermark secret. Public CLI remains empty.

## Result

| Arm | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | NFC WM | Raw UW | Visible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 62/64 | 62/64 | 62/64 | 62/64 | 62/64 | 2/64 | 128/128 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 128/128 |

Fail-closed identity count 0. Mean insertions 185.1953125. Raw transformed WM max score 0.52963 versus threshold 0.55710.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
