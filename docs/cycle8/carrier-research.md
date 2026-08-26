# Cycle 8 carrier research

Labels: `VERIFIED`, `HYPOTHESIS`, `REJECTED`, `PRODUCT_DISQUALIFIED`, `HISTORICAL_ONLY`, `UNKNOWN`.

## H1. Normalization-stable non-Cf carrier

`HYPOTHESIS` for product use. Sanitizer screen `VERIFIED` for U+034F and U+FE00..U+FE0F on the frozen arms:

- category Mn, default-ignorable, combining class 0;
- NFC/NFKC-stable in isolation;
- survives Cf-strip (not Cf);
- survives `whitespace-collapse-v1` when placed after an ASCII space.

GPT-2 tokenizer screen `VERIFIED` on the Cycle 8 fixture (tiktoken `gpt2`): inserting U+034F after ASCII word spaces changed token IDs (`ids_equal=false`, token-count delta +40) with suffix realignment of only one token. An 8-copy space run produced delta +208. U+200C also disrupts GPT-2 (delta +28) but remains Cf-fragile.

Not product-authorized. Fixture compare on four ASCII texts is `VERIFIED` for visible projection (`20/20`) and for U+034F / U+FE00 survival under Cf-strip, NFKC, and `whitespace-collapse-v1`. Chromium `pre` screenshots: U+034F and U+FE00 are `VERIFIED` pixel-equal to the original; U+200C is `REJECTED` (PNG bytes differ). Detector-blind GPT-2 / SynthID looks on seeds `890000`, `900000`, and `910000` are `PROMISING_DEVELOPMENT` / `HYPOTHESIS` only (four watermarked pairs per seed). Prefer U+034F x1: x8 overflowed GPT-2's 1024-token context on seed `900000`. The public CLI still authorizes zero carriers.

## H2. Carrier runs at space boundaries

`HYPOTHESIS` for the space-x1 product-research arm. Repeating an approved carrier after existing ASCII spaces increases hidden payload without splitting `[A-Za-z]+` words, so historical hard-invariant word matching still passes. Word-final ASCII letter x1 (`[A-Za-z](?![A-Za-z])`) plus space x1 was a detector-blind density follow-up on reserved seed `960000`. On that 16-pair corpus both space x1 and space-wordfinal were **1/16** raw transformed WM on the same residual row. Density did not beat space x1. Space-x1 scale remains **1/64** on seed `930000` and **0/64** on seed `940000` (combined **1/128**). These space-x1 results are frozen. Do not rewrite them as zero.

## H10. Intra-word visible-preserving letter carrier

`HYPOTHESIS` / `PROMISING_DEVELOPMENT`. The frozen hard-invariant word regex is a raw-byte check. User-visible words are the Priority Zero object, so the letter arm computes negation/modality signatures on `project_visible_v1` and opt-in quote-interior policy `quote-visible-carrier-v1` allows approved letter carriers inside surface-editable quotations without changing quote delimiters. Machine spans (URLs, paths, code, numbers) stay blocked on raw protected-span identity. A detector-blind selected-site cap of 192 keeps GPT-2 context under 1024 tokens.

Letter-x1 is **not** in `release_transform_registry()`. Space-x1 still uses blanket quotes and raw word signatures.

Diagnostic rescore of seen corpora (not unseen): `960000` n=16 **0/16**, `930000` n=64 **0/64**, `940000` n=64 **0/64**. Independent reserved seed `970000` is **0/16** then **0/64**. Experimental letter-x1 **0/192** = seen `930000` n=64 plus seen `940000` n=64 plus independent `970000` n=64 (**128/192 seen**, **64/192 independent**). Matched unwatermarked controls stayed clean. Visible projection passed on every scored letter row.

A later system benchmark reserved seeds `980000` and `990000` before generation. Fresh letter-x1 is **0/128** raw transformed WM on those two independent 64-pair corpora, with space-x1 **1/128** on the same texts. Maximum fresh letter score is 0.554066 versus threshold 0.557099. That 0/128 is measurement, not confirmation, and must not be collapsed into the experimental 0/192. Formal confirmation readiness is `NOT_READY`. See `docs/cycle8/letter-system-benchmark.md`.

Still `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. Not confirmation. Not a freeze. Public CLI remains empty. Do not generate `950000`.

Intra-word insertion is no longer treated as tokenizer-diagnostic-only. It is the current strongest visible-invariant U+034F arm.

## H3-H8

Placement geometry, Cycle 6 scheduler reuse, and root-window correlation remain `HYPOTHESIS` for larger corpora. Tiny-corpus detector looks on seeds `890000`, `900000`, and `910000` are `PROMISING_DEVELOPMENT` only.

## H9. Feasibility boundary

Still `HYPOTHESIS`. If every tokenizer-disruptive invisible carrier is removed by ordinary sanitizers, Cycle 8 will freeze that boundary rather than weaken Priority Zero.

## Rejected as product mechanisms

| Mechanism | Label | Why |
| --- | --- | --- |
| Contractions / Cycle 7 durable edits | `PRODUCT_DISQUALIFIED` | visible words or punctuation change |
| Cycle 6 U+0020 runs | `PRODUCT_DISQUALIFIED` | visible spacing change |
| U+200C / other Cf | `REJECTED` as durable; diagnostic only | Cf-strip restores the original string |
| NBSP / hair spaces / dashes / homoglyphs | `REJECTED` | visible or NFKC-mapped layout/glyph change |

## Baseline

U+200C after ASCII word spaces: visibility-aligned on the v1 projection, Cf-fragile, and Chromium-pixel-`REJECTED`. Keep as the diagnostic control. Do not promote to release.
