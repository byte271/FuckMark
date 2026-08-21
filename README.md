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
| Durable portfolio | `development-durable-surface-rules-v1` | Adds 14 reversible development rules for guarded perfect auxiliaries, ellipses, and Markdown list markers without changing any existing registry |
| Durable comparison | `durable-portfolio-comparison-v2` | Replays matched v2 baseline/portfolio evidence and blocks release promotion when fidelity evidence is absent |
| Baseline invariant screen | `context-survival-baseline-invariant-screen-v1` | Hashes every individual hard-invariant decision and excludes expected invalid candidates before baseline scheduling |
| Diverse Beam | `context-survival-diverse-beam-v1` | Preserves ranked elites, reserves capacity for distinct root-edit branches, and retains exact-depth output semantics |
| TinyDev context plan | `tiny-dev-context-survival-plan-v3` | Uses the invariant-screened baseline pool and the separately versioned diverse Beam strategy |
| Environment capture | `environment-snapshot-v2` | Canonicalizes platform metadata while continuing to accept v1 snapshots |

The original `context-survival-beam-v2` function is unchanged. Frozen MidDev protocols that name Beam v2 continue to use that implementation. The diversity strategy has a distinct identity so historical evidence is not silently reinterpreted.

The invariant screen is detector-blind and key-blind. It catches expected individual candidate rejection only. Invalid enumerations, validator failures, replay mismatches, multi-candidate invariant interactions, and other programming errors remain visible. A candidate can be safe in one sentence and rejected in another; for example, the current hard-invariant contract rejects `you are` to `you're` inside `you are not` because the canonical negation signatures differ.

On the frozen real TinyDev attack-development watermarked sources used by the transformability workflow, surface v4 increased raw candidates from `51` to `65` and independent candidates from `51` to `64`; all four sources remained transformable. Across all eight real TinyDev attack-development sources, the combined context registry enumerated `148` root candidates and the invariant screen accepted `147`, deterministically rejecting the single context-invalid `you are not` candidate. These are opportunity and stability measurements, not detector-effectiveness claims.

The diverse Beam regression proves one synthetic dead-end graph where legacy Beam v2 returns no exact-depth state and the new strategy reaches the requested depth. Real-corpus improvement over Beam v2 is not yet proven. Spacing edits remain fragile under whitespace normalization, and the additional contractions do not eliminate that limitation.

### Frozen Diverse Beam real-corpus decision protocol

The `Diverse Beam Real-Corpus A/B` workflow is the bounded promotion experiment for `context-survival-diverse-beam-v1`. It deterministically generates 640 DEV-key watermarked attack-development continuations across 128-token and 256-token cells, removes duplicate generated text or continuation-token tracks before analysis, and freezes exactly 250 unique samples per length before either search strategy runs. The 500 eligible samples cover six prompt families and four domains. Detector scores never participate in generation selection, corpus freezing, search, or promotion.

The search stage runs in a separate tokenizer-only process. Historical `context-survival-beam-v2` and `context-survival-diverse-beam-v1` receive the same frozen samples, candidate registry and ordering, protected spans, hard invariants, tokenizer identity, public repetition geometry, B1/B2/B4/B6 budgets, width 32, risk ceiling, and visible-cost model. Each strategy is replayed from fresh expanders, and every one of the 4,000 sample/budget/strategy rows binds exact-depth status, state and frontier hashes, opportunity counts, dead ends, accepted transitions, duplicate suppression, risk, cost, token distance, runtime, and access attestations.

The preregistered sufficient promotion rule requires at least one matched rescue, zero losses on Beam v2 successes, zero accepted hard-invariant or protected-content violations, exact structural replay, no detector or watermark-secret access, no more than a 10% median visible-cost increase in relevant matched budget cells, and no more than 2x aggregate median runtime. Exact McNemar results are reported separately for every budget. A valid negative result keeps Beam v2 and does not fail the engineering workflow; incomplete, contaminated, malformed, underpowered, or nondeterministic evidence fails closed. Until the real workflow finishes and its content-addressed artifact is reviewed, Diverse Beam remains development-only and no real-corpus advantage is claimed.

The workflow uploads all 32 generation shards, the frozen corpus, all 64 matched search shards, the strict analysis artifact, and a SHA-256 manifest. The tokenizer-only search dependency is pinned separately in `requirements-tokenizer.txt`. Local unit coverage can be reproduced with:

