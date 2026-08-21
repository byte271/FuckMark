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

## v0.1.0 release readiness

The content-addressed Phase 0 baseline is stored in `specs/fuckmark-v0.1.0-release-readiness-baseline.json`. It binds main commit `afc8794be68c9495348c4934f2dd7e6cf4c61ce9`, the exact release registry, algorithm identities, engineering evidence, known scientific rejection, and every release-program gate. Its artifact hash is `f9834d502c8cfb1e1a3801710dfa3e152fde2de85348d5cd68b4f8334227b350`.

At the freeze, 6 of 26 gates passed, 5 were blocked, and 15 were pending. The explicit blockers include the missing owner-selected project license, missing package license metadata, the unqualified public release engine, and the rejected CAL-SELECT/CAL-AUDIT pair with 55 exact cross-role generated-content collisions. No public `v0.1.0` tag or GitHub Release exists yet.

Replay the frozen artifact with:

```text
python -m fuckmark.release_readiness_baseline --verify-json specs/fuckmark-v0.1.0-release-readiness-baseline.json
```

This validates the historical baseline without requiring later release work to preserve old README, metadata, or registry contents. The `Release Readiness Baseline` workflow also builds and clean-installs the baseline wheel and sdist.

## Open SynthID smoke experiment

A development-only runner can test the current release transform against the pinned open Hugging Face SynthID implementation without using watermark keys or detector scores during transform selection.

Install the package and the separate smoke dependencies:

```text
python -m pip install -e ".[dev]"
python -m pip install -r requirements-smoke.txt
```

Run the built-in 20-prompt smoke set:

```text
python -m fuckmark.synthid_smoke_hf --model openai-community/gpt2 --prompt-limit 20
```

The runner generates matched control and watermarked continuations with the same per-prompt generation seed, transforms both groups before any detector scoring, and records pristine/transformed Weighted Mean scores. It also reports transformed-control drift so a lower watermarked score cannot hide a simultaneous false-positive increase.

The default report files are `artifacts/synthid-smoke.json` and `artifacts/synthid-smoke.csv`. The artifacts directory is ignored by Git. The threshold in this smoke report is descriptive and is derived only from pristine control scores. A smoke result is development evidence, not a confirmatory result and not evidence about a proprietary watermarking system.

## Development transformation engine

The release CLI remains limited to the release transform registry. The mechanisms below are development-only and are exercised by the TinyDev and MidDev research workflows.

| Component | Current identity | Behavior |
| --- | --- | --- |
| Surface catalog | `development-surface-rules-v4` | 35 reversible tier-1 spacing rules, including additional function-word and sentence-punctuation sites |
| Context contractions | ruleset hash over 40 forward/reverse rules | Adds reversible `I am`, `you are`, `we are`, `they are`, and `must not` forms that survive whitespace normalization |
| Baseline invariant screen | `context-survival-baseline-invariant-screen-v1` | Hashes every individual hard-invariant decision and excludes expected invalid candidates before baseline scheduling |
| Diverse Beam | `context-survival-diverse-beam-v1` | Preserves ranked elites, reserves capacity for distinct root-edit branches, and retains exact-depth output semantics |
| TinyDev context plan | `tiny-dev-context-survival-plan-v3` | Uses the invariant-screened baseline pool and the separately versioned diverse Beam strategy |
| Environment capture | `environment-snapshot-v2` | Canonicalizes platform metadata while continuing to accept v1 snapshots |

The original `context-survival-beam-v2` function is unchanged. Frozen MidDev protocols that name Beam v2 continue to use that implementation. The diversity strategy has a distinct identity so historical evidence is not silently reinterpreted.

The invariant screen is detector-blind and key-blind. It catches expected individual candidate rejection only. Invalid enumerations, validator failures, replay mismatches, multi-candidate invariant interactions, and other programming errors remain visible. A candidate can be safe in one sentence and rejected in another; for example, the current hard-invariant contract rejects `you are` to `you're` inside `you are not` because the canonical negation signatures differ.

On the frozen real TinyDev attack-development watermarked sources used by the transformability workflow, surface v4 increased raw candidates from `51` to `65` and independent candidates from `51` to `64`; all four sources remained transformable. Across all eight real TinyDev attack-development sources, the combined context registry enumerated `148` root candidates and the invariant screen accepted `147`, deterministically rejecting the single context-invalid `you are not` candidate. These are opportunity and stability measurements, not detector-effectiveness claims.

The diverse Beam regression proves one synthetic dead-end graph where legacy Beam v2 returns no exact-depth state and the new strategy reaches the requested depth. Real-corpus improvement over Beam v2 is not yet proven. Spacing edits remain fragile under whitespace normalization, and the additional contractions do not eliminate that limitation.

Run the local validation layers with:

```text
python -m pytest
python -m pytest tests/test_repository_hygiene.py tests/test_beam_v2.py tests/test_context_survival_plan_v2.py
python -m fuckmark.tiny_dev_transformability --corpus-json artifacts/tiny-dev-corpus.json --json artifacts/tiny-dev-transformability.json
```

The corresponding GitHub workflows are `CI`, `MidDev Full Matrix Gate`, `Real TinyDev Transformability`, `Real TinyDev Transform Evidence`, `Real TinyDev Extended Transform Evidence`, and `Real TinyDev Context-Survival Mechanism Pilot`.

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
48. Development-only surface v4 and normalization-surviving contraction opportunity catalogs
49. Deterministic invariant-aware baseline scheduling with content-addressed rejection evidence
50. Separately versioned root-branch-diverse Beam search without changing frozen Beam v2 semantics
51. Canonical cross-platform environment capture with legacy v1 snapshot compatibility

Python source is English-only and contains no comments or docstrings.
