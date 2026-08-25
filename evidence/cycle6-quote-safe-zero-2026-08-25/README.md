# Cycle 6 quote-safe zero development evidence

Measurement identity: GPT-2 revision
`607a30d783dfa663caf39e06633721c8d4cfcd7e`, Hugging Face SynthID 5-gram,
threshold `0.5570987654320988`, v4 scheduler, B16 operation budget.

| Corpus | Stable content hash | v4 result | Stable result hash | Sanitizers |
| --- | --- | ---: | --- | --- |
| frozen seed 720000 | `b114cf4d869c5a5d78ac52855a1a480b1f0e605137aee2cb269062880fcc22d3` | 0/16 | `2e1bcf862bfa0d24423ac5f2d8bca6374e3d72020fc9f092e91f5d4f7d66152c` | 0/16 raw, NFKC, Cf, combined |
| disjoint seed 730000 | `e055e0f7a6417c9294a7ed55718cae6fba276cab1256869e1f8babe9d1a84208` | 0/16 | `13731d69a2a710c6a0d37aacb63af23e0a6c112be2093438a64dd074431d2848` | 0/16 raw, NFKC, Cf, combined |

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
- `blind-review-public.json`: detector-blind A/B packet for independent fidelity review.

These are development results, not a formal confirmation or a general watermark-removal
claim. Geometry zero was not reached. Independent fidelity review is pending.
