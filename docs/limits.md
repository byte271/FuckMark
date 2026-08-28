# Supported scope and failure matrix

This page is the public limit list for FuckMark 0.4.1. Frozen detector numbers are not regenerated here. Do not retune on spent confirmation corpora.

No-install walkthrough of these limits: [`demo.html`](demo.html).

## L01 — Sanitizers

| Arm | Restores source? | Gate v2 mix WM (frozen) |
| --- | --- | --- |
| raw | no | 0/192 |
| nfc | no | 0/192 |
| nfkc | no | 0/192 |
| cf_strip | no | 0/192 |
| nfkc_cf_strip | no | 0/192 |
| ws_collapse | no | 0/192 |
| ws_collapse_nfkc_cf_strip | no | 0/192 |
| lm-watermarking UnicodeSanitizer | no (mangles; does not reconstruct) | 0/192 |
| Mn-strip / combining-mark strip | **yes** | 188/192 (diagnostic restore) |
| default-ignorable strip | **yes** | 188/192 (diagnostic restore) |

If `R(T(x)) = x` and a detector sees `R(T(x))`, it sees the original watermarked source. The insertion-only mechanism cannot claim immunity to that removal. Demonstrations must show both the successful required-sanitizer paths and this source-restoring failure path.

## L02 — Input domain

Supported code points: U+0009, U+000A, U+000D, U+0020..U+007E.

| Input | Behavior |
| --- | --- |
| `I do not agree.` | transformed (exit 0, reason `transformed`) |
| `I don't agree.` (U+2019) | unchanged (exit 0, reason `unsupported-domain`) |
| `Hello 😀` | unchanged |
| `café` | unchanged |
| BOM, NBSP, CJK | unchanged |
| already contains U+034F or U+FE00 | unchanged (`already-transformed`) |

The product does not strip a BOM, normalize accents, or transliterate to force eligibility.

## L03 — Length and the 192-site cap

Only the first 192 eligible ASCII-letter sites receive insertions. For a long document, report `--status` fields `sites`, `last_index`, and `capped=yes`. A 9,000-character paragraph sequence can stop near source index 245, leaving thousands of trailing characters unchanged. That is a coverage limit, not a long-document detection result.

## L04 — Detector / model / tokenizer evidence

| Family | Model | Tokenizer | n | Label |
| --- | --- | --- | --- | --- |
| Gate v2 confirmation | GPT-2 | GPT-2 BPE | 192 pairs | VERIFIED on that protocol |
| DeepMind 30-key transfer | GPT-2 | GPT-2 BPE | 192 pairs | HYPOTHESIS / configuration check |
| DistilGPT2 n=16 | DistilGPT2 | GPT-2 BPE | 16 pairs | HYPOTHESIS; not a second tokenizer family |

Zero detections in a finite set is not a universal zero-rate. Not claimed: generic AI-authorship classifiers, unknown proprietary detectors, every SynthID deployment, C2PA.

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
