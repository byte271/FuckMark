# Cycle 7 literature notes

Claim labels used below: VERIFIED, SOURCE-BOUND, HYPOTHESIS, UNKNOWN, REJECTED, EXTERNAL-VALIDATION-ONLY.

## SynthID-Text

SOURCE-BOUND. Google documents SynthID-Text as a logits-processor watermark using a keyed g-function and tournament sampling. Detectability uses n-gram context. Larger `ngram_len` is more detectable and more brittle to edits. Public docs state robustness to cropping, a few word changes, and mild paraphrasing, with large detector-confidence loss under thorough rewrite or translation.

- https://ai.google.dev/responsible/docs/safeguards/synthid
- https://huggingface.co/blog/synthid-text
- Dathathri et al., *Scalable watermarking for identifying large language model outputs*, Nature (2024): https://www.nature.com/articles/s41586-024-08025-4

This repository's Cycle 6 result is the local VERIFIED measurement for the frozen GPT-2 / mean-score protocol: 183/192 pristine detections reduced to 7/192 transformed detections, 0/192 transformed unwatermarked, `NONZERO_RESIDUAL`. That is not a claim about proprietary production detectors.

## Edit-channel / synchronization

SOURCE-BOUND / HYPOTHESIS. Context-hashed watermarks re-synchronize after a local edit once the sliding n-gram window has moved past the edit. Cycle 6 spacing inserts extra U+0020 tokens that change GPT-2 segmentation, then ordinary space-collapse removes those tokens and restores the original token sequence. That collapse failure is VERIFIED here as a mechanism class on fresh seed `810000`, not as a universal watermark theorem.

EXTERNAL-VALIDATION-ONLY. Zhao-style or layer-inflation analyses of SynthID, and synonym/paraphrase/back-translation robustness papers (including arXiv:2508.20228 and arXiv:2603.03410), are not reproduced in this repository and must not be cited as FuckMark results. Neural paraphrasing is out of protocol for the attack itself.

## Deterministic non-neural edits

VERIFIED tokenizer effects on frozen GPT-2 `607a30d783dfa663caf39e06633721c8d4cfcd7e`:

- `proof of concept` → 3 tokens; `proof-of-concept` → 5 tokens.
- ASCII `It's not uncommon` → `[1026, 338, 407, 19185]`; U+2019 apostrophe form → `[1026, 447, 247, 82, 407, 19185]`.

VERIFIED sanitizer fate:

- U+2019 survives NFKC and is not Cf, so it survives `ws_collapse_nfkc_cf_strip`.
- NBSP U+00A0 NFKC-maps to U+0020. REJECTED as a collapse-resistant channel.
- U+200B / U+00AD are Cf. REJECTED against the frozen Cf-strip arm.

HYPOTHESIS. Unambiguous contractions, attested hyphenation, and typographic apostrophes can destroy some observation windows. Whether they destroy enough windows on 64-token TinyDev GPT-2 text is a Cycle 7 measurement. Family 1 detector attachment on seed `810000` was INSUFFICIENT_EVIDENCE because natural site density was too low.

EXTERNAL-VALIDATION-ONLY. Optional complementizer *that* is a high-frequency English reduction (Jaeger, *Cognitive Psychology* 2010, UID/information-density accounts). Cycle 7 admits only a closed pronoun+verb list plus object-relative `DET+N that PRON`. That literature is not a local density measurement.

EXTERNAL-VALIDATION-ONLY. CMOS hyphenates compound modifiers before a noun (`well-known method`) and leaves predicative forms open. Family 7 encodes that bound, not a generic hyphenation whitelist.

VERIFIED tokenizer effects added in catalog v3 on the same frozen GPT-2 revision:

- `Hello. World` → `[15496, 13, 2159]`; `Hello.\nWorld` → `[15496, 13, 198, 10603]`.
- `I think that the protocol works` versus `I think the protocol works` differs by the `that` piece.
- `failed and the replica` versus `failed, and the replica` differs by the comma piece.

HYPOTHESIS. Sentence-boundary newline survives `whitespace-collapse-v1` because that sanitizer preserves LF. A wrap/reflow sanitizer is not in the frozen Cycle 7 suite.

REJECTED as a Cycle 7 direction: adding more U+0020 spaces to chase 7/192 → 0/192 on spent confirmation rows.

REJECTED: running-text `and` to `&` (not prose-equivalent under CMOS/AP). U+2026 ellipsis NFKC-maps to `...`. U+2009 / U+202F NFKC-map to space.

EXTERNAL-VALIDATION-ONLY. Cambridge English Grammar Today: `all`, `both`, and `half` allow optional `of` before articles, demonstratives, and possessives (`all the` / `all of the`) with no meaning change; `of` is obligatory before personal pronouns (`all of them`). Family 11 encodes that bound. That literature is not a local density measurement.

HYPOTHESIS. Clause commas are much more common than sentence terminals on ordinary prose, so Family 10 should raise layout-channel density relative to Family 4 alone. Whether that is enough to replace Cycle 6 spacing after `whitespace-collapse-v1` is a Stage C measurement, not a theorem.

