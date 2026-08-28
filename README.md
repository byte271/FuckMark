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

## No-install demo (start here)

Open [`docs/demo.html`](docs/demo.html) in a browser. `file://` works; no Python install required. After website deploy: [mark.q1z.org/demo.html](https://mark.q1z.org/demo.html).

The demo shows:

- character-level differences for fixed CLI samples (U+034F / U+FE00)
- processed vs not processed, reason, insertions, sites, `last_index`, cap
- Mn-strip / default-ignorable strip restoring the source
- frozen Gate v2 detection numbers on the fixed GPT-2 corpus

It does **not** score your paste against a detector and does **not** promise the same detection outcome for arbitrary user text.

## Honest limits (read these)

### 1. Sanitizer reversal

Insertion-only means clearing combining marks or default-ignorable characters restores the original text. On the frozen Gate v2 set: **0/192** after required sanitizers, then **188/192** again after Mn-strip or default-ignorable strip. That is a designed limitation, not a tuning gap.

### 2. Unsupported input must look like failure to process

Supported code points: tab, CR, LF, and ASCII space through tilde. Chinese characters, emoji, accents, and curly apostrophes (U+2019) cause the **whole** input to be returned unchanged with exit 0. Exit 0 means I/O succeeded, not that hidden characters were inserted.

Example: `I don't agree.` with a curly apostrophe is **not processed**. Use `--status` or `--inspect`. The paste UI and stderr say `not processed` with the first unsupported code point.

### 3. Frozen scores are not “AI detector rate reduction”

Primary confirmation used GPT-2 / SynthID with 64-token samples (192 pairs). DistilGPT2 n=16 still used the GPT-2 tokenizer. The product only fills the first 192 eligible letter sites; long documents stay mostly unchanged after that. See [`docs/limits.md`](docs/limits.md).

### 4. Install is still a terminal tool

Python 3.11+, venv, and a CLI remain the supported install. The no-install demo above is the path for people who need visible feedback first.

## Who it is for

People who paste or pipe **English ASCII** and want a local, deterministic, detector-blind insertion that keeps visible text identical.

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

Paste or type text, then a line that is only `:done`. The result is copied to the clipboard. Status on stderr says whether hidden characters were inserted, with insertions, sites, `last_index`, and cap. Successful interactive runs also remind you that stripping combining marks restores the source.

```text
printf 'I do not agree.\n' | .venv/bin/fuckmark
.venv/bin/fuckmark --text "I do not agree."
.venv/bin/fuckmark --text "I agree. You are right"
.venv/bin/fuckmark --file notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | .venv/bin/fuckmark --visible
printf 'I do not agree.\n' | .venv/bin/fuckmark --status >/tmp/fm.out
printf 'I do not agree.\n' | .venv/bin/fuckmark --inspect >/tmp/fm.out
```

Pipes and files write the payload to stdout. `--visible` prints the original visible text. `--status` writes a machine-readable outcome to stderr. `--inspect` writes a character-level map to stderr. `fuckmark --help` is enough to start.

## What it guarantees

`VISIBLE(original) == VISIBLE(transformed)`. FuckMark only inserts U+034F and U+FE00 after eligible ASCII letters. It does not contract, paraphrase, homoglyph, or add spaces. Transformation selection does not use detectors or watermark keys.

Supported input: tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged with exit 0 and a stderr reason. That status means I/O succeeded, not that hidden characters were inserted or that a watermark was removed. Only UTF-8.

Machine text is left intact when recognized: fenced/inline/indented code, HTML tags and entities, markdown destinations and reference labels (including multiline and container forms), URLs including `ftp://`, emails, and paths such as `src/main.py`, `scripts/build`, `C:/My final notes.txt`, and `C:/Users/Alice/My final notes.txt`. Ambiguous prose such as `and/or` stays eligible.

## Frozen GPT-2 / SynthID confirmation (not a product guarantee)

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** |
| Transformed text after required sanitizers | **0/192** |
| Transformed text after Mn-strip / DI-strip | **188/192** (source restored) |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after UnicodeSanitizer | **0/192** |

Google synthid-text 30-key GPT-2 transformed text: **0/192**.

These numbers are frozen Gate v2 confirmation on GPT-2 / SynthID, 64-token samples, threshold and sanitizer paths as recorded. They are not a universal zero-rate guarantee and are not “AI detector rate reduction” for arbitrary platforms. See [`docs/limits.md`](docs/limits.md) and the [no-install demo](docs/demo.html).

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

Frozen evidence, hashes, and protocols: [`docs/research.md`](docs/research.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md). Limits matrix: [`docs/limits.md`](docs/limits.md). Demo: [`docs/demo.html`](docs/demo.html).

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
