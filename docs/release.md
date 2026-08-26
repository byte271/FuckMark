# v0.2.0 Release Process

FuckMark v0.2.0 is a deterministic CLI and research-infrastructure release. The published tag remains historically valid. Current `main` after the visible-invariance repair still reports package version `0.2.0`, but the public CLI algorithm identity is `release-cli-v4` and the release registry is the empty product-visible-invariance registry. Do not treat the v0.2.0 tag's contraction behavior as the current product contract.

The public CLI is restricted to product-authorized invisible transforms. None are authorized yet, so the CLI fail-closes to unchanged text. Cycle 4 exact-survival machinery remains in the research path.

## Release invariants

1. `pyproject.toml`, `fuckmark.__version__`, `uv.lock`, installed CLI output, and the Git tag must agree on `0.2.0` / `v0.2.0`.
2. The release registry is not broadened merely because a development experiment succeeds. Product authorization additionally requires exact visible-projection equality.
3. U+200C remains diagnostic-only and is never promoted into automatic CLI behavior.
4. Visible-edit historical catalogs (contractions, Cycle 6 spacing, Cycle 7 durable families) remain replayable and must not silently become release defaults.
5. Frozen historical contracts and evidence under `specs/` remain byte-stable unless their own protocol explicitly defines a successor artifact.
6. The release must build and clean-install on Linux, macOS, and Windows.
7. Every published GitHub Release must be backed by an immutable `v*` tag.

## Required release sequence

1. Start from the latest green `main`.
2. Update the package version, lock metadata, tests, current documentation, and release notes on a dedicated release branch.
3. Run the complete test suite and `uv lock --check` through CI.
4. Build one wheel and one source distribution.
5. Run `twine check` on both distributions.
6. Clean-install and execute both distributions on Linux, macOS, and Windows.
7. Verify every installed console alias, `--version`, deterministic stream output, wheel metadata, and source-distribution metadata.
8. Generate `SHA256SUMS.txt` from the exact verified wheel and source distribution.
9. Merge the release branch only after required GitHub Actions are green.
10. On the resulting `main` push, rerun the cross-platform package matrix. That push must **not** create tags, publish a GitHub Release, or delete branches.
11. Create and push the immutable `v<project-version>` tag yourself after the package matrix is green. The workflow never runs `git tag`.
12. Publish with `workflow_dispatch` and `publish_github_release=true` on that same commit. The job refuses to run unless the tag already exists and points at the dispatch SHA. If the GitHub Release is missing, it uploads the verified wheel and sdist. It does not delete merged branches.

## Publication workflow

The `Release Engineering` workflow runs its package matrix on Ubuntu, macOS, and Windows. It uses current Node 24 GitHub Actions, builds the distributions independently in each operating-system job, runs `twine check`, and invokes `tools/verify_release_install.py` against both artifacts.

The Linux job uploads the verified release distributions. Publication is **manual**: `workflow_dispatch` with `publish_github_release=true`. The job never creates tags, never uses `persist-credentials` to push, and never deletes merged pull-request branches. It publishes only when `v<project-version>` already exists and matches the dispatch commit.

Direct tag pushes do not trigger the workflow. There is no hard-coded release tag and no commit-message release trigger.

## v0.2.0 scientific result

The preregistered Cycle 4 exact-survival confirmation reports `CONFIRMATORY_IMPROVEMENT` on the frozen open Hugging Face SynthID evaluation:

- Cycle-3 proxy scheduling: 8/192 transformed watermarked samples remained detected.
- Exact-survival scheduling: 5/192 remained detected.
- Measured evasion rate: 95.83% -> 97.40%.
- Matched unwatermarked detections: 2/192 -> 2/192.
- Each of the three independent 64-source confirmation corpora improved by one residual detection.

This evidence supports the exact post-retokenization objective on the frozen open-detector setup. It does not prove perfect watermark removal, proprietary-detector transfer, arbitrary-model transfer, or the superiority of the development-only scheduler v2.

The expanded pool plus scheduler v2 achieved 0/12 detected in its fresh development run, but that result has not yet received the same large-corpus confirmatory treatment and is documented as development evidence only.

## Historical boundary

`specs/fuckmark-v0.1.0-release-readiness-baseline.json` remains an immutable historical artifact. v0.2.0 does not rewrite the old baseline's gate statuses or reinterpret the repository state it captured.

Likewise, rejected experiments remain rejected records. The U+200C visible-projection mechanism stays quarantined because Unicode format-character stripping restores the evaluated detection behavior. Cycle 6 `NONZERO_RESIDUAL` 7/192 remains the frozen formal detector result and is product-disqualified because it used visible ASCII spaces.

## Distribution scope

The GitHub Release is the authoritative v0.2.0 publication produced by this repository workflow. Publishing to another package index is a separate action and must not be implied unless that publication actually occurs and its credentials/workflow are configured.
