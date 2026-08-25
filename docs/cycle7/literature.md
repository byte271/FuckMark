# Cycle 7 literature notes

Claim labels used below: VERIFIED, SOURCE-BOUND, HYPOTHESIS, UNKNOWN, REJECTED, EXTERNAL-VALIDATION-ONLY.

## SynthID-Text

SOURCE-BOUND. Google documents SynthID-Text as a logits-processor watermark using a keyed g-function and tournament sampling. Detectability uses n-gram context. Larger `ngram_len` is more detectable and more brittle to edits. Public docs state robustness to cropping, a few word changes, and mild paraphrasing, with large detector-confidence loss under thorough rewrite or translation.

- https://ai.google.dev/responsible/docs/safeguards/synthid
- https://huggingface.co/blog/synthid-text

This repository's Cycle 6 result is the local VERIFIED measurement for the frozen GPT-2 / mean-score protocol: 183/192 pristine detections reduced to 7/192 transformed detections, 0/192 transformed unwatermarked, `NONZERO_RESIDUAL`. That is not a claim about proprietary production detectors.

## Edit-channel / synchronization

SOURCE-BOUND / HYPOTHESIS. Context-hashed watermarks re-synchronize after a local edit once the sliding n-gram window has moved past the edit. Cycle 6 spacing inserts extra U+0020 tokens that change GPT-2 segmentation, then ordinary space-collapse removes those tokens and restores the original token sequence. That collapse failure is VERIFIED here as a mechanism class, not as a universal watermark theorem.

EXTERNAL-VALIDATION-ONLY. Zhao et al. style analyses of SynthID robustness (paraphrase, back-translation, layer-inflation) are not reproduced in this repository and must not be cited as FuckMark results.

## Deterministic non-neural edits

HYPOTHESIS. Unambiguous contractions and closed orthographic variants change tokenizer boundaries without depending on repeated spaces. Whether they destroy enough SynthID observation windows on GPT-2 text is a Cycle 7 measurement, not a literature conclusion.

REJECTED as a Cycle 7 direction: adding more U+0020 spaces to chase 7/192 → 0/192 on spent confirmation rows.
