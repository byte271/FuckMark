# Cycle 8 letter-x1 independent exploratory (seed 970000, 16 pairs)

Development-only. Not confirmation. Seed `970000` and topic `intra-word carrier follow-up` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison: identity versus U+034F after ASCII letters (`u034f-letter-x1`) with visible-word invariants, quote-interior carrier policy, and a detector-blind selected-site cap of 192. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. Hard-invariant fail-closed site skipping remains. No visible-edit fallback. Public CLI remains empty.

## Result

| Arm | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | NFC WM | Raw UW | Visible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 | 1/16 | 32/32 |
| u034f-letter-x1 | **0/16** | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 32/32 |

Fail-closed identity count 0. Mean insertions 187.9375. Raw transformed WM max score 0.52455 versus threshold 0.55710.

This is an independent generation, not a rescore of `930000` / `940000` / `960000`. Those seen corpora also have letter-x1 diagnostic 0/64, 0/64, and 0/16 artifacts. The n=64 expansion of this same seed is in `evidence/cycle8-letter-970000-n64-2026-08-26/` (0/64; this n=16 artifact is a prefix).

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
