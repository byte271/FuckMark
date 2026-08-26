# Changelog

## Unreleased — exact user-visible invariance

- Restored Priority Zero: product output must keep the exact user-visible projection of the input.
- Public CLI `release-cli-v4` fail-closes instead of applying contractions or other visible edits.
- `release_transform_registry()` is the empty product-visible-invariance registry. Historical contraction/lexical/syntax/spacing catalogs remain replayable under explicit historical names.
- Added `specs/fuckmark-user-visible-invariance-v1.contract.json` and Cycle 8 invisible-carrier research. No product-authorized carrier is promoted yet.
- Reclassified Cycle 6 formal `NONZERO_RESIDUAL` 7/192 and Cycle 7 visible-edit stages as scientific evidence that is product-disqualified.
- GitHub CI installed-CLI end-to-end now expects unchanged visible text, matching `release-cli-v4`.
- Cycle 8 fixture compare reports visible-projection pass `20/20` for space-carrier arms.
- Chromium `pre` screenshots: U+034F / U+FE00 pixel-equal; U+200C PNG bytes differ.
- Detector-blind GPT-2 / SynthID development scoring on seeds `890000`, `900000`, and `910000` reduced watermarked detections for U+034F space-carrier x1 without unwatermarked inflation on these tiny 4-pair corpora. This is not confirmation and is not a product promotion.
- Product contract loading uses the embedded v1 payload in installed wheels. Writers that replace pinned `specs/cycle8` tokenizer JSON refuse to run without a GPT-2 encoder; the detector harness still scores when tiktoken is absent. Chromium HTML evidence encodes less-than and greater-than as JSON unicode escapes so an ASCII script terminator cannot close the inline script.
- Official install docs now use the tagged GitHub Release wheel plus `SHA256SUMS.txt`. In-repo installers verify that checksum, do not start the CLI, and do not use sudo. `d.q1z.org/mark` is no longer documented as the install path.
- Release Engineering no longer auto-tags, auto-publishes, or deletes merged branches on `main` push. Publishing is `workflow_dispatch` only against an existing tag.
- GitHub Actions `workflow_dispatch` values are passed through `env:` instead of being interpolated into `run:` scripts.
- Interactive CLI copies to the clipboard only with `--copy`.
- Product contract loading requires the frozen v1 hash even when `specs/` is absent from an installed wheel.
- `source_verified_release_transform_registry` keeps verified visible-preserving rules instead of dropping them after promotion checks.
- `BayesianDetectorEvidence.confirmatory_score()` refuses UNVERIFIED status. `raw_score` stays the frozen v1 field.
- `load_bayesian_checkpoint` rejects JSON larger than 64 MiB.

## v0.2.0 — Exact-survival confirmation and release hardening

### Research

- Confirmed the Cycle 4 exact post-retokenization scheduling objective on three independent frozen confirmation corpora.
- The preregistered aggregate outcome is `CONFIRMATORY_IMPROVEMENT`.
- Cycle-3 proxy scheduling left 8/192 transformed watermarked samples detected; exact-survival scheduling left 5/192 detected under the same inherited threshold.
- The measured evasion rate on that frozen open Hugging Face SynthID configuration therefore changed from 95.83% to 97.40%.
- Matched unwatermarked detections remained 2/192 in both aggregate arms.
- Every independent 64-source confirmation corpus improved by one residual detection: 3->2, 3->2, and 2->1.
- Added `exact-survival-greedy-key-blind-v2`, extending the frozen v1 objective with deterministic pairwise completion after single-candidate saturation.
- Added the development-only `content-region-destruction-v1` visible candidate pool without mutating the frozen Cycle-3 ruleset hash.
- Added raw, NFKC, Cf-strip, and combined sanitizer robustness reporting.
- Kept U+200C explicitly quarantined as a diagnostic upper-bound mechanism and excluded it from automatic release behavior.
- The expanded pool plus scheduler v2 reached 0/12 detected in the fresh development run, but this remains development evidence rather than a large-corpus confirmatory claim.

### Release engineering

- Advanced the project version to 0.2.0 across package metadata, package identity, lock metadata, CLI regressions, and clean-install verification.
- Removed the hard-coded `v0.1.0` publication fallback from `Release Engineering`.
- GitHub Release publication now occurs only from an immutable `v*` tag.
- Added a publication guard that requires the Git tag to exactly match the version in `pyproject.toml`.
- Made `tools/verify_release_install.py` derive the expected version from project metadata instead of embedding a release-specific literal.
- Upgraded the core CI and release workflows to current Node 24 GitHub Actions.
- Retained cross-platform wheel/sdist build, `twine check`, clean-install verification, console-command verification, and SHA-256 generation.

### Documentation

- Rewrote the README for the v0.2.0 release and current Cycle 4 evidence.
- Updated all current documentation under `docs/`: CLI, installation, and release process.
- Separated the confirmed 97.40% open-detector research result from the conservative public CLI behavior.
- Preserved frozen historical evidence and v0.1.0 release-readiness artifacts rather than rewriting old contracts to match the new release.

### Claim boundary

The 97.40% figure is specific to the frozen open GPT-2 / Hugging Face SynthID Weighted Mean confirmation configuration and its fixed threshold. v0.2.0 does not claim perfect watermark removal, arbitrary-model transfer, proprietary-detector transfer, future-watermark transfer, or formal confirmation of scheduler v2.

## v0.1.0 — Foundation hardening

v0.1.0 established the deterministic research and release foundation used by Cycle 4. Major work included:

- deterministic source/run identities, hashing, canonical serialization, and replayable evidence;
- token alignment and exact n-gram observation geometry;
- pinned DeepMind and Hugging Face SynthID observation adapters;
- source-conformant Mean and Weighted Mean detector primitives;
- conservative fixed-FPR calibration and pristine-baseline evidence;
- content-addressed corpora, prompt provenance, generation boundaries, and matched watermarked/control validation;
- immutable protected-span extraction and hard semantic invariants;
- deterministic transform registries, candidate enumeration, conflict graphs, traces, and replay;
- TinyDev and MidDev experiment infrastructure with separate planning and scoring paths;
- release-safe CLI behavior for interactive, stream, file, clipboard, and atomic-output use;
- wheel and source-distribution verification on Linux, macOS, and Windows;
- MIT licensing, package metadata, project URLs, and tagged GitHub Release support;
- explicit rejection records for experiments that failed preregistered effectiveness gates;
- quarantining of invisible-format-character experiments that failed sanitizer durability.

The detailed v0.1.0 research chronology remains preserved in the repository history and frozen artifacts under `specs/`. Those historical contracts are not rewritten by later releases.
