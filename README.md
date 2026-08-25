<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a deterministic, detector-blind research harness for studying how small text transformations change statistical watermark observations while preserving the source text as much as possible.

**Current release: v0.2.0**  
Website: [mark.q1z.org](https://mark.q1z.org)  
License: MIT

## What changed in v0.2.0

v0.2.0 promotes the Cycle 4 research infrastructure and the first confirmatory improvement from exact post-retokenization observation scheduling.

On the frozen open Hugging Face SynthID confirmation protocol, the Cycle-3 proxy scheduler left **8 of 192** transformed watermarked samples detected. The exact-survival scheduler left **5 of 192** detected under the same inherited threshold and corpus protocol. That changes the measured evasion rate from **95.83% to 97.40%** on this specific confirmation setup. Matched unwatermarked detections remained **2 of 192 in both arms**.

All three independent 64-sample confirmation corpora moved in the same direction:

| Confirmation seed | Cycle-3 proxy | Exact-survival |
| --- | ---: | ---: |
| 530000 | 3/64 detected | 2/64 detected |
| 540000 | 3/64 detected | 2/64 detected |
| 550000 | 2/64 detected | 1/64 detected |
| **Aggregate** | **8/192** | **5/192** |

The preregistered aggregate outcome is `CONFIRMATORY_IMPROVEMENT`.

The expanded `content-region-destruction-v1` pool and pairwise-completion scheduler v2 reached 0/12 detected in the fresh development run, but that 12-source result is not a formal large-corpus confirmation. v0.2.0 therefore does **not** claim that v2 is proven stronger than exact-survival v1.

## Claim boundary

The 97.40% result is narrow research evidence, not a universal watermark-removal guarantee.

It applies to the repository's frozen open GPT-2 / Hugging Face SynthID Weighted Mean confirmation configuration, fixed threshold, exact source protocol, and measured corpus. It does not establish proprietary-detector transfer, arbitrary-model transfer, unknown future watermark transfer, perfect removal, or semantic equivalence under every input.

The public CLI also remains deliberately conservative. It uses only the release transform registry. Development schedulers, detector code, experimental search, and the quarantined U+200C diagnostic registry are not automatically selected by the command-line product path.

## Install

Python 3.11 or newer is required.

### Linux

```sh
curl -fsSL https://d.q1z.org/mark | sh
```

### macOS

```sh
curl -fsSL https://d.q1z.org/mark | sh
```

### Windows

Run PowerShell:

```powershell
irm https://d.q1z.org/mark | iex
```

Verify the installation:

```text
FuckMark --version
```

For a manual tagged install:

```text
python -m venv .venv
python -m pip install https://github.com/byte271/FuckMark/archive/refs/tags/v0.2.0.zip
```

See [`docs/install.md`](docs/install.md) for platform details and update behavior.

## CLI

The same entry point is installed as `FuckMark`, `Fuckmark`, and `fuckmark`.

Interactive mode:

```text
FuckMark
```

Paste text and finish with `:done` on its own line. The legacy `ok` terminator remains accepted.

Stream mode:

```sh
printf 'I do not agree.\n' | FuckMark
```

File mode:

```text
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
```

Useful options:

- `--version` prints the project and release algorithm identities.
- `--stdin` / `--non-interactive` forces stream mode.
- `-o FILE` / `--output FILE` writes UTF-8 output atomically.
- `--copy` also copies the transformed text to the platform clipboard.
- `-q` / `--quiet` hides interactive status messages.
- `--no-color` disables ANSI color.

The CLI has no network path and no runtime model dependency. See [`docs/cli.md`](docs/cli.md) for the full contract.

## Cycle 4 research

Cycle 4 separates planning from scoring and keeps transform selection detector-blind and watermark-key-blind.

The main additions are:

- exact post-retokenization root-observation destruction scheduling;
- deterministic replay and content-addressed plan identities;
- a larger visible candidate pool for development experiments;
- pairwise completion after single-candidate saturation in scheduler v2;
- raw, NFKC, Cf-strip, and combined sanitizer robustness reporting;
- explicit quarantine of U+200C as diagnostic-only evidence.

The formal exact-survival confirmation freezes three independent corpora, validates cross-corpus disjointness, scores the paired plans under the inherited detector threshold, and aggregates only after the scoring artifacts are sealed.

The U+200C mechanism is not promoted into release behavior. It can strongly perturb raw tokenization, but stripping Unicode format characters can restore the evaluated detector behavior. It remains useful as a diagnostic upper bound rather than a durable product mechanism.

## Cycle 6 development status

Cycle 6 reached **0 of 16 detected** on the frozen seed-720000 development corpus with the unchanged `0.5570987654320988` threshold and the raw, NFKC, Cf-strip, and combined sanitizer arms. The timestamp-independent corpus content hash is `b114cf4d869c5a5d78ac52855a1a480b1f0e605137aee2cb269062880fcc22d3`; the stable scored-result hash is `73f44b173d7ec55ea80e7d2e9a46b7ea70d8b32682f465dc66643387d99aa8b6`.

This is detector-endpoint development evidence, not geometry zero and not a release claim. Surviving original observations remain in every output. The attack also relies on visible repeated ASCII spaces: NFKC and Cf stripping preserve them, but repeated-space canonicalization removes the mechanism and human fidelity review is still pending.

The Cycle 6 formal-confirmation harness is preregistered for three new 64-sample corpora with matched transformed-unwatermarked controls. Sealed detector scoring remains blocked until the full all-16 blind B14 fidelity packet receives independent human adjudication and its audit hash is bound into the confirmation contract.

## Reproduce the research environment

Install the development package and pinned smoke dependencies:

```text
python -m pip install -e ".[dev]"
python -m pip install -r requirements-smoke.txt
```

Run the ordinary test suite:

```text
python -m pytest
```

The repository's GitHub Actions additionally run package installation checks, frozen research gates, TinyDev/MidDev evidence workflows, the Cycle 4 exact-survival confirmation workflow, and the fidelity-gated Cycle 6 sealed-confirmation harness.

## Release engineering

v0.2.0 builds one wheel and one source distribution and verifies both on Linux, macOS, and Windows before publication. The release workflow also runs `twine check`, verifies the installed console commands, generates SHA-256 checksums for the built artifacts, and refuses to publish a tag whose name does not match the package version.

GitHub Release publication happens only from an immutable `v*` tag after the package matrix succeeds.

See [`docs/release.md`](docs/release.md) for the release sequence.

## Historical evidence

Frozen contracts, evidence, and historical release-readiness artifacts under `specs/` are intentionally immutable. A new release does not rewrite earlier experiment contracts or reinterpret old measurements.

The v0.1.0 release-readiness baseline remains at:

`specs/fuckmark-v0.1.0-release-readiness-baseline.json`

Cycle 4 confirmation contracts and research notes remain separately versioned under `specs/` so old results can be replayed without depending on the current README.

## Project layout

- `fuckmark/` — library, adapters, transforms, schedulers, evidence and experiment tooling.
- `tests/` — regression, invariant, replay, packaging, detector, and workflow-support tests.
- `specs/` — frozen research contracts and evidence records.
- `docs/` — current CLI, installation, and release documentation.
- `.github/workflows/` — CI, release engineering, and research evidence workflows.

## Links

- Website: [mark.q1z.org](https://mark.q1z.org)
- Repository: [github.com/byte271/FuckMark](https://github.com/byte271/FuckMark)
- Issues: [github.com/byte271/FuckMark/issues](https://github.com/byte271/FuckMark/issues)

## License

MIT. See [`LICENSE`](LICENSE).
