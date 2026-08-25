# Cycle 8 carrier research

Labels: `VERIFIED`, `HYPOTHESIS`, `REJECTED`, `PRODUCT_DISQUALIFIED`, `HISTORICAL_ONLY`, `UNKNOWN`.

## H1. Normalization-stable non-Cf carrier

`HYPOTHESIS` for product use. Sanitizer screen `VERIFIED` for U+034F and U+FE00..U+FE0F on the frozen arms:

- category Mn, default-ignorable, combining class 0;
- NFC/NFKC-stable in isolation;
- survives Cf-strip (not Cf);
- survives `whitespace-collapse-v1` when placed after an ASCII space.

GPT-2 tokenizer screen `VERIFIED` on the Cycle 8 fixture (tiktoken `gpt2`): inserting U+034F after ASCII word spaces changed token IDs (`ids_equal=false`, token-count delta +40) with suffix realignment of only one token. An 8-copy space run produced delta +208. U+200C also disrupts GPT-2 (delta +28) but remains Cf-fragile.

Not product-authorized. Chromium pixel rendering on this host is `UNKNOWN` (headless timeout). Detector development on seed `890000` has not been scored yet.

## H2. Carrier runs at space boundaries

`HYPOTHESIS`. Repeating an approved carrier after existing ASCII spaces increases hidden payload without splitting `[A-Za-z]+` words, so historical hard-invariant word matching still passes. This is the TransformRegistry-compatible high-density channel. Intra-word insertion is tokenizer-diagnostic only because it breaks the frozen hard-invariant word regex.

## H3-H8

Placement geometry, Cycle 6 scheduler reuse, and root-window correlation are `HYPOTHESIS` until Cycle 8 detector development on seed `890000`.

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

U+200C after ASCII word spaces: visibility-aligned, Cf-fragile. Keep as the diagnostic control. Do not promote to release.
