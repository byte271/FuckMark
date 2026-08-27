<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a deterministic, detector-blind research harness and CLI for disrupting statistical text watermarks.

**Product contract (Priority Zero):** the user-visible text must not change. Product-safe transforms may modify only rigorously validated non-rendering Unicode representation while preserving exact visible projection. Semantic equivalence, "minor" punctuation edits, and extra visible spaces are not product success.

The public CLI currently fail-closes: no product-authorized invisible carrier has been promoted yet, so `FuckMark` returns the original text unchanged rather than applying contractions or other visible edits. That is intentional. Historical visible-edit research remains replayable through explicitly named historical registries.

Cycle 8 U+034F space-carrier x1 is a `PROMISING_DEVELOPMENT` / `HYPOTHESIS`. Tiny 4-pair corpora are 0/12 transformed WM. Scale exploratory seed `930000` is 0/16, 0/32, then **1/64** raw transformed WM. Independent replication seed `940000` is **0/64**. Combined large-N on those two 64-pair corpora is **1/128**. Density seed `960000` n=16 compared space x1 with space plus word-final letter x1: both **1/16** on the same residual row. Do not rewrite those space-x1 residuals as zero.

Cycle 8 U+034F letter-x1 (after ASCII letters, visible-word invariants, quote-interior carriers, detector-blind cap 192) is a stronger `PROMISING_DEVELOPMENT` / `HYPOTHESIS` on the same visible contract. Diagnostic rescore of seen corpora: `930000` n=64 **0/64**, `940000` n=64 **0/64**, `960000` n=16 **0/16**. Independent reserved seed `970000` is **0/16** then **0/64**. Experimental letter-x1 **0/192** = those two seen 64-pair diagnostics plus independent `970000` n=64 (**128/192 seen**, **64/192 independent**).

A later system benchmark reserved seeds `980000` and `990000` before generation and scored letter-x1 versus space-x1 on two new independent 64-pair corpora: letter-x1 **0/128** raw transformed WM (max 0.554066, gap 0.003032 below threshold 0.557099) and space-x1 **1/128** on the same corpora. Visible projection passed on every scored letter row and on 21/21 local fixtures.

Letter-space margin seeds `1000000` and `1010000` were reserved before generation. Combined fresh letter-space is **1/128**; do not rewrite that as zero.

Letter-mix margin seeds `1020000` and `1030000` were reserved before generation. Detector-blind U+034F/U+FE00 letter-alt is fresh **0/128** raw transformed WM (max 0.513691, gap 0.043407) with mix UW **0/128**. Independent scale seeds `1040000` and `1050000` were reserved before generation; combined mix is **0/256** (worst max 0.519522, gap 0.037577). The two-corpus 0/128 scorecard is not rewritten. Letter-x1 on those same corpora is also 0/256 (worst max 0.543903). Chromium mix fixtures were pixel-equal on the measured surfaces. The mix mechanism is frozen as `cycle8-mix-freeze-v1`. One-shot confirmation on seeds `830000` / `840000` / `850000` is **0/192** raw transformed WM, mix UW **0/192**, visible **192/192**, worst max 0.524300 (gap 0.032798). Those seeds are spent. Publishability: software compatibility PASS on the UTF-8 / visible-search product surface; sanitizer FAIL (Mn-strip and default-ignorable-strip still restore mix; assigned-Unicode closed set found no Priority-Zero-safe survivor); cross-detector PASS on Hugging Face nine-key GPT-2 Weighted Mean plus independent DeepMind 30-key GPT-2 mix **0/192**. DistilGPT2 n=16 is `HYPOTHESIS` second-model transfer, not confirmation-scale. Mix is still not product-authorized. Seed `880000` is publicly exposed by closed unmerged PR #98 and is not eligible as unseen validation. See [`docs/cycle8/mix-publishability.md`](docs/cycle8/mix-publishability.md), [`docs/cycle8/mix-freeze.md`](docs/cycle8/mix-freeze.md), [`docs/cycle8/mix-deepmind-transfer.md`](docs/cycle8/mix-deepmind-transfer.md), [`docs/cycle8/mix-second-model-transfer.md`](docs/cycle8/mix-second-model-transfer.md), [`docs/cycle8/letter-mix-margin.md`](docs/cycle8/letter-mix-margin.md), [`docs/cycle8/letter-system-benchmark.md`](docs/cycle8/letter-system-benchmark.md), and [`docs/seeds.md`](docs/seeds.md).

