# Cycle 8 scale exploratory detector evidence (seed 930000, 16 pairs)

Development-only. Not confirmation. Seed `930000` and topic `carrier scaling` were reserved in `global-seed-ledger-v1` before generation.

Frozen mechanism: U+034F space-carrier x1. Detector-blind placement. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

## Result

| Arm | Pristine WM | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | Combined WM | NFC WM | Raw UW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 0/16 |
| u034f-space-x1 | 16/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 |

Visible projection: 32/32 PASS on the U+034F x1 arm (16 watermarked + 16 matched unwatermarked). Artifact `visible_pass_rate` `64/64` counts identity and U+034F arms together.

U+034F x1 mean insertions 47.0; mean UTF-8 overhead 94 bytes. Raw transformed WM max score 0.535 < threshold.

This is `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. It is not 0/192 and is not a product authorization.

Do not inspect `830000`, `840000`, or `850000`. Do not generate `950000` yet. U+034F is not product-authorized.
