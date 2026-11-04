# Boundary-aware, constraint-first reconstruction: experimental v1

**This is a working research prototype, not a verified LLM-watermark remover.**
It changes ordinary visible wording. It does not extend the Unicode carrier stack,
change the production CLI, ship a detector product, or claim a novel watermark attack.

## What actually runs

The end-to-end frontend supports a deliberately narrow English reporting grammar:

```text
Orion Labs reported a revenue of 120 USD in 2025.
Vega Systems did not report a cost of 42 EUR in 2024.
```

Five metric families are supported: revenue/cost, distance, duration, and mass,
with explicit compatible units. Amounts are nonnegative decimal literals. Entities
follow a bounded ASCII proper-name grammar; years are 1900-2199. Positive and
negative reporting statements are accepted in four active/passive/time-fronted
forms. Unsupported prose, quotations, code, hidden characters, and languages are
not silently rewritten. The text API returns the original with `unsupported`;
the CLI returns exit 3. This is not an arbitrary-prose semantic parser.

Each accepted sentence becomes an ordered frame:
`(entity, metric, exact amount literal, unit, year, negated)`.
All alternatives must reparse to the same frame. The output is checked again
against the ordered frames and numeric literals. This is stronger than matching
an unordered bag of numbers, but it proves only the restricted grammar contract,
not the truth of assertions or semantic equivalence for unrestricted language.

The generic low-level planner accepts finite candidate lattices. It is **not**
a semantic verifier; do not feed unchecked LLM paraphrases into it and treat its
score as a quality guarantee. The included frontend supplies grammar-checked
candidates. Connecting a general-purpose generator/semantic verifier remains work
not implemented here.

## Algorithm, not another hidden-character layer

For each supported sentence, construct a finite candidate set. Search their
combinations jointly under a fixed normalized-word edit budget. The state carries
last `k-1` tokens for every measurement view, accumulated retained-window counts,
and edit cost. Extending a state scores both interior and cross-sentence windows.

The objective is lexicographic:

1. Minimize the largest source-normalized retained-window count across views.
2. Minimize the sum of those fractions.
3. Minimize edit cost, then choose a deterministic candidate-index path.

The denominator is fixed from the **source**, so adding filler cannot dilute the
score. A retained output window is counted when its tuple occurs anywhere in the
source, including at a different location. Repetition is counted with output
multiplicity; this is not an implementation of SynthID's repetition masking.

Pareto pruning is allowed only for equal tail states: a state can dominate another
only when its cost and every accumulated count are no larger. Future increments
are then identical for equal suffix choices. Exactness is conditional on the given
finite candidate lattice, supported tokenizers, objective, and successful bounded
completion. It is not an optimum over all possible rewrites.

A full-output recomputation must agree with the dynamic program. Unsupported
non-compositional tokenizers, including an arbitrary BPE callback, are rejected
rather than falsely declared exact. State/evaluation limits return the unchanged
source and `search_limit`; no truncated search is labeled optimal.

Current views are NFKC/casefold word 3-grams, word 5-grams, and word-plus-punctuation
5-grams. These are proxies, **not GPT-2/BPE observations or watermark scores**.
There are no watermark keys, detector queries, model/API calls, or new runtime
dependencies in candidate generation and selection.

## Run from a repository checkout

```sh
python -m research.reconstruction --text "Orion Labs reported a revenue of 120 USD in 2025. Vega Systems did not report a cost of 42 EUR in 2024." --json
python -m research.reconstruction --file input.txt --budget 32 --json
python -m pytest -q tests/test_reconstruction.py
python -m research.reconstruction.benchmark --output geometry-128.json
python -m research.reconstruction.legacy_control --output legacy-control.json
```

The research directory intentionally is not included in the current `fuckmark*`
wheel package selection. Existing `fuckmark` commands and evidence are unchanged.
Exit 0 means a supported reconstruction finished, not that a watermark was removed.
Exit 2 is invalid input/configuration; exit 3 is unsupported input or a search limit.
JSON receipts always include `watermark_removal_verified: false`.

## Measured results, and their exact scope

Local environment: CPython 3.13.5, Linux. New tests: **102 passed**. Existing CLI,
CLI I/O, and protected-machine-text tests: **70 passed**. Combined: **172 passed**.
This is targeted local validation, not a complete checkout CI result.

The protocol was written before the first development benchmark. The 128 fixtures
are newly synthesized controlled-grammar statements, **not watermarked LLM text**.
No previous frozen confirmation corpus was used. The greedy comparator uses the
same alternatives and budget, recomputes whole-output geometry, and changes one
candidate position at a time. It is not the repository's historical scheduler.

| Measurement | Result |
| --- | --- |
| Supported documents reconstructed | 128 / 128 |
| Ordered grammar-frame checks | 128 / 128 |
| Joint search strictly better than greedy on worst-view retention | 51 / 128 |
| Tied on worst-view retention | 77 / 128 |
| Mean worst-view retention, joint search | 0.5987639731 |
| Mean worst-view retention, greedy | 0.6205182055 |
| Exhaustive-search agreement on benchmark fixtures | 24 / 24 |
| Additional randomized exhaustive-search test cases | 48 / 48 |
| Generated frame/form roundtrips tested | 2,048 |
| Real watermark-detector evaluation | **Not run** |

Canonical benchmark row digest:
`36d173f4e1521f74a963754c917724eaf4e5ba37b62201feb662a5510f495736`.
The benchmark test pins it; elapsed time is excluded. `results.json` contains the
summary. Re-running the command produces all source/output texts and receipts.

In a separate control against baseline commit
`09c8cbf184e37e2e934e133b74a5db9af67b4f97`, exact deletion of known FuckMark carriers
restored all 128 legacy outputs. All 128 new outputs survived NFKC plus that same
carrier deletion unchanged. This demonstrates the new representation does not
rely on those carriers. It does **not** prove resistance to arbitrary normalization,
semantic rewrites, a tokenizer, or an actual watermark detector.

## Limits and the next scientific gate

The local runtime lacked pretrained model/tokenizer artifacts, and outbound DNS
failed. No real SynthID, KGW, proprietary detector, cross-tokenizer, or real-LLM
removal claim is made. Proxy optimization can fail to reduce a real detector score;
protected facts and short texts can retain strong signals. Meaning-preserving
reconstruction may also fail against semantic watermark designs.

Before product promotion: integrate an independently checked general-text
candidate provider; use genuine tokenizer handling with boundary verification;
freeze fresh model/watermark/threshold configurations; retain unsupported cases
and failures in the denominator; and measure fidelity and detection separately.
Neither the production CLI nor frozen scientific records should change merely
because this mechanism benchmark passes.

Prior work already studies paraphrase and character-level watermark attacks:
- https://arxiv.org/abs/2508.20228
- https://arxiv.org/abs/2509.09112

This prototype's measured contribution is a small, reproducible constrained
reconstruction implementation with exact joint selection on its finite lattice.
A broader novelty or watermark-efficacy claim remains unestablished.
