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

Install the package, then start the interactive interface:

```text
FuckMark
```

Paste one or more lines of text. Type `:done` on its own line when the paste is complete. The legacy `ok` terminator remains accepted.

The terminal UI identifies the exact project version, applies the deterministic release registry, reports the number of accepted changes, and copies the result to the system clipboard. ANSI color is enabled only for a compatible interactive terminal and can be disabled with `--no-color` or the standard `NO_COLOR` environment variable.

The CLI uses the same protected-span and hard-invariant checks as the release transform registry. Development-only lexical and syntax rules are not enabled by this command.

On macOS the CLI uses `pbcopy`. On Windows it uses `clip`. On Linux it tries `wl-copy`, `xclip`, `xsel`, and `clip.exe` in that order. Clipboard processes have a ten-second timeout. If clipboard transfer fails, the transformed text is still printed and the command returns exit status 2.

This interface performs deterministic text transformation. It is not a watermark detector and does not claim to remove, defeat, or validate any proprietary watermarking system.

Piped input automatically uses clean stream mode:

```text
printf 'I do not agree.\n' | FuckMark
```

`--stdin` and `--non-interactive` remain available when an explicit mode is preferred. Stream mode writes only transformed text to standard output and never accesses the clipboard unless `--copy` is supplied.

UTF-8 files can be processed without shell redirection:

```text
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
```

Output files are replaced atomically, and the CLI refuses to use the same path for input and output. Run `FuckMark --help` for every option or read `docs/cli.md` for the complete behavior and exit-status contract. `FuckMark --version` reports the project, CLI, and release-registry identities.

## v0.1.0 release readiness

The content-addressed Phase 0 baseline is stored in `specs/fuckmark-v0.1.0-release-readiness-baseline.json`. It binds main commit `afc8794be68c9495348c4934f2dd7e6cf4c61ce9`, the exact release registry, algorithm identities, engineering evidence, known scientific rejection, and every release-program gate. Its artifact hash is `f9834d502c8cfb1e1a3801710dfa3e152fde2de85348d5cd68b4f8334227b350`.

At the freeze, 6 of 26 gates passed, 5 were blocked, and 15 were pending. This immutable historical record is not silently rewritten as later engineering work lands. The explicit scientific blockers include the rejected CAL-SELECT/CAL-AUDIT pair with 55 exact cross-role generated-content collisions and missing blind fidelity evidence. The project license and package license metadata also remain blocked until the owner deliberately selects a license.

The current `release-cli-v3` interface closes the earlier command-line usability gaps, and `Release Engineering` clean-builds and clean-installs both distributions on Linux, macOS, and Windows. A `v*` tag publishes the already verified wheel, source distribution, and SHA-256 manifest only after that matrix succeeds. The release process and remaining boundary are documented in `docs/release.md`.

## Blind fidelity review packets

The development API includes `blind-fidelity-review-packet-v1` for preparing source-grounded human fidelity reviews. `build_blind_review_packet` deterministically samples unique reviewed text pairs from a frozen seed, randomizes pair orientation and reviewer-facing order, and binds both the public packet and private source mapping to content hashes. The public payload contains only opaque item IDs and `text_a`/`text_b`; source IDs, source-versus-transformed orientation, rule identity, and sample hashes remain in the private manifest. `verify_blind_review_packet` replays the packet from the exact source pool before `bind_blind_review_judgment` or `bind_blind_review_judgments` can create review judgments.

This is review tooling, not human evidence. No real reviewer judgments have been collected for the durable development rules, so their source-grounded fidelity status remains `NOT_PROVIDED` and the public release registry remains unchanged.

Replay the frozen artifact with:

```text
python -m fuckmark.release_readiness_baseline --verify-json specs/fuckmark-v0.1.0-release-readiness-baseline.json
```

This validates the historical baseline without requiring later release work to preserve old README, metadata, or registry contents. The `Release Readiness Baseline` workflow also builds and clean-installs the baseline wheel and sdist.

