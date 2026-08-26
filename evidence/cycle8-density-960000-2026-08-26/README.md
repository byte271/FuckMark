# Cycle 8 density exploratory detector evidence (seed 960000, 16 pairs)

Development-only. Not confirmation. Seed `960000` and topic `carrier density follow-up` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison on one new corpus: identity, U+034F space-carrier x1, and U+034F space plus word-final ASCII letter x1. Not every-letter insertion. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. Hard-invariant fail-closed site skipping is unchanged. No visible-edit fallback.

## Result

| Arm | Pristine WM | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | Combined WM | NFC WM | Raw UW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 0/16 |
| u034f-space-x1 | 16/16 | **1/16** | 1/16 | 1/16 | 1/16 | 1/16 | 1/16 | 0/16 |
| u034f-space-wordfinal-x1 | 16/16 | **1/16** | 1/16 | 1/16 | 1/16 | 1/16 | 1/16 | 0/16 |

Visible projection: 32/32 PASS on each transformed arm. Artifact `visible_pass_rate` `96/96` counts identity plus both transformed arms.

Do not rewrite 1/16 as zero.

## Density versus space x1

Space x1 mean insertions 45.84375; mean UTF-8 overhead 91.6875 bytes; raw transformed WM mean 0.51974, max 0.60522.

Space plus word-final mean insertions 92.6875; mean UTF-8 overhead 185.375 bytes; raw transformed WM mean 0.51850, max 0.61553.

Word-final density is about 2x space x1 on this corpus. GPT-2 transformed token counts stayed under 1024 on every row (space max 246, word-final max 363). Fail-closed identity count 0. Word-final hard-invariant blocked-site mean 0.65625 versus 0.09375 for space x1, from contracted-word splits that the frozen validator already rejects.

Both transformed arms left the same watermarked row detected: `cycle8-960000-12-general_explanatory-watermarked`. Residual geometry only: space x1 had 4 insertions and GPT-2 token-count delta 12; word-final had 7 insertions and delta 18. Residual raw scores 0.60522 (space) and 0.61553 (word-final) versus threshold 0.55710. Word-final did not clear the residual and did not lower its score.

This residual was not used to write per-row lexical rules. Density is not justified as a better mechanism than space x1 on this seed. Do not expand 960000 to 32 or 64 on this result.

The harness classifier still labels the word-final arm `PROMISING_DEVELOPMENT` because 1/16 is below identity 16/16 with no unwatermarked inflation. That label does not make density a freeze candidate.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
