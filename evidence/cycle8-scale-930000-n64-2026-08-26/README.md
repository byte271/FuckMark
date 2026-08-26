# Cycle 8 scale exploratory detector evidence (seed 930000, 64 pairs)

Development-only. Not confirmation. Seed `930000` and topic `carrier scaling` were reserved in `global-seed-ledger-v1` before generation. Pair indices 0-63. Frozen mechanism: U+034F space-carrier x1 with hard-invariant fail-closed site skipping. Detector-blind placement. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`.

## Result

| Arm | Pristine WM | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | Combined WM | NFC WM | Raw UW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 63/64 | 63/64 | 63/64 | 63/64 | 63/64 | 63/64 | 63/64 | 2/64 |
| u034f-space-x1 | 63/64 | **1/64** | 1/64 | 1/64 | 1/64 | 1/64 | 1/64 | 0/64 |

Visible projection: 128/128 PASS on the U+034F x1 arm (64 watermarked + 64 matched unwatermarked). Artifact `visible_pass_rate` `256/256` counts identity and U+034F arms together.

U+034F x1 mean insertions 47.0703125; mean UTF-8 overhead 94.140625 bytes. Raw transformed WM mean score 0.51196, median 0.50947, max 0.55894.

This is a **NONZERO residual**: 1/64 transformed watermarked detections. Do not rewrite it as zero. The residual row kept 22 insertions (below the corpus mean of 47) and a GPT-2 token-count delta of 70 (corpus min; mean 149). Its raw score 0.55894 is 0.00184 above the frozen threshold. Fail-closed identity count is 0. One other watermarked row skipped 2 hard-invariant sites and still inserted 43 carriers; that row is not the residual.

Identity unwatermarked detections are 2/64 on this corpus. Transformed unwatermarked detections are 0/64.

This is `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. It is not 0/192 and is not a product authorization. Do not inspect this residual to write per-row lexical rules. Do not retune the frozen U+034F x1 placement on this row. Independent replication uses reserved seed `940000`.

Do not inspect `830000`, `840000`, or `850000`. Do not generate `950000` yet. U+034F is not product-authorized.
