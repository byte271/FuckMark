<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a UTF-8 command for **English text with eligible ASCII letters**. It inserts Unicode carriers (U+034F, U+FE00, C0/C1 controls, enclosing Me U+20DD, and Egyptian hieroglyph format controls U+13430-U+1343F) after those letters. Visible projection stays identical; Me may decorate glyphs in some renderers.

It is a constrained research/product CLI with measured SynthID / GPT-2 results. It is **not** a general watermark remover, not a paraphraser, and not a claim against unknown or proprietary detectors.

Website: [mark.q1z.org](https://mark.q1z.org) · License: MIT

## No-install demo (start here)

Open [`docs/demo.html`](docs/demo.html) in a browser. `file://` works; no Python install required. After website deploy: [mark.q1z.org/demo.html](https://mark.q1z.org/demo.html).

The demo shows:

- character-level differences for fixed CLI samples (U+034F / U+FE00 plus C0/C1 / Me / Cf residuals)
- processed vs not processed, reason, insertions, sites, `last_index`, cap
- Mn-strip / default-ignorable strip leaving control residuals (source not restored)
- frozen Gate v2 detection numbers on the historical mark-only GPT-2 corpus, plus historical triple-layer exploratory rescore and the four-layer restore census

It does **not** score your paste against a detector and does **not** promise the same detection outcome for arbitrary user text.

## Honest limits (read these)

### 1. Combined sanitizer reversal (live four-layer)

Live mix inserts a mark, a C0/C1 control, enclosing Me (U+20DD), and a cycling Egyptian hieroglyph format control (U+13430-U+1343F) at each eligible ASCII letter. Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, and the required sanitizer bundle leave Me/Cc/Cf residuals, so the source is not restored. Frozen Cf-strip still removes the Cf layer. Exploratory restore census of frozen Gate v2 watermarked sources on seeds 1200000, 1210000, and 1220000: four-layer **0/192** restore under Mn then Me then UnicodeSanitizer, and **0/192** match to `UnicodeSanitizer(source)`. Historical triple-layer under that path matches `UnicodeSanitizer(source)` **192/192**. Historical GPT-2 / SynthID combo stress on the prior triple-layer mix remains **0/192** after Mn then UnicodeSanitizer. Frozen Gate v2 confirmation remains the historical mark-only corpus (**0/192** after required sanitizers, **188/192** after Mn/DI strip).

### 2. Mixed Unicode with ASCII letters is processed

ASCII letter sites are transformed even when the surrounding text contains other Unicode (curly apostrophes, accents, emoji). The non-ASCII stays in the visible text. `--status` still reports `first_unsupported`. Inputs with **no** eligible ASCII letters stay unchanged with exit 0. Exit 0 means I/O succeeded, not that hidden characters were inserted.

### 3. Frozen scores are not “AI detector rate reduction”

Primary confirmation used GPT-2 / SynthID with 64-token samples (192 pairs). DistilGPT2 n=16 still used the GPT-2 tokenizer. The product fills up to 4096 eligible letter sites (four insertions per site).

That evidence does **not** answer: “Is this text actually useful on the platform I am using?” Statistical watermarking results on a frozen GPT-2 corpus must not be marketed as a general reduction in AI detection rates. See [`docs/limits.md`](docs/limits.md).

### 4. Install is still a terminal tool

Python 3.11+, venv, and a CLI remain the supported install. The no-install demo above is the path for people who need visible feedback first.

## Who it is for

People who paste or pipe **English text with ASCII letters** and want a local, deterministic, detector-blind insertion that keeps visible text identical.

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

Paste or type text, then a line that is only `:done`. The result is copied to the clipboard. Stderr always reports processed vs not processed, reason, insertions, sites, `last_index`, `source_length`, and cap unless `-q`. Successful runs note that Mn-strip and default-ignorable strip leave control residuals.

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

`VISIBLE(original) == VISIBLE(transformed)` under approved-carrier projection. FuckMark inserts U+034F or U+FE00, a C0/C1 control, U+20DD, and a cycling U+13430-U+1343F format control after eligible ASCII letters. It does not contract, paraphrase, homoglyph, or add spaces. Transformation selection does not use detectors or watermark keys.

ASCII letter sites are processed in mixed-Unicode input. Only UTF-8. Inputs with no eligible ASCII letters, or that already contain approved carriers, stay unchanged with exit 0 and a stderr reason. That status means I/O succeeded, not that hidden characters were inserted or that a watermark was removed.

Machine text is left intact when recognized: fenced/inline/indented code, HTML tags and entities, markdown destinations and reference labels (including multiline and container forms), URLs including `ftp://`, emails, and paths such as `src/main.py`, `scripts/build`, `C:/My final notes.txt`, and `C:/Users/Alice/My final notes.txt`. Ambiguous prose such as `and/or` stays eligible.

## Frozen GPT-2 / SynthID confirmation (not a product guarantee)

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** (frozen mark-only corpus) |
| Transformed text after required sanitizers | **0/192** (frozen mark-only corpus) |
| Transformed text after Mn-strip / DI-strip | **188/192** on frozen mark-only; historical triple-layer exploratory **0/192** |
| Transformed text after Mn then UnicodeSanitizer | Historical dual-layer **182/192**; historical triple-layer exploratory **0/192** |
| Transformed text after Mn then Me then UnicodeSanitizer | Four-layer restore census **0/192** (Cf residual; detector not run) |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after UnicodeSanitizer | **0/192** |

Google synthid-text 30-key GPT-2 transformed text: **0/192**. DistilGPT2 combo stress on frozen second-model watermarked sources: historical triple-layer **0/16** after Mn then UnicodeSanitizer (`HYPOTHESIS`).

These numbers are frozen Gate v2 confirmation on GPT-2 / SynthID, 64-token samples, threshold and sanitizer paths as recorded. They are not a universal zero-rate guarantee and are not “AI detector rate reduction” for arbitrary platforms. See [`docs/limits.md`](docs/limits.md) and the [no-install demo](docs/demo.html).

## Limitations

Live four-layer mix does not restore under Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, or the required sanitizer bundle (restore census **0/192** on frozen Gate v2 watermarked sources from seeds 1200000, 1210000, and 1220000). Frozen Gate v2 confirmation is still the historical mark-only arm (**188/192** after Mn/DI strip).

Insertion stops after the first 4096 eligible letter sites (four insertions per site). A longer document is unchanged after that point.

Primary evidence uses GPT-2-generated 64-token samples and GPT-2 BPE. DistilGPT2 still uses that tokenizer family. This is not evidence against generic AI-authorship classifiers, unknown proprietary detectors, every SynthID deployment, or C2PA.

Hidden characters change raw substring search, some editors, and GPT-2 token counts (about 8.9x on the stored Gate v2 watermarked set). Downstream software does not automatically call `visible_contains()`.

Cap 4096 letter sites. See [`docs/limits.md`](docs/limits.md).

Live four-layer mix is Chromium pre-pixel `REJECTED` because enclosing Me (U+20DD) changes glyphs. Historical mark-only mix remains pixel-equal where measured. Older Chromium `contenteditable` VERIFIED rows from 2026-08-26 used a blank-div measurement bug and are not proof of rendering equivalence. Safari/WebKit/terminal pixels remain UNKNOWN. Viewport screenshots cannot prove whole-document equality.

## How it works

Eligible ASCII letters receive an alternating mark (U+034F, then U+FE00), a cycling C0/C1 control, enclosing Me (U+20DD), and a cycling Egyptian hieroglyph format control (U+13430-U+1343F). The public command is `fuckmark` / `FuckMark` / `Fuckmark`.

## Research

Frozen evidence, hashes, and protocols: [`docs/research.md`](docs/research.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md). Limits matrix: [`docs/limits.md`](docs/limits.md). Demo: [`docs/demo.html`](docs/demo.html).

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
