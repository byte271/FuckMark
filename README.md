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

That prints `FuckMark 0.4.0`. v0.4.0 wheel SHA-256: `5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f`. See [`docs/install.md`](docs/install.md). Do not pipe `https://d.q1z.org/mark` into a shell.

## Use

```text
fuckmark
```

Paste or type text, then a line that is only `:done`. The result is copied to the clipboard. You still read the same words; the hidden payload is not printed.

```text
printf 'I do not agree.\n' | fuckmark
fuckmark --text "I do not agree."
fuckmark --text "I agree. You are right"
fuckmark --file notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | fuckmark --visible
```

Pipes and files write the payload to stdout. `fuckmark --help` is enough to start.

## What it guarantees

`VISIBLE(original) == VISIBLE(transformed)`. FuckMark only inserts U+034F and U+FE00 after eligible ASCII letters. It does not contract, paraphrase, homoglyph, or add spaces.

Supported input: tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged with exit 0. That status means I/O succeeded, not that hidden characters were inserted. Only UTF-8. URLs, code spans, paths (including `src/main.py` and `C:/Users/...`), Markdown reference labels, and similar machine text are left intact.

## Verified results

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** |
| Transformed text after required sanitizers | **0/192** |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after UnicodeSanitizer | **0/192** |

Google synthid-text 30-key GPT-2 transformed text: **0/192**.

## Limitations

This does not remove every AI watermark. It is not a claim against unknown, proprietary, or future detectors.

Stripping combining marks or default-ignorable characters restores the source. On the frozen Gate v2 confirmation set, mix plus those two stress sanitizers restored detection to 188/192. The stored 0/192 result applies only to the specified detectors, threshold, samples, and required sanitizer paths.

Primary confirmation uses 64 generated tokens per sample. Insertion stops after the first 192 eligible letter sites, so the tail of a long document is unchanged. That coverage limit is not a measured long-document detection result.

English ASCII only. Valid Unicode outside that domain, including accented letters, is returned unchanged with exit 0.

Equal visible projection is not the same as equal behavior in other software. Raw codepoint search, Markdown reference matching, and exact byte paths can still fail if hidden characters remain. Historical Chromium `contenteditable` VERIFIED rows from 2026-08-26 used a blank-div measurement bug and are not proof of rendering equivalence. Safari/WebKit and terminal-pixel results remain UNKNOWN.

Cap 192 insertion sites.

## How it works

Eligible ASCII letters receive an alternating pair of invisible characters (U+034F, then U+FE00). The public command is `fuckmark` / `FuckMark` / `Fuckmark`.

## Research

Frozen evidence, hashes, and protocols: [`docs/research.md`](docs/research.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md).

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
