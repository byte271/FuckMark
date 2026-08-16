# FuckMark

FuckMark is a deterministic research harness for studying how text transformations alter statistical watermark observations.

The project is implemented bottom-up. The current project version is **FuckMark v0.1.0**.

## Project identity

- Display name: `FuckMark`
- Distribution name: `fuckmark`
- Python package: `fuckmark`
- Project version: `v0.1.0`

Historical project identities and the former Python namespace are retired and must not reappear in source, tests, configuration, or documentation.

## Version policy

The project remains on `v0.1.0` for this research line. Fixes and research hardening do not change the project version.

## Current foundation

1. Canonical serialization
2. Content hashing
3. Deterministic seed derivation
4. Immutable source and run identities
5. Deterministic token edit alignment
6. Packed traceback storage with bounded alignment allocation
7. Exact-match and positional alignment maps
8. Conserved contiguous token runs
9. Token n-gram construction
10. Structural observation preservation, replacement, and unmapped classification
11. Substitution observation intervals
12. Overlap-aware interval merging and union coverage
13. Strict public-boundary type and identity validation
14. Project-name and version regression checks
15. Strict source-pin registry and duplicate-safe JSON loading
16. Adapter protocol and deterministic adapter registry
17. Pinned DeepMind SynthID Text reference observation adapter
18. Signed-int64 source-conformant n-gram hashing and g-value generation
19. Source-conformant bounded context-repetition masks
20. Source-conformant EOS observation masks
21. Immutable native observation batches with separated mask semantics
22. Pinned Hugging Face Transformers SynthID observation adapter
23. Source-conformant Hugging Face sampling-table reproduction through an optional Torch bridge
24. Adapter-specific behavioral fingerprints with sampling-table hashing
25. Cross-implementation isolation between the DeepMind reference and Hugging Face observation paths
26. Source-conformant Mean scoring over valid g-values
27. Source-conformant Weighted Mean scoring with normalized layer weights
28. Explicit detector compatibility states with fail-closed Bayesian handling
29. Immutable uncalibrated detector evidence bound to adapter and detector identity

Bayesian checkpoint training, fixed-FPR calibration, transformation rules, experiments, and reporting remain intentionally outside this layer.

Python source is English-only and contains no comments or docstrings.
