# Watermark survival attack plan v1

Status: evidence-based development plan. Visible typography candidate rejected; no implementation retained.

## Why 79.2% survives

The current real TinyDev evidence detects all 216 pristine watermarked variants and 171 of 216 transformed variants. The variants destroy only about 14% to 16% of eligible observations, so most context-conditioned token statistics remain unchanged. The 216 variants originate from four independent watermarked sources and are engineering evidence, not 216 independent samples.

Public SynthID Text descriptions assign pseudorandom values to candidate tokens from preceding token context and secret keys, then aggregate those values after repeated-context masking. A local edit changes only a bounded observation neighborhood. Once the original context is restored, later observations can resynchronize. This explains why more random spacing candidates do not create proportionally stronger detector reduction.

Primary mechanism sources:

- [Scalable watermarking for identifying large language model outputs](https://www.nature.com/articles/s41586-024-08025-4)
- [Google DeepMind SynthID Text reference implementation](https://github.com/google-deepmind/synthid-text)
- [Hugging Face SynthID generation utilities](https://huggingface.co/docs/transformers/v4.57.1/internal/generation_utils)
- [Google SynthID Text documentation](https://ai.google.dev/responsible/docs/safeguards/synthid)

## Portfolio audit

| Primitive | Evidence | Decision |
| --- | --- | --- |
| Extra horizontal spacing | High opportunity, but zero survival under whitespace-collapse and copy/paste profiles | Stop expanding |
| Contractions | Durable under whitespace normalization, but sparse | Retain as baseline |
| Coverage-greedy placement | Does not consistently outperform random placement | Do not equate coverage with effectiveness |
| Context-survival search | Observation destruction tracks margin reduction better than word edits | Retain as detector-blind selection |
| Representation differential audit | Measures retokenization with zero detector or secret queries | Use as a prerequisite only |

## Candidate 1 result: visible typography

Hypothesis: standard visible U+2019 apostrophe and U+2010 hyphen substitutions would create separated durable retokenization sites without changing words or sentence structure.

Opportunity passed: a frozen 500-source corpus exposed 1,723 protected-span-safe sites; 267 sources had at least two sites, and all individual edits passed hard invariants and NFC stability.

Effectiveness failed: in independent TinyDev scoring, B6 observation destruction rose from 0.52540 to 0.52957, but detection regressed from 1/4 to 2/4 and mean margin drop fell from 0.08551 to 0.08174. B4 remained 3/4 detected and its mean margin drop fell from 0.07364 to 0.06764. The primitive triggered its preregistered effectiveness kill criterion and was removed. Exact artifact identities and all comparison values are stored in `fuckmark-visible-typography-v1.rejection.json`.

This rejection is informative: public-tokenizer observation destruction is directionally useful but not sufficient. A stronger primitive must provide broader separated context disruption and must improve detector outcomes, not merely representation metrics.

## Next experiment gate

Audit explicit visible sequence-boundary primitives, beginning with paragraph and sentence separator canonicalization, before implementing them. The prerequisite is:

1. NFC-stable, visible, copy/paste-durable behavior.
2. No word replacement, insertion, deletion, or reordering.
3. At least two independent sites in more than half of a frozen source corpus.
4. Tokenization change across at least two pinned tokenizer families.
5. No protected-span, hard-invariant, fidelity, or replay failure.

Only after those gates pass should a distinct detector-blind plan be frozen and independently scored. Kill the idea if B6 detection and detector-margin outcomes do not beat the historical context-survival plan without worsening transformed controls.