The rejected v2 calibration pair is immutable evidence. The development-only `mid-dev-calibration-independence-v3` protocol is now available for a replacement corpus: it rejects reused prompt, sample, record, and seed identities as structural errors; deduplicates generated text and continuation-token identities by first occurrence; excludes and records CAL-AUDIT rows that collide with retained CAL-SELECT content; and refuses to produce a threshold-sized pair when post-collision counts are insufficient. Its manifests and exclusion records are content-addressed and strictly replayable. A new valid v3 generated corpus has not yet been produced, so calibration independence and confirmatory detector evidence remain blocked.

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

## Frozen high-coverage effectiveness profile

The development-only `key-blind-high-coverage-v1` profile rewrites the local exploratory B16 candidate as an isolated, content-addressed experiment. It combines the existing development surface, lexical, and syntax rules with forward-only reversible contractions, then uses only public GPT-2 tokenizer offsets and `COVERAGE_GREEDY_KEY_BLIND` scheduling. It freezes the independently tested requested operation budget of 16, truncates it to each source's candidate count, and derives the sole schedule seed as `1120000 + sorted_source_index`. The release CLI and the ordinary development registry are unchanged.

The archived exploratory evidence used two independently generated 12-source hold-outs under one fixed open Hugging Face SynthID Weighted Mean detector and a fixed 1% FPR threshold. B10 changed watermarked detection from 12/12 to 8/12. The independently planned B16 run changed it from 12/12 to 6/12 while transformed unwatermarked controls remained 0/12. The B16 transformed-watermarked mean score was still 0.56586, above the 0.56169 threshold and 0.07355 above the transformed-control mean. These are narrow open-detector results, not evidence of watermark removal, unknown-key transfer, proprietary-detector transfer, normalization durability, or release quality. No blind human semantic or style audit has been completed.

The frozen GitHub TinyDev run on four independent attack-development watermarked sources changed detection from 4/4 to 0/4; four matched controls remained 0/4 before and after transformation. Mean watermarked score changed from 0.62644 to 0.52847, while mean control score changed from 0.47821 to 0.48723 and the highest transformed-control score remained 0.03575 below the threshold. The immutable record is `specs/fuckmark-key-blind-high-coverage-v1.tinydev-evidence.json`. This is development-set evidence from one fixed open detector and one replicate, not confirmatory evidence or authorization for a release claim.

The rewritten B16 profile replays all 24 archived samples exactly through candidate enumeration, public-tokenizer geometry, effective-budget truncation, schedule result, selected candidate IDs, and transformed text. Validator v4 intentionally gives new invariant and trace identities, so archived v3 trace hashes are not reused.

The frozen research contract is `specs/fuckmark-open-detector-effectiveness-v1.contract.json`. Planning and scoring use separate commands and separate processes. The planning import graph contains no detector, adapter, Bayesian, watermark-key, or secret-key dependency.

```text
python -m fuckmark.tiny_dev_effectiveness_plan_hf \
  --corpus-json artifacts/tiny-dev-corpus.json \
  --source-code-commit "$(git rev-parse HEAD)"

python -m fuckmark.tiny_dev_effectiveness_score_hf \
  --corpus-json artifacts/tiny-dev-corpus.json \
  --plan-json artifacts/tiny-dev-effectiveness-plan.json \
  --source-code-commit "$(git rev-parse HEAD)"
```

The plan hash covers the full source denominator, requested and effective budgets, profile hash, ruleset hash, public tokenizer geometry, every schedule result, every transformed text, and every hard-invariant trace. Scoring rejects a plan with an unknown field, missing source-budget-replicate coordinate, changed hash, changed profile, changed corpus, changed tokenizer identity, changed source commit, detector access, or secret access.

## Development transformation engine

The release CLI remains limited to the release transform registry. The mechanisms below are development-only and are exercised by the TinyDev and MidDev research workflows.

| Component | Current identity | Behavior |
| --- | --- | --- |
| Surface catalog | `development-surface-rules-v4` | 35 reversible tier-1 spacing rules, including additional function-word and sentence-punctuation sites |
| Context contractions | ruleset hash over 40 forward/reverse rules | Adds reversible `I am`, `you are`, `we are`, `they are`, and `must not` forms that survive whitespace normalization |
| Baseline invariant screen | `context-survival-baseline-invariant-screen-v1` | Hashes every individual hard-invariant decision and excludes expected invalid candidates before baseline scheduling |
| Diverse Beam | `context-survival-diverse-beam-v1` | Preserves ranked elites, reserves capacity for distinct root-edit branches, and retains exact-depth output semantics |
| TinyDev context plan | `tiny-dev-context-survival-plan-v3` | Uses the invariant-screened baseline pool and the separately versioned diverse Beam strategy |
| Environment capture | `environment-snapshot-v3` | Resolves duplicate distributions by runtime import precedence while continuing to accept v1 and v2 snapshots |
| Representation differential audit | `representation-differential-audit-v1` | Replays one transformed pair per independent source through at least two pinned tokenizer families without detector or secret access |

