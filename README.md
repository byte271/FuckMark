<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a UTF-8 command that inserts hidden Unicode into ordinary English ASCII text **without changing what you see**.

On confirmation-scale GPT-2 / SynthID tests, transformed text was not flagged, visible words stayed identical, and output was deterministic.

Website: [mark.q1z.org](https://mark.q1z.org) · License: MIT

## Install

Python 3.11 or newer. From this repository:

```text
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fuckmark --version
```

That prints `FuckMark 0.4.0`. The checksummed GitHub Release wheel is published after the immutable `v0.4.0` tag. See [`docs/install.md`](docs/install.md). Do not pipe `https://d.q1z.org/mark` into a shell. Do not retag `v0.3.0`.

## Use

```text
printf 'I do not agree.\n' | fuckmark
fuckmark "I do not agree."
fuckmark notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | fuckmark --visible
```

You still read **I do not agree.** The bytes changed. The visible words did not.

```text
printf 'I do not agree.\n' | fuckmark | python3 -c "import sys; t=sys.stdin.read(); print(len(t.encode()), 'bytes')"
```

`--copy` also puts that output on the clipboard. `fuckmark --help` is enough to start.

## What it guarantees

`VISIBLE(original) == VISIBLE(transformed)`. FuckMark only inserts U+034F and U+FE00 after eligible ASCII letters. It does not contract, paraphrase, homoglyph, or add spaces.

Supported input: tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged. Only UTF-8. URLs, code spans, paths, and similar machine text are left intact.

## Verified results

Gate v2 confirmation (seeds `1200000` / `1210000` / `1220000`, spent):

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** |
| Transformed text after required sanitizers | **0/192** |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after `lm-watermarking` UnicodeSanitizer | **0/192** |
| Carrier-free control after that sanitizer | **182/192** |

Cross-detector transfer (not rescored here): Google synthid-text 30-key GPT-2 transformed text **0/192**. DistilGPT2 n=16 and mean-versus-weighted-mean remain `HYPOTHESIS`.

## Limitations

This does not remove every AI watermark. It is not a claim against unknown, proprietary, or future detectors.

Stripping combining marks or default-ignorable characters restores the source. Those are recorded stress tests, not required product sanitizers. The older v1 mix sanitizer gate stays FAIL.

English ASCII only. Cap 192 insertion sites.

## How it works

Eligible ASCII letters receive an alternating pair of invisible characters (U+034F, then U+FE00). The public command is `fuckmark` / `FuckMark` / `Fuckmark`. The transform is frozen. Older visible-edit catalogs stay out of the release path.

## Research / reproducibility

Detailed protocols, hashes, seed ledgers, and H9-H16 negatives live under [`docs/cycle8/`](docs/cycle8/README.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md). Release process: [`docs/release.md`](docs/release.md).

Do not rerun spent confirmation seeds looking for zero. Do not generate `950000`.

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

Open SynthID research extras: `requirements-smoke.txt` and `python -m pip install -e ".[research]"`.

## License

MIT. See [`LICENSE`](LICENSE).
