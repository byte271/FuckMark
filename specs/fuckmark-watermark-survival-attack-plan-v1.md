# Watermark survival attack plan v1

Status: evidence-based development plan. Visible-typography and sentence-boundary soft-break candidates rejected; no implementation retained.

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

## Candidate 2 result: sentence-boundary soft breaks

The detector-blind opportunity audit is complete. Replacing one inter-sentence ASCII space with a single LF produced 1,774 protected-span-safe and N4-surviving sites on the exact 500-source artifact. At least two sites were reachable on 339 sources, four on 205, and six on 109. Every site changed tokenization under pinned GPT-2, Qwen2, and Mistral tokenizers; the pinned T5 whitespace-normalizing negative control changed at zero sites. This passes the preregistered opportunity gate while explicitly limiting the tokenizer claim.

The development-only implementation was evaluated against these frozen prerequisites:

1. NFC-stable, visible, copy/paste-durable behavior.
2. No word replacement, insertion, deletion, or reordering.
3. At least two independent sites in more than half of a frozen source corpus.
4. Tokenization change across at least two pinned tokenizer families.
5. No protected-span, hard-invariant, fidelity, or replay failure.

The distinct detector-blind plan was `tiny-dev-sequence-boundary-softbreak-plan-v1`. Independent scoring increased mean exact observation destruction from 0.38931 to 0.41906 at B4 and from 0.52540 to 0.55514 at B6. Mean detector-margin drop increased slightly from 0.07364 to 0.07452 at B4 and from 0.08551 to 0.08655 at B6. However, detected counts did not improve: B4 remained 3/4 and B6 remained 1/4. Controls remained 0/4 detected and selection observed no detector or secret access.

The candidate therefore triggered the mandatory detected-count kill criterion. Its representation gain was real but not effective enough, so the implementation, experiment-only planner hook, and workflow profile were removed. Exact artifact identities and comparisons are stored in `fuckmark-sequence-boundary-softbreak-v1.rejection.json`.

## Next experiment gate

Do not add another representation-only surface primitive. The next candidate must predict a materially larger change in the detector's aggregated evidence than the roughly three-point increase in mean exact observation destruction seen here, and it must establish that improvement on a larger independent watermarked sample before any release consideration. Detector-blind selection, key blindness, exact replay, protected-span safety, source-grounded fidelity, and matched controls remain mandatory.
