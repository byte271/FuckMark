# Changelog

## v0.4.0 — Product-authorized CLI

- The public command now transforms ordinary English ASCII text. Visible words stay exactly the same. `fuckmark "text"`, pipes, files, and `--stdin` write the payload to stdout. Status and errors go to stderr. `--help` is enough to start. `--visible` prints the original visible text. `--copy` copies that output (UTF-16 on Windows `clip`, UTF-8 elsewhere). Unsupported Unicode is returned unchanged. Invalid UTF-8 and empty input fail closed with an actionable error.
- Install from a clone with `python -m pip install .`. The checksummed GitHub Release wheel is published after the immutable `v0.4.0` tag. Do not retag `v0.3.0`.
- Verified Gate v2 confirmation (spent seeds `1200000` / `1210000` / `1220000`): mix required-sanitizer WM **0/192**, mix UW **0/192**, visible **192/192**, identity **188/192**, UnicodeSanitizer mix **0/192**. Google synthid-text 30-key GPT-2 mix remains **0/192**. This does not remove every watermark. Mn-strip and default-ignorable-strip still restore the source. English ASCII only.
- `release_transform_registry()` stays empty. The frozen apply path is `u034f-ufe00-letter-alt-v1`. The v1 mix sanitizer gate stays FAIL. `required_sanitizers_keep` is not weakened. Do not generate `950000`.

## v0.3.0 — Visible invariance, install and release hardening

- Advanced the project version to 0.3.0 so the identity CLI is not published under the v0.2.0 contraction tag.
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
- Seed `880000` is `PUBLICLY_EXPOSED` by closed unmerged PR #98 and is not eligible as unseen validation. Added `global-seed-ledger-v1` and reserved Cycle 8 scale seeds `930000` / `940000` / `950000` before scale generation.
- Cycle 8 scale exploratory seed `930000` U+034F x1: 0/16 then 0/32 raw transformed WM, then **1/64** on the 64-pair expansion (matched UW 0, visible projection pass, sanitizer matrix matches raw). Do not rewrite 1/64 as zero. Independent replication seed `940000` n=64 is **0/64** raw transformed WM (max score 0.557052 versus threshold 0.557099). Combined 64-pair corpora: **1/128**. Product registry fail-closes carrier sites that would violate frozen hard invariants.
- U+034F is still not product-authorized. Do not generate `950000`. Do not inspect `830000` / `840000` / `850000`.
- Reserved Cycle 8 density exploratory seed `960000` (`carrier density follow-up`) before generation, then scored a detector-blind U+034F space x1 versus space plus word-final letter x1 comparison. Both arms are **1/16** raw transformed WM on the same residual row. Density did not beat space x1. Not product-authorized.
- Cycle 8 letter-x1 (U+034F after ASCII letters, visible-word invariants, quote-interior carrier policy, detector-blind selected-site cap 192) diagnostically rescored seen `930000` n=64, `940000` n=64, and `960000` n=16 to **0** raw transformed WM with clean unwatermarked controls and exact visible projection. Independent reserved seed `970000` (`intra-word carrier follow-up`) is **0/16** then **0/64**. Experimental letter-x1 **0/192** = seen `930000` n=64 plus seen `940000` n=64 plus independent `970000` n=64 (**128/192 seen**, **64/192 independent**). Space-x1 1/64 and 1/16 remain frozen.
- Cycle 8 letter-x1 system benchmark reserved seeds `980000` and `990000` before generation. Fresh independent corpora: letter-x1 **0/128** raw transformed WM, space-x1 **1/128** on the same texts, letter max score 0.554066 versus threshold 0.557099. Local fixtures: visible projection 21/21, protected spans 21/21, Chromium `pre`/textarea/contenteditable pixel-equal on measured samples. Formal confirmation readiness is `NOT_READY`. Letter-x1 is not product-authorized and is not confirmation. Do not generate `950000`.
- Cycle 8 letter-space margin seeds `1000000` and `1010000` were reserved before generation. Combined fresh letter-space is **1/128** on the same residual geometry; do not rewrite that as zero.
- Cycle 8 letter-mix margin reserved seeds `1020000` and `1030000` before generation. Detector-blind U+034F/U+FE00 alternating letter mix is fresh **0/128** raw transformed WM, mix UW **0/128**, worst mix score 0.513691 versus threshold 0.557099 (gap 0.043407). Letter-x1 on those same corpora is 0/128 with max 0.527389. Chromium mix fixtures were pixel-equal on the measured `pre`/textarea/contenteditable surfaces. Mix is not product-authorized and is not confirmation. Formal confirmation readiness remains `NOT_READY`.
- Cycle 8 letter-mix scale reserved seeds `1040000` and `1050000` before generation. Combined with `1020000`+`1030000`, mix is **0/256** raw transformed WM, mix UW **0/256**, worst mix score 0.519522 (gap 0.037577). The two-corpus 0/128 scorecard is not rewritten. This 0/256 is development scale, not confirmation.
- Froze development mechanism `u034f-ufe00-letter-alt-v1` as `cycle8-mix-freeze-v1`. Public CLI remains empty.
- Cycle 8 mix freeze one-shot confirmation on preregistered seeds `830000` / `840000` / `850000`: mix **0/192** raw transformed WM, mix UW **0/192**, visible **192/192**, frozen sanitizers matching raw zeros, worst mix score 0.524300 versus threshold 0.557099 (gap 0.032798). Those seeds are spent. Do not rerun looking for zero. Mix is not product-authorized. Do not generate `950000`.
- Recorded `cycle8-mix-publishability-v1` after merging that freeze onto `main`. Product hardening on that report: software compatibility PASS on the UTF-8 product surface (Latin-1/ASCII/cp1252 unsupported; visible-projection search; raw codepoint search is not the product API). Sanitizer weaknesses still FAIL; assigned-Unicode feasibility and the width-0 closed set found no stronger Priority-Zero invisible mechanism. All 13 enclosing marks change Chromium `pre` pixels. Cross-detector generalization PASSes on Hugging Face nine-key GPT-2 Weighted Mean 0/192 plus independent Google `synthid-text` 30-key GPT-2 mix **0/192** (identity WM 189/192). DistilGPT2 n=16 is HYPOTHESIS second-model transfer (identity 16/16, mix 0/16), not confirmation-scale. Mean versus Weighted Mean on the same GPT-2 Hugging Face adapter remains HYPOTHESIS. Mix is not product-publishable. Tag `v0.3.0` is not retagged.
- Cycle 8 H12 control-code research: DEL and C1 except NEXT LINE survive Mn-strip, default-ignorable-strip, Cf-strip, NFC/NFKC/NFKD, and frozen Cycle 6/7 sanitizers while keeping exact visible projection. Chromium `pre` pixels are host-dependent (research host matched; GitHub Actions Chromium rejected the full apply). Seen DeepMind 30-key diagnostic rescore of seed `920000` n=16 is control-mix **0/16** WM with identity **16/16**. Independent reserved seed `1100000` n=16 is control-mix **0/16** WM with identity **15/16**. This is a new `Cc` class, not a mix sanitizer PASS. Public CLI stays empty. Do not generate `950000`.
- Cycle 8 H13 post-sanitizer mechanism class: no measured Unicode-string transform family is simultaneously sanitizer-surviving on the required set, Chromium-portable, ordinary plain text, and Priority-Zero safe. This is a classification, not a Unicode re-scan, and does not rewrite mix sanitizer FAIL. Public CLI stays empty. Do not generate `950000`.

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