The original `context-survival-beam-v2` function is unchanged. Frozen MidDev protocols that name Beam v2 continue to use that implementation. The diversity strategy has a distinct identity so historical evidence is not silently reinterpreted.

The invariant screen is detector-blind and key-blind. It catches expected individual candidate rejection only. Invalid enumerations, validator failures, replay mismatches, multi-candidate invariant interactions, and other programming errors remain visible. `hard-invariant-validator-v4` canonically equates the unambiguous `you're`, `we're`, and `they're` forms with `you are`, `we are`, and `they are` when followed by `not`; ambiguous forms such as `he's` remain fail-closed.

On the frozen real TinyDev attack-development watermarked sources used by the transformability workflow, surface v4 increased raw candidates from `51` to `65` and independent candidates from `51` to `64`; all four sources remained transformable. The historical v3 invariant screen accepted 147 of 148 combined-context root candidates and rejected one `you are not` contraction. Validator v4 repairs that narrow canonicalization defect under a new algorithm identity. These are opportunity and stability measurements, not detector-effectiveness claims.

The diverse Beam regression proves one synthetic dead-end graph where legacy Beam v2 returns no exact-depth state and the new strategy reaches the requested depth. Real-corpus improvement over Beam v2 is not yet proven. Spacing edits remain fragile under whitespace normalization, and the additional contractions do not eliminate that limitation.

The representation differential audit is a development-only measurement layer for exact multi-tokenizer replay. It binds the source text, transformed text, transform trace, full model/tokenizer identities, token sequences, and canonical alignment metrics. It rejects duplicate source text, dependent variants presented as independent sources, non-NFC text, and changes to invisible or representation-sensitive Unicode code points. Its output is representation evidence only; it does not measure detector reduction or authorize a release rule.

The visible-typography retokenization candidate was rejected after independent scoring. It slightly increased B6 observation destruction but regressed watermarked detection from 1/4 to 2/4 and reduced mean detector-margin drop. The implementation is not retained. The content-addressed rejection record is `specs/fuckmark-visible-typography-v1.rejection.json`; the mechanism diagnosis and next experiment gate are in `specs/fuckmark-watermark-survival-attack-plan-v1.md`.

The sentence-boundary soft-break candidate was also rejected after its preregistered independent scoring gate. It increased mean exact observation destruction from 0.38931 to 0.41906 at B4 and from 0.52540 to 0.55514 at B6, but detected counts remained 3/4 and 1/4. Detector-margin drops improved only slightly, controls produced no false positives, and selection access attestation remained clean; none of those secondary outcomes could waive the mandatory detected-count improvement. The implementation is not retained. The content-addressed rejection record is `specs/fuckmark-sequence-boundary-softbreak-v1.rejection.json`.

Run the local validation layers with:

```text
python -m pytest
python -m pytest tests/test_repository_hygiene.py tests/test_beam_v2.py tests/test_context_survival_plan_v2.py
python -m fuckmark.tiny_dev_transformability --corpus-json artifacts/tiny-dev-corpus.json --json artifacts/tiny-dev-transformability.json
```

The corresponding GitHub workflows are `CI`, `MidDev Full Matrix Gate`, `Real TinyDev Transformability`, `Real TinyDev Transform Evidence`, `Real TinyDev Extended Transform Evidence`, `Real TinyDev Context-Survival Mechanism Pilot`, and `Frozen TinyDev Effectiveness Profile`.

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
52. Strict multi-tokenizer representation differential audits with independent-source accounting and representation-sensitive Unicode rejection
53. Isolated content-addressed `key-blind-high-coverage-v1` planning with complete-denominator replay validation
54. Separate detector-free planning and fixed open-detector scoring processes for exploratory B16 measurement

Python source is English-only and contains no comments or docstrings.