```text
python -m pytest tests/test_diverse_beam_corpus.py tests/test_diverse_beam_ab.py tests/test_repository_hygiene.py
```

### Frozen normalization-survival benchmark

The `Normalization Survival Benchmark` workflow reuses the 500-sample corpus frozen by Diverse Beam run `32504847438`; it does not regenerate, score, or select text. `normalization-survival-benchmark-v2` enumerates the context-survival contractions and Surface v4 spacing rules once per source, screens every candidate against hard invariants, and measures five preregistered normalizers:

| ID | Frozen operation |
| --- | --- |
| `N0_IDENTITY` | Preserve text exactly |
| `N1_WHITESPACE_COLLAPSE` | Remove trailing horizontal whitespace and collapse horizontal runs while preserving line endings |
| `N2_LINE_ENDINGS_LF` | Convert CRLF and CR line endings to LF |
| `N3_UNICODE_NFC` | Apply Unicode NFC |
| `N4_COPY_PASTE_WHITESPACE` | Convert line endings to LF, remove trailing horizontal whitespace, and collapse horizontal runs |

Every candidate/profile row binds the source, candidate, rule, transformed text, hard-invariant report, normalizer, normalized source, normalized output, and survival decision by hash. Per-sample evidence distinguishes raw candidates, maximum non-overlapping opportunity, invariant-safe opportunity, normalization-surviving opportunity, and replay-verified B1/B2/B4/B6 witnesses. For each budget, v2 searches every geometrically legal combination until it finds a hard-invariant-safe normalized witness or exhausts the finite search space; exact interval-capacity pruning cannot discard a feasible selection. Expected individual or combined invariant rejection is counted and excluded; malformed enumeration, registry replay disagreement, and artifact provenance errors remain fatal.

The historical v1 witness builder tested only one greedily selected maximum-cardinality interval set. A regression demonstrates a source where its first overlapping alternative creates an invalid combined modality signature while a second alternative reaches the same exact budget legally. The v1 artifact loader remains available for strict historical replay, but v1 evidence must not be reinterpreted as exhaustive. The v2 identifiers bind the corrected search and schema, including per-budget reachability instead of a monotonic compatible-prefix assumption.

The benchmark reports family/rule survival rates, exact-budget reachable sample counts, Surface v4 disappearance under N1/N4, contraction survival under N1/N4, and whether enough N4 B2 opportunity exists to justify a later matched survival-aware scheduler experiment. Normalization survival alone never promotes a rule into the release registry; fidelity qualification remains a separate requirement. The benchmark is detector-blind and key-blind.

Strict local v2 replay of frozen corpus artifact `9455132579` from workflow run `32504847438` measured 25,795 raw candidates and 25,774 invariant-safe candidates across all 500 sources. The artifact contains 128,975 candidate/profile rows. All 25,229 invariant-safe Surface v4 candidates disappeared under both N1 and N4. All 545 invariant-safe contraction candidates survived both profiles. Exhaustive N4 reachability was 231/500 at B1, 127/500 at B2, 40/500 at B4, and 16/500 at B6, identical to the earlier v1 corpus totals; no real-corpus reachability cell changed. The B2 rate is 25.4%, below the preregistered 50% prerequisite, so the benchmark answers `INSUFFICIENT_DURABLE_CHOICE_FOR_SCHEDULER_PREFERENCE`. This proves a durable-opportunity bottleneck on this corpus; it does not measure detector response, establish semantic fidelity for every rule, or authorize release promotion. The final workflow-bound v2 benchmark artifact is pending.

After obtaining the frozen corpus artifact, reproduce the benchmark with:

```text
python -m fuckmark.normalization_survival_benchmark \
  --corpus-json artifacts/diverse-beam-frozen-corpus.json \
  --source-code-commit "$(git rev-parse HEAD)" \
  --source-workflow-run-id 32504847438 \
  --json artifacts/normalization-survival-benchmark.json
python -m pytest tests/test_normalization_survival.py tests/test_repository_hygiene.py
```

### Development durable portfolio gate

The `Durable Portfolio Real-Corpus Gate` workflow compares the frozen context baseline with the separate `durable_portfolio_transform_registry()`. Existing default, development, context-survival, and release registries are unchanged. The new catalog contains seven reversible pairs: four perfect-auxiliary pairs (`I have`, `you have`, `we have`, and `they have`) guarded by frozen participle and optional-adverb allowlists; ASCII/Unicode ellipses; Markdown unordered-list markers; and Markdown single-digit ordered-list delimiters. Markdown marker changes are tier-0 format rules; the other rules are tier-1 surface rules. Ambiguous `let us` to `let's` conversion was deliberately excluded.

