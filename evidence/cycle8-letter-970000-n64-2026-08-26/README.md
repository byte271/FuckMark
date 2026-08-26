# Cycle 8 letter-x1 independent exploratory (seed 970000, 64 pairs)

Development-only. Not confirmation. Seed `970000` and topic `intra-word carrier follow-up` were reserved in `global-seed-ledger-v1` before generation.

Detector-blind comparison: identity versus U+034F after ASCII letters (`u034f-letter-x1`) with visible-word invariants, quote-interior carrier policy, and a detector-blind selected-site cap of 192. Threshold `0.5570987654320988`. Model `openai-community/gpt2` revision `607a30d783dfa663caf39e06633721c8d4cfcd7e`. Hard-invariant fail-closed site skipping remains. No visible-edit fallback. Public CLI remains empty.

This 64-pair corpus is an independent generation. The n=16 artifact in `evidence/cycle8-letter-970000-2026-08-26/` is a prefix of this corpus (32/32 sample text hashes match).

## Result

| Arm | Raw WM | Cf-strip WM | NFKC WM | ws-collapse WM | NFC WM | Raw UW | Visible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| identity | 64/64 | 64/64 | 64/64 | 64/64 | 64/64 | 1/64 | 128/128 |
| u034f-letter-x1 | **0/64** | 0/64 | 0/64 | 0/64 | 0/64 | 0/64 | 128/128 |

Fail-closed identity count 0. Mean insertions 184.203125. Raw transformed WM max score 0.53039 versus threshold 0.55710.

Together with diagnostic letter-x1 rescored of seen `930000` n=64 (0/64) and `940000` n=64 (0/64), this is an experimental **0/192**. Of those 192 pairs, **128 are seen-corpus diagnostic** and **64 are this independent corpus**. That is not confirmation and not a freeze. Do not rewrite frozen space-x1 `930000` 1/64 or `960000` 1/16 as zero.

U+034F is not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
