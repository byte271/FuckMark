# Cycle 6 quote-safe zero development evidence

Measurement identity: GPT-2 revision
`607a30d783dfa663caf39e06633721c8d4cfcd7e`, Hugging Face SynthID 5-gram,
threshold `0.5570987654320988`, v4 scheduler, B14 operation budget.

| Corpus | Stable content hash | v4 result | Stable result hash | Sanitizers |
| --- | --- | ---: | --- | --- |
| frozen seed 720000 | `b114cf4d869c5a5d78ac52855a1a480b1f0e605137aee2cb269062880fcc22d3` | 0/16 | `73f44b173d7ec55ea80e7d2e9a46b7ea70d8b32682f465dc66643387d99aa8b6` | 0/16 raw, NFKC, Cf, combined |
| disjoint seed 730000 | `e055e0f7a6417c9294a7ed55718cae6fba276cab1256869e1f8babe9d1a84208` | 0/16 | `49e13cbfdd134ef9d22b94c447cc4ad57351e8e2c335008119853c9b0e1bb37a` | 0/16 raw, NFKC, Cf, combined |

Files:

- `original-residual-reachability.json`: full sample 8/10 source, quotation and
  protected spans, candidate/rejection map, token IDs, g-values, evidence attribution,
  alignment, repetition, sanitizer, and limitation classification.
- `frozen16-content-snapshot.json` and `unseen16-content-snapshot.json`: timestamp-free
  corpus snapshots.
- `fresh16-scored-evidence.json` and `unseen16-scored-evidence.json`: scored artifacts
  wrapped with their source corpus and implementation identities.
- `fresh16-geometry.json` and `unseen16-geometry.json`: per-sample exact geometry,
  budget, candidate, conflict, protected-region, quote-container, repetition, and token
  counts.
- `budget-ablation.json`: adverse B10/B12/B13 results and the minimum-successful B14
  selection, with a stable result hash for every tested arm.
- `blind-review-public.json`: detector-blind A/B packet for independent fidelity review.

These are development results, not a formal confirmation or a general watermark-removal
claim. Geometry zero was not reached. Independent fidelity review is pending.
