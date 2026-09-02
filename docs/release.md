# v0.4.1 Release Process

FuckMark v0.4.1 is the audit-fix and five-layer mix release on top of the Gate v2 product-authorization CLI. The public CLI algorithm identity is `release-cli-v12`. Do not retag `v0.4.0`. The historical `v0.3.0` tag is the identity CLI (`release-cli-v4`). The historical `v0.2.0` tag still applies contractions.

## Release invariants

1. `pyproject.toml`, `fuckmark.__version__`, installed CLI output, and the Git tag must agree on `0.4.1` / `v0.4.1`.
2. The release registry is not broadened merely because a development experiment succeeds. Product authorization additionally requires exact visible-projection equality and the frozen mix apply path.
3. U+200C remains diagnostic-only and is never promoted into automatic CLI behavior.
4. Visible-edit historical catalogs (contractions, Cycle 6 spacing, Cycle 7 durable families) remain replayable and must not silently become release defaults.
5. Frozen historical contracts and evidence under `specs/` remain byte-stable unless their own protocol explicitly defines a successor artifact. Mix-freeze and mix-confirmation stay historical snapshots (`product_authorized: false`). The live v1 mix publishability report records dual-layer stress-strip PASS and remains `product_authorized: false`. Gate v2 is the frozen confirmation instrument. Product authorization v2 is the live dual-layer authorization.
6. The release must build and clean-install on Linux, macOS, and Windows.
7. Every published GitHub Release must be backed by an immutable `v*` tag.
8. Gate v2 still records the historical v1 mix sanitizer gate as FAIL. `required_sanitizers_keep` is not weakened. Do not generate `950000`. Live five-layer mix does not restore under Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, Mn then Me then UnicodeSanitizer then frozen Cf-strip, or the required sanitizer bundle.
9. CI for the published artifact must exercise `--text`, `--file`, `--status`, and the documented exit statuses, not only a piped sentence.

## Required release sequence

1. Merge this v0.4.1 branch to green `main`. Clone install (`python -m pip install .`) already runs the product CLI from that tree. The GitHub Release wheel URL is valid only after the next two steps.
2. On the resulting `main` push, rerun the cross-platform package matrix. That push must **not** create tags, publish a GitHub Release, or delete branches.
3. Create and push the immutable `v0.4.1` tag on that merge commit yourself. The workflow never runs `git tag`. Do not tag a pull-request SHA if `main` will be a squash merge. Do not retag `v0.4.0`.
4. Publish with `workflow_dispatch` and `publish_github_release=true` on that same commit. The job refuses to run unless `v0.4.1` already exists and points at the dispatch SHA. If the GitHub Release is missing, it uploads the verified wheel, sdist, and `SHA256SUMS.txt` written by `tools/verify_release_install.py` into `dist/`. It does not delete merged branches.
5. Record the published v0.4.1 wheel SHA-256 in README and `docs/install.md` in a follow-up commit, as was done for v0.4.0.
6. Deploy [mark.q1z.org](https://mark.q1z.org), `https://mark.q1z.org/demo.html` from `docs/demo.html`, and `https://d.q1z.org/mark` from `docs/website.md`, including the PowerShell User-Agent response. The demo must stay static, work from `file://`, and must not run detectors on visitor paste.

## Publication workflow

The `Release Engineering` workflow runs its package matrix on Ubuntu, macOS, and Windows. It uses current Node 24 GitHub Actions, builds the distributions independently in each operating-system job, runs `twine check`, and invokes `tools/verify_release_install.py` against both artifacts.

The Linux job uploads the verified release distributions. Publication is **manual**: `workflow_dispatch` with `publish_github_release=true`. The job never creates tags, never uses `persist-credentials` to push, and never deletes merged pull-request branches. It publishes only when `v<project-version>` already exists and matches the dispatch commit.

Direct tag pushes do not trigger the workflow. There is no hard-coded release tag and no commit-message release trigger.

## Claim boundary

Gate v2 confirmation is GPT-2 / Hugging Face SynthID Weighted Mean plus the real UnicodeSanitizer, with existing DeepMind 30-key GPT-2 transfer. It is not a universal watermark-removal guarantee. Live five-layer mix leaves Me/Cc/Cf residuals and UnicodeSanitizer spaces after Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, Mn then Me then UnicodeSanitizer then frozen Cf-strip, and the required sanitizer bundle. DistilGPT2 n=16 and mean-versus-weighted-mean remain `HYPOTHESIS`. See `docs/limits.md`.

## Historical boundary

`specs/fuckmark-v0.1.0-release-readiness-baseline.json` remains an immutable historical artifact. v0.4.1 does not rewrite the old baseline's gate statuses or reinterpret the repository state it captured.

The `v0.4.0` GitHub Release remains the first product-CLI publication (without later `--text` / `--file` and protection fixes). The `v0.3.0` GitHub Release remains the historical identity CLI. The `v0.2.0` GitHub Release remains the historical contraction CLI.

## Distribution scope

The GitHub Release is the authoritative v0.4.1 publication produced by this repository workflow. Publishing to another package index is a separate action and must not be implied unless that publication actually occurs and its credentials/workflow are configured.
