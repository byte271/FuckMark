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

`HYPOTHESIS`. Repeating an approved carrier after existing ASCII spaces increases hidden payload without splitting `[A-Za-z]+` words, so historical hard-invariant word matching still passes. This is the TransformRegistry-compatible high-density channel. Intra-word insertion is tokenizer-diagnostic only because it breaks the frozen hard-invariant word regex.

Word-final ASCII letter x1 (`[A-Za-z](?![A-Za-z])`) plus space x1 is a detector-blind density follow-up on reserved seed `960000`. It is not every-letter insertion. Sites that would split contracted words such as `don't` are fail-closed by the frozen hard-invariant validator. This arm is not product-authorized.

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
