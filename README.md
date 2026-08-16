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

## Interactive CLI

Install the package, then run exactly:

```text
FuckMark
```

Paste one or more lines of text. Type `ok` on its own line and press Enter when the paste is complete.

The CLI prints `Processing...`, applies the current deterministic release transform registry, and copies the resulting text to the system clipboard. When clipboard transfer succeeds it prints `Success. Copied to clipboard.` If no eligible release transformation exists, the original text is copied unchanged.

The CLI uses the same protected-span and hard-invariant checks as the release transform registry. Development-only lexical and syntax rules are not enabled by this command.

On macOS the CLI uses `pbcopy`. On Windows it uses `clip`. On Linux it tries `wl-copy`, `xclip`, `xsel`, and `clip.exe` in that order. If no supported clipboard command is available, the processed text is printed so it is not lost.

This interface performs deterministic text transformation. It is not a watermark detector and does not claim to remove, defeat, or validate any proprietary watermarking system.

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
29. Immutable uncalibrated detector evidence bound to adapter identity, detector identity, and the exact native observation batch hash
30. Conservative finite-sample fixed-FPR calibration with explicit `>` or `>=` threshold semantics
31. Empirical null quantiles, robust null scale, and exact Clopper-Pearson FPR intervals
32. Immutable calibration scopes, detector identities, threshold hashes, and calibration-bundle hashes
33. Calibrated detector decisions with standardized margins and pristine-baseline interpretability gates
34. Immutable corpus manifests with deterministic content-addressed prompt and sample records
35. Exact prompt provenance, licensing, English-language scope, and prompt-family partition enforcement
36. Immutable model/tokenizer identities with revision, chat-template, special-token, padding, BOS, and EOS provenance
37. Exact generation continuation boundaries over padded inputs and attention masks
38. Separate captured-generation and decoded/re-tokenized token tracks for the same source text
39. Matched watermarked/control validation with frozen non-watermark generation parameters and explicit seed policy
40. Exact-output deduplication, TEST_KEYS isolation, target-length feasibility, and corpus integrity hashes
41. Immutable protected-span extraction for URLs, emails, IPs, numeric values, dates, currency, code, Markdown destinations, quotations, paths, CLI flags, citations, math, configured identifiers, and user-marked entities
42. Overlap-merged protected-span manifests with exact UTF-8 content hashes and post-transform protected-content validation
43. Versioned deterministic literal transform rules with a narrow built-in English negation-contraction ruleset
44. Candidate enumeration with explicit precondition failures, protected-overlap rejection, canonical conflict graphs, and input-bound candidate identities
45. Explicit-candidate application with independent enumeration replay, exact operation geometry, immutable traces, and deterministic byte-identical replay
46. Canonical negation and modality signatures that make hard-invariant validation reject semantic polarity or obligation changes
47. Transform dependency isolation with no detector, watermark-key, network, model, or neural inference access in the transform package

Python source is English-only and contains no comments or docstrings.
