# Watermark survival attack plan v1

Status: development research plan. No release authorization and no proprietary-watermark claim.

## Observed plateau

The current real TinyDev result detects all 216 pristine watermarked variants and 171 of 216 transformed variants. Detection therefore remains 79.2%. The mean detector score falls from 0.6264 to 0.5938 and the mean calibrated margin falls from 0.1248 to 0.0921. These 216 variants are dependent measurements derived from four independent watermarked sources, so they are engineering evidence rather than an independent-source effectiveness estimate.

The transformation portfolio changes only about 14% to 16% of eligible watermark observations in the existing variants. The stronger context-survival Beam B6 pilot changes a mean 52.5% of eligible observations and leaves one of four independent watermarked sources detected, compared with three of four for Beam B4. That result is descriptive because the independent-source count is four, but it isolates the likely bottleneck: most existing edits leave most context-conditioned token statistics unchanged.

## Mechanism model

The public SynthID Text description assigns pseudorandom g-values to candidate tokens as a function of preceding token context and secret keys. The detector aggregates g-values after masking repeated contexts. An isolated local edit changes the token at the edit and a bounded suffix of context-conditioned observations; once the original token history is restored, later observations can resynchronize. Increasing the number of random surface candidates does not solve this. Useful primitives need separated, durable retokenization sites that replace more local observation windows at the same visible cost.

Primary mechanism sources:

- [Scalable watermarking for identifying large language model outputs](https://www.nature.com/articles/s41586-024-08025-4)
- [Google DeepMind SynthID Text reference implementation](https://github.com/google-deepmind/synthid-text)
- [Hugging Face SynthID generation utilities](https://huggingface.co/docs/transformers/v4.57.1/internal/generation_utils)
- [Google SynthID Text responsible-AI documentation](https://ai.google.dev/responsible/docs/safeguards/synthid)

## Existing portfolio audit

| Primitive | Current evidence | Decision |
| --- | --- | --- |
| Extra horizontal spacing | High raw opportunity but zero survival under whitespace-collapse and copy/paste profiles | Do not invest further as a durable primitive |
| Contractions | Survive whitespace normalization and preserve meaning, but eligible sites are sparse | Retain as a baseline component |
| Coverage-greedy placement | Does not consistently outperform random placement in current evidence | Do not treat candidate coverage alone as effectiveness |
| Context-survival search | Exact observation destruction tracks detector-margin reduction better than word edit count | Retain as the detector-blind selection mechanism |
| Representation differential audit | Measures cross-tokenizer retokenization with zero detector or secret queries | Use as a prerequisite, never as effectiveness evidence |

## Candidate 1: visible typography retokenization

Hypothesis: replacing internal ASCII apostrophes and hyphen-minus characters with the standard visible U+2019 RIGHT SINGLE QUOTATION MARK and U+2010 HYPHEN will preserve words and sentence structure while changing local token identities across tokenizer families.

Mechanism: each eligible site induces a deterministic retokenization event and changes the context-conditioned observation window after that site. Multiple separated sites should dilute more of the surviving watermark statistic than spacing edits or sparse contraction sites. The transformation uses neither watermark keys nor detector queries.

Opportunity prerequisite: replay over the frozen 500-source real-corpus pre-search artifact `354097a63d58a963b67b12a64928d0a0f11dd46b29012d667ca4702a913f395e` yields 1,723 protected-span-safe candidates over 330 sources. At least two sites are available in 267 of 500 sources (53.4%), four in 163 (32.6%), and six in 103 (20.6%). All 1,723 individual applications pass hard invariants and remain Unicode NFC. The artifact was frozen before search and records zero detector-score selection and zero planner-secret access.

Experiment:

1. Freeze the new registry profile in a distinct content-addressed plan before scoring.
2. Use public tokenizer geometry and context-survival search only; attest zero detector and secret access.
3. Score the frozen plan in a separate process with the existing open weighted-mean SynthID TinyDev evaluator.
4. Compare detection count, score and margin distributions, exact observation destruction, unwatermarked-control distance, text fidelity, and replay hashes against the historical v3 plan at matched policy and realized edit cost.
5. Treat the four-source result as an engineering gate only. A positive result must be repeated on a larger frozen independent-source corpus before promotion.

Kill criteria:

1. Reject if the representation differential audit fails to change tokenization across every pinned tokenizer family for at least two independent sources.
2. Reject if any protected content, hard invariant, Unicode NFC requirement, or exact replay guarantee fails.
3. Reject if independently scored matched-cost results do not improve detection or detector-margin outcomes relative to the historical plan.
4. Reject if unwatermarked-control distance or fidelity is materially worse than the preregistered development tolerance.

## Next candidate if killed

Test explicit visible paragraph-boundary canonicalization as a separately versioned primitive. It has broader opportunity but a higher text-experience cost and stronger tokenizer-family dependence, so it follows rather than precedes visible typography.