Every rule has a distinct ID and content hash. Enumeration applies protected-span and grammar preconditions before candidacy, application replays the complete registry, and `durable-portfolio-comparison-v2` requires both inputs to use the exhaustive normalization-survival v2 contract and every baseline candidate/profile row to remain present. Its development success gate requires at least a 10% gain in independent N4 opportunities, at least one matched exact-budget gain, zero matched losses, zero new invariant rejection, complete normalization survival for every observed new rule, and no detector or watermark-secret access. Nested counts, decisions, rule declarations, release status, and the final artifact hash are replay-validated. The historical comparison-v1 artifact loader remains available for attribution, but v1 comparisons are not accepted as inputs to a new v2 comparison.

A strict local v2 matched replay over the 500 frozen samples measured 25,795 baseline and 25,990 portfolio candidates. Invariant-safe counts rose from 25,774 to 25,969. Independent N4-surviving opportunity rose from 545 to 740, a 35.78% relative gain. The portfolio added 195 candidates: 48 guarded perfect-auxiliary forms and 147 punctuation/format forms. All 195 were invariant-safe and survived N4. Exhaustive matched exact-budget reachability rose from 231 to 266 samples at B1, 127 to 157 at B2, 40 to 62 at B4, and 16 to 28 at B6, for 99 gains and zero losses across the four cells. These totals are identical to the earlier v1 measurement; the exhaustive correction changed no real-corpus cell. The development decision was `MATERIAL_DURABLE_OPPORTUNITY_INCREASE`.

This result is opportunity evidence, not detector evidence. All 14 new rules remain development-only with `source_grounded_fidelity_status=NOT_PROVIDED`; the release decision is `DEVELOPMENT_ONLY_FIDELITY_EVIDENCE_REQUIRED`. N4 B2 reachability is 31.4%, still below the frozen 50% prerequisite, so survival-aware scheduling remains blocked. The workflow-bound artifact is pending.

After obtaining the frozen corpus artifact, reproduce the matched gate with:

```text
python -m fuckmark.normalization_survival_benchmark \
  --corpus-json artifacts/diverse-beam-frozen-corpus.json \
  --source-code-commit "$(git rev-parse HEAD)" \
  --source-workflow-run-id 32504847438 \
  --registry context-baseline \
  --json artifacts/baseline-normalization-survival.json
python -m fuckmark.normalization_survival_benchmark \
  --corpus-json artifacts/diverse-beam-frozen-corpus.json \
  --source-code-commit "$(git rev-parse HEAD)" \
  --source-workflow-run-id 32504847438 \
  --registry durable-portfolio \
  --json artifacts/portfolio-normalization-survival.json
python -m fuckmark.durable_portfolio_analyze \
  --baseline-json artifacts/baseline-normalization-survival.json \
  --portfolio-json artifacts/portfolio-normalization-survival.json \
  --json artifacts/durable-portfolio-comparison.json \
  --require-success
python -m pytest \
  tests/test_durable_surface_rules.py \
  tests/test_durable_portfolio.py \
  tests/test_normalization_survival.py \
  tests/test_repository_hygiene.py
```

Run the local validation layers with:

```text
python -m pytest
python -m pytest tests/test_repository_hygiene.py tests/test_beam_v2.py tests/test_context_survival_plan_v2.py
python -m fuckmark.tiny_dev_transformability --corpus-json artifacts/tiny-dev-corpus.json --json artifacts/tiny-dev-transformability.json
```

The corresponding GitHub workflows are `CI`, `Diverse Beam Real-Corpus A/B`, `Normalization Survival Benchmark`, `Durable Portfolio Real-Corpus Gate`, `MidDev Full Matrix Gate`, `Real TinyDev Transformability`, `Real TinyDev Transform Evidence`, `Real TinyDev Extended Transform Evidence`, and `Real TinyDev Context-Survival Mechanism Pilot`.

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
52. Five-profile normalization-survival measurement with candidate-level provenance and replay-verified exact-budget witnesses
53. Separately versioned guarded perfect-auxiliary, ellipsis, and Markdown-marker development rules with inverse semantic-site resolution
54. Matched durable-portfolio evidence with baseline-row preservation, nested replay validation, and mandatory fidelity blocking

Python source is English-only and contains no comments or docstrings.