See [`docs/product-contract.md`](docs/product-contract.md) and `specs/fuckmark-user-visible-invariance-v1.contract.json`.

**Current release: v0.3.0**  
Website: [mark.q1z.org](https://mark.q1z.org)  
License: MIT

## What changed in v0.3.0

v0.3.0 is the visible-invariance product release. The public CLI is `release-cli-v4` and returns input text unchanged. Official install uses a tagged GitHub Release wheel plus `SHA256SUMS.txt`. Release Engineering no longer auto-tags, auto-publishes, or deletes merged branches.

The historical `v0.2.0` tag still applies contractions. Do not treat that tag as the current product contract.

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

The 97.40% Cycle 4 result is narrow research evidence, not a universal watermark-removal guarantee, and it is not a product-contract success: those schedulers selected visible-edit candidates.

It applies to the repository's frozen open GPT-2 / Hugging Face SynthID Weighted Mean confirmation configuration, fixed threshold, exact source protocol, and measured corpus. It does not establish proprietary-detector transfer, arbitrary-model transfer, unknown future watermark transfer, or perfect removal.

The public CLI uses only `release_transform_registry()`, which is now the product-visible-invariance registry. That registry currently contains zero authorized carriers. Development schedulers, detector code, experimental search, historical contraction/lexical/syntax rules, Cycle 6 spacing, Cycle 7 durable visible edits, and the quarantined U+200C diagnostic registry are not automatically selected by the command-line product path.

## Install

Python 3.11 or newer is required. Install a **tagged GitHub Release wheel** and check `SHA256SUMS.txt`. Do not pipe `https://d.q1z.org/mark` into a shell.

```text
python3 -m venv .venv
.venv/bin/python -m pip install https://github.com/byte271/FuckMark/releases/download/v0.3.0/fuckmark-0.3.0-py3-none-any.whl
```

v0.3.0 wheel SHA-256: `cb4ee7b6c06d1dde8c612c237df78f68f8364bc74bf469086288e55a2d5c9325`

The installed CLI currently returns input text unchanged. See [`docs/install.md`](docs/install.md) for checksum verification, the in-repo installer, and Windows notes.

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

The current product CLI prints the same visible text. It does not emit `I don't agree.`

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

Cycle 6 reached **0 of 16 detected** on the frozen seed-720000 development corpus with the unchanged `0.5570987654320988` threshold and the raw, NFKC, Cf-strip, and combined sanitizer arms. Formal confirmation froze **NONZERO_RESIDUAL 7/192** transformed-WM detections (2/64 + 2/64 + 3/64) with 0/192 matched transformed-UW detections.

This is detector-endpoint scientific evidence, **PRODUCT_DISQUALIFIED**. The Cycle 6 workhorse inserted repeated ordinary ASCII U+0020 spaces, which are visible spacing changes. Do not treat 7/192, 0/16, or the older 96%+ Cycle 4 figure as proof that FuckMark currently meets the product goal.

## Cycle 7 status

Cycle 7 Stage A/B/C researched collapse-resistant *visible* edits (contractions, hyphenation, punctuation, newlines). Those results remain historically valid as **INSUFFICIENT_EVIDENCE** and are **PRODUCT_DISQUALIFIED**. They must not enter `release_transform_registry()`.

## Cycle 8 status

Cycle 8 is the exact-visible-projection generation. See [`docs/cycle8/README.md`](docs/cycle8/README.md). U+200C remains a diagnostic baseline (stripped by Cf). Combining grapheme joiner U+034F letter-x1 remains a strong visible-invariant development arm (`HYPOTHESIS`): fresh reserved-before-generation **0/128** on seeds `980000`+`990000` with a thin 0.003 gap, plus a separate experimental **0/192** (128 seen + 64 independent). The later U+034F/U+FE00 letter-mix arm is currently stronger on fresh independent corpora: **0/128** on seeds `1020000`+`1030000` with worst score 0.513691 (gap 0.043407), plus independent scale **0/256** including `1040000`+`1050000` with worst score 0.519522 (gap 0.037577). Mix is frozen as `cycle8-mix-freeze-v1` and is not a release mechanism. One-shot confirmation is **0/192**. Publishability still fail-closes: sanitizer weaknesses and cross-detector generalization remain FAIL. Public CLI remains empty.

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

v0.3.0 builds one wheel and one source distribution and verifies both on Linux, macOS, and Windows before publication. The release workflow also runs `twine check`, verifies the installed console commands, generates SHA-256 checksums for the built artifacts, and refuses to publish unless an existing `v*` tag already matches the package version and commit.

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
