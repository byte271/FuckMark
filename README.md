<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a UTF-8 command for **ordinary English ASCII text**. It inserts hidden Unicode (U+034F and U+FE00) after eligible letters **without changing the words you see**.

It is a constrained research/product CLI with measured SynthID / GPT-2 results. It is **not** a general watermark remover, not a paraphraser, and not a claim against unknown or proprietary detectors.

Website: [mark.q1z.org](https://mark.q1z.org) · License: MIT

## Who it is for

People who paste or pipe **English ASCII** (tab, CR, LF, space through tilde) and want a local, deterministic, detector-blind insertion that keeps visible text identical.

If the input contains an emoji, a curly apostrophe, an accent, or any other Unicode, FuckMark copies it unchanged and says so.

## Install from this repository

Python 3.11 or newer. Get the code, then keep using the venv path (or activate the venv). A venv is not on PATH by itself.

Linux / macOS:

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fuckmark --version
printf 'I do not agree.\n' | .venv/bin/fuckmark --visible
printf 'I do not agree.\n' | .venv/bin/fuckmark --status >/tmp/fm.out
```

Windows (PowerShell):

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\fuckmark.exe --version
```

That prints `FuckMark 0.4.1` for this source tree.

Do not pipe `https://d.q1z.org/mark` into a shell. The supported install is a clone or a checksummed GitHub Release wheel. See [`docs/install.md`](docs/install.md) and [`docs/website.md`](docs/website.md).

Last **published** wheel is still **v0.4.0** (SHA-256 `5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f`). That wheel does not implement `--text` / `--file`. Use this 0.4.1 tree or wait for the v0.4.1 GitHub Release. Do not retag v0.4.0.

If clipboard copy fails, pipe instead: `printf 'I do not agree.\n' | .venv/bin/fuckmark`.

## Use

Keep using the venv command from the install step. Examples below assume `.venv/bin/fuckmark` on Unix.

```text
.venv/bin/fuckmark
```

Paste or type text, then a line that is only `:done`. The result is copied to the clipboard. Status on stderr says whether hidden characters were inserted.

```text
printf 'I do not agree.\n' | .venv/bin/fuckmark
.venv/bin/fuckmark --text "I do not agree."
.venv/bin/fuckmark --text "I agree. You are right"
.venv/bin/fuckmark --file notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | .venv/bin/fuckmark --visible
printf 'I do not agree.\n' | .venv/bin/fuckmark --status >/tmp/fm.out
```

Pipes and files write the payload to stdout. `--visible` prints the original visible text. `--status` writes a machine-readable outcome to stderr. `fuckmark --help` is enough to start.

## What it guarantees

`VISIBLE(original) == VISIBLE(transformed)`. FuckMark only inserts U+034F and U+FE00 after eligible ASCII letters. It does not contract, paraphrase, homoglyph, or add spaces. Transformation selection does not use detectors or watermark keys.

Supported input: tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged with exit 0 and a stderr reason. That status means I/O succeeded, not that hidden characters were inserted or that a watermark was removed. Only UTF-8.

Machine text is left intact when recognized: fenced/inline/indented code, HTML tags and entities, markdown destinations and reference labels (including multiline and container forms), URLs including `ftp://`, emails, and paths such as `src/main.py`, `scripts/build`, and `C:/Users/Alice/My final notes.txt`. Ambiguous prose such as `and/or` stays eligible.

## Verified results

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** |
| Transformed text after required sanitizers | **0/192** |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after UnicodeSanitizer | **0/192** |

Google synthid-text 30-key GPT-2 transformed text: **0/192**.

These numbers are frozen Gate v2 confirmation on GPT-2 / SynthID, 64-token samples, threshold and sanitizer paths as recorded. They are not a universal zero-rate guarantee. See [`docs/limits.md`](docs/limits.md).

## Limitations

Stripping combining marks or default-ignorable characters restores the source and the detectable watermark. On the frozen Gate v2 set, those two stress sanitizers restored detection to 188/192. NFC, NFKC, Cf stripping, and whitespace collapse are not that removal step.

English ASCII only. One unsupported character disables transformation of the whole input.

Insertion stops after the first 192 eligible letter sites. A long document is mostly unchanged after that point.

Primary evidence uses GPT-2-generated 64-token samples and GPT-2 BPE. DistilGPT2 still uses that tokenizer family. This is not evidence against generic AI-authorship classifiers, unknown proprietary detectors, every SynthID deployment, or C2PA.

Hidden characters change raw substring search, some editors, and GPT-2 token counts (about 8.9x on the stored Gate v2 watermarked set). Downstream software does not automatically call `visible_contains()`.

Cap 192 insertion sites. See [`docs/limits.md`](docs/limits.md).

Historical Chromium `contenteditable` VERIFIED rows from 2026-08-26 used a blank-div measurement bug and are not proof of rendering equivalence. Replacement controls exist; actual product-payload pixel requalification and Safari/WebKit/terminal pixels remain UNKNOWN. Viewport screenshots cannot prove whole-document equality.

## How it works

Eligible ASCII letters receive an alternating pair of invisible characters (U+034F, then U+FE00). The public command is `fuckmark` / `FuckMark` / `Fuckmark`.

## Research

Frozen evidence, hashes, and protocols: [`docs/research.md`](docs/research.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md). Limits matrix: [`docs/limits.md`](docs/limits.md).

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
