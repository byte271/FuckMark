# Public sanitizer-restore bench

`fuckmark robustness` replays `fuckmark-robustness-bench-v1`: a hashed, model-free
grid of short fixtures times Unicode sanitizer attacks. It answers whether the
live five-layer mix still restores the original source after those attacks.

It does **not** rerun GPT-2, SynthID, or any neural detector. Detector numbers
stay on the sealed Gate v2 confirmation scorecard. This is a restore and
residual-category bench, not a platform-evasion rate.

Protocol: [`specs/fuckmark-robustness-bench-v1.protocol.md`](../specs/fuckmark-robustness-bench-v1.protocol.md).
Vectors (sources as codepoint arrays only):
[`specs/fuckmark-robustness-bench-v1.vectors.json`](../specs/fuckmark-robustness-bench-v1.vectors.json).
Freeze hashes: [`specs/fuckmark-robustness-bench-v1.freeze.json`](../specs/fuckmark-robustness-bench-v1.freeze.json).
Installed wheels load copies from `fuckmark/robustness_data/` that must match
`specs/` after UTF-8 LF newline folding. Before exit 0 the CLI recomputes those
hashes, including the scorecard *file* SHA-256, so editing the scorecard while
leaving its embedded `scorecard_hash` field alone still fails. CRLF checkouts
(Windows `core.autocrlf`) are folded to LF before hashing.

## Command line

```text
fuckmark robustness
fuckmark robustness --json
fuckmark robustness -q
fuckmark robustness --fixture digits --attack identity
fuckmark robustness --json --fixture ascii_prose --attack mn_me_us_cf
```

Default is every public fixture and every frozen attack (180 cells). `--fixture`
and `--attack` are repeatable. `--json` writes the full report to stdout. Human
status goes to stderr. `-q` is silent on success.

A file named `robustness` in the current directory is not read; use
`fuckmark --file robustness` for that.

## What a cell records

For source `S` and attack `A`: mix `M`, then `T = A(M)`.

| Field | Meaning |
| --- | --- |
| `restores_source` | `T == S` |
| `mix_projection_equals_source` | visible projection of `M` equals `S` |
| `projection_equals_source` | visible projection of `T` equals `S` |
| `carrier_detected` | closed-set FuckMark insertion scan of `T` |
| `residual_categories` | `fuckmark-hidden-scan-v1` categories still in `T` |
| `mix_sha256` / `output_sha256` | SHA-256 of UTF-8 `M` and `T` |

Visible projection is `project_visible_v1` (approved carriers removed; Me, Cc,
and Cf residuals remain). UnicodeSanitizer turns interlinear annotation
controls into spaces, so Cf-strip after that path cannot rebuild the original
spacing.

## Frozen outcome

Live measure of the v1 grid:

- 10 fixtures, 18 attacks, 180 cells
- mix visible projection holds on every cell (180/180)
- `digits` has no eligible letter or emoji site, so mix is a no-op and every
  attack restores (18/18)
- mixed letter/emoji fixtures do not restore under the catalog
- `ascii_prose` / `mn_me_us_cf`: restore false, carrier false, projection false
  (spaces from UnicodeSanitizer)

Sealed detector track (hashed, not rerun): Gate v2 confirmation identity
**188/192** detected; mix **0/192** after required sanitizers; visible
**192/192**. Do not rewrite that scorecard.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | Selected cells match the frozen vectors, freeze hashes match the loaded artifacts, and the sealed scorecard hash still matches. |
| 1 | Mix, sanitizer, or freeze-hash drift, or a packaged artifact is missing. |
| 2 | Usage (unknown `--fixture` / `--attack`, or argparse). |

## Python

```text
from fuckmark.robustness import measure_cell, run_robustness_bench

cell = measure_cell("ascii_prose", "mn_strip")
report = run_robustness_bench()
```

`tests/test_robustness.py` binds the freeze hashes and replays every cell.

## Honest limits

This v1 freeze is local and deterministic. It is not a leaderboard of third-party
detectors. A later track may add opt-in adapters; it is not this freeze. Short
public fixtures are not the GPT-2 Gate v2 corpus. Sanitizer restore is not the
same as detector miss, and detector miss on GPT-2 / SynthID is not a general
AI-detector rate.
