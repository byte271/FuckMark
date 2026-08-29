# Supported scope and failure matrix

This page is the public limit list for FuckMark 0.4.1. Frozen detector numbers are not regenerated here. Do not retune on spent confirmation corpora.

No-install walkthrough of these limits: [`demo.html`](demo.html).

## L01 — Sanitizers

| Arm | Live four-layer restores source? | Frozen Gate v2 mark-only mix WM |
| --- | --- | --- |
| raw | no | 0/192 |
| nfc | no | 0/192 |
| nfkc | no | 0/192 |
| cf_strip | no | 0/192 |
| nfkc_cf_strip | no | 0/192 |
| ws_collapse | no | 0/192 |
| ws_collapse_nfkc_cf_strip | no | 0/192 |
| lm-watermarking UnicodeSanitizer | no (mangles; does not reconstruct) | 0/192 |
| Mn-strip / combining-mark strip | **no** (exploratory 0/192) | 188/192 (historical restore) |
| default-ignorable strip | **no** (exploratory 0/192) | 188/192 (historical restore) |
| Mn-strip then Me-strip then UnicodeSanitizer | **no** (restore census 0/192) | historical triple-layer matches US(source) 192/192 |
| Mn then Me then UnicodeSanitizer then frozen cf_strip | **yes** (closed-set remainder) | n/a |
| required-bundle then UnicodeSanitizer | **no** (exploratory 0/192) | n/a (bundle already strips marks) |

Live mix (`u034f-ufe00-cc-me-cf-letter-alt-v1`) leaves Me/Cc/Cf residuals after Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, and the required sanitizer bundle. Frozen Cf-strip still removes the Cf layer. Frozen Gate v2 confirmation is the historical mark-only arm and is not rewritten. Exploratory rescores: `evidence/cycle8-dual-layer-stress-exploratory-2026-08-28/`, `evidence/cycle8-combo-stress-exploratory-n192-2026-08-28/` (historical triple-layer detector scores), and `evidence/cycle8-quad-layer-restore-exploratory-2026-08-29/` (four-layer restore census).

## L02 — Input domain

Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji grapheme clusters are processed. Other characters remain in the visible text and are reported as `first_unsupported`.

| Input | Behavior |
| --- | --- |
| `I do not agree.` | transformed (exit 0, reason `transformed`) |
| `I don't agree.` (U+2019) | transformed (exit 0, `first_unsupported=U+2019@5`) |
| `Hello` + U+1F600 | transformed (ASCII letters and the emoji cluster) |
| `caf` + U+00E9 | transformed (the precomposed Latin letter is a site) |
| U+00E9 only | transformed |
| U+4E2D U+6587 | transformed (Han syllables) |
| BOM / NBSP with no letter or emoji sites | unchanged (`unsupported-domain` or `no-eligible-sites`) |
| already contains an approved carrier | unchanged (`already-transformed`) |

The product does not strip a BOM, normalize accents, or transliterate to force eligibility.

## L03 — Length and the 4096-site cap

Only the first 4096 eligible letter or emoji grapheme clusters receive insertions (four per site: mark, control, Me, Cf). NFD Latin clusters are marked after the combining sequence. For a long document, report `--status` fields `sites`, `last_index`, and `capped=yes`. That is a coverage limit, not a long-document detection result.

## L04 — Detector / model / tokenizer evidence

| Family | Model | Tokenizer | n | Label |
| --- | --- | --- | --- | --- |
| Gate v2 confirmation | GPT-2 | GPT-2 BPE | 192 pairs | VERIFIED on that protocol |
| DeepMind 30-key transfer | GPT-2 | GPT-2 BPE | 192 pairs | HYPOTHESIS / configuration check |
| DistilGPT2 n=16 | DistilGPT2 | GPT-2 BPE | 16 pairs | HYPOTHESIS; not a second tokenizer family |
| DistilGPT2 combo stress | DistilGPT2 | GPT-2 BPE | 16 watermarked | HYPOTHESIS; historical triple-layer 0/16 under Mn then US |
| Four-layer restore census | n/a (no detector) | n/a | 192 watermarked | HYPOTHESIS; live four-layer 0/192 restore under Mn then Me then US |

Zero detections in a finite set is not a universal zero-rate. This evidence does not answer whether text is useful on a specific commercial platform. Not claimed: generic AI-authorship classifiers, unknown proprietary detectors, every SynthID deployment, C2PA, or a general reduction in AI detection rates.

## L05 — Downstream behavior

| Path | Status |
| --- | --- |
| Raw substring search for `do not` after mix | fails (proven) |
| `visible_contains()` | matches visible text |
| Other editors, screen readers, clipboard apps | not all measured; do not assert they all fail |

`--visible` is the reversible plain-text export. `--status` reports the outcome without inspecting invisible characters.

## L06 — Token overhead (GPT-2, stored Gate v2 watermarked geometry)

| Quantity | Stored value |
| --- | --- |
| Original tokens | 58–64, mean 63.90 |
| Transformed tokens | 139–605, mean 566.61 |
| Mean ratio | about 8.87x |
| Bytes added at 192 insertions | 480 UTF-8 bytes |

These GPT-2 ratios are not measurements for unrelated commercial tokenizers.

## P01 — Size budget

Maximum product input: 2,000,000 characters. Larger input is a documented error (exit 1), not a silent no-op. Bracket-heavy scans precompute line starts so they do not grow as repeated prefix copies.
