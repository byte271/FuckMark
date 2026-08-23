# v0.2.0 Release Process

FuckMark v0.2.0 is a deterministic CLI and research-infrastructure release. The release contains the Cycle 4 exact-survival research machinery and its confirmatory evidence path, while the public CLI remains restricted to the separately reviewed release transform registry.

## Release invariants

1. `pyproject.toml`, `fuckmark.__version__`, `uv.lock`, installed CLI output, and the Git tag must agree on `0.2.0` / `v0.2.0`.
2. The release registry is not broadened merely because a development experiment succeeds.
3. U+200C remains diagnostic-only and is never promoted into automatic CLI behavior.
4. Frozen historical contracts and evidence under `specs/` remain byte-stable unless their own protocol explicitly defines a successor artifact.
5. The release must build and clean-install on Linux, macOS, and Windows.
6. Every published GitHub Release must be backed by an immutable `v*` tag.

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
10. On the resulting `main` push, rerun the cross-platform release matrix.
11. If `v<project-version>` does not already exist, the release job creates that immutable tag at the exact verified `main` commit.
12. The same job separately checks whether the GitHub Release exists. If the tag exists but the Release does not, publication is repaired from the verified distributions instead of silently stopping in a half-published state.
13. Later `main` pushes with the same project version and an existing GitHub Release are safe no-ops for publication.

## Publication workflow

The `Release Engineering` workflow runs its package matrix on Ubuntu, macOS, and Windows. It uses current Node 24 GitHub Actions, builds the distributions independently in each operating-system job, runs `twine check`, and invokes `tools/verify_release_install.py` against both artifacts.

The Linux job uploads the verified release distributions. On a `main` push, the publication job derives `v<project-version>` from `pyproject.toml`, checks the Git tag and GitHub Release independently, creates the tag only when it is missing, and creates the GitHub Release only when it is missing. This makes publication idempotent and repairs the specific boundary where a tag was created successfully but Release creation failed afterward.

Direct tag pushes do not trigger the release workflow. That avoids duplicate release runs racing against the `main` run that created the tag. There is no hard-coded release tag and no commit-message release trigger.

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

Likewise, rejected experiments remain rejected records. The U+200C visible-projection mechanism stays quarantined because Unicode format-character stripping restores the evaluated detection behavior.

## Distribution scope

The GitHub Release is the authoritative v0.2.0 publication produced by this repository workflow. Publishing to another package index is a separate action and must not be implied unless that publication actually occurs and its credentials/workflow are configured.
