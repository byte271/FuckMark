<p align="center">
  <a href="https://mark.q1z.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fuckmark-logo-dark.png">
      <img src="docs/assets/fuckmark-logo.png" alt="FuckMark FM star logo" width="180">
    </picture>
  </a>
</p>

# FuckMark

FuckMark is a UTF-8 command for **Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji text**. It inserts Unicode carriers (U+034F, U+FE00, C0/C1 controls, enclosing Me U+20DD, Egyptian hieroglyph format controls U+13430-U+13438, and interlinear annotation controls U+FFF9-U+FFFB) after those grapheme clusters. Visible projection stays identical; Me may decorate glyphs in some renderers.

It is a constrained research/product CLI with measured SynthID / GPT-2 results. It is **not** a general watermark remover, not a paraphraser, and not a claim against unknown or proprietary detectors.

Website: [mark.q1z.org](https://mark.q1z.org) · License: MIT

## Browser tool (start here if you dislike the CLI)

```text
fuckmark web
```

Opens a local page at `http://127.0.0.1:8765/mark.html`. Paste text in the browser. No other CLI flags required. Use `--no-open` to print the URL only, or `--port 0` to pick a free port.

`fuckmark web` also serves a local Python API. Detect and strip POST to `/api/remove-marks` and run the same engine as `fuckmark --detect`. Opening `mark.html` with `file://` or the static website has no Python process, so those paths keep the in-browser fallback.

- Product paste UI source: [`docs/mark.html`](docs/mark.html) (packaged as `fuckmark/webui/mark.html`) — after deploy: [mark.q1z.org/mark.html](https://mark.q1z.org/mark.html)
- Research demo: [`docs/demo.html`](docs/demo.html) — `file://` works; after deploy: [mark.q1z.org/demo.html](https://mark.q1z.org/demo.html)

`mark.html` runs a local closed-set FuckMark scan, strips approved insertions when found, and on a miss shows an English no-watermark card with contact to `Fhelp@q1z.org`. Under `fuckmark web` that scan is the Python detector; the JS copy is the fallback.

The research demo also includes:

- a local FuckMark detector (same closed-set scan; miss path contacts `Fhelp@q1z.org`)
- character-level differences for fixed CLI samples (U+034F / U+FE00 plus C0/C1 / Me / Cf residuals)
- processed vs not processed, reason, insertions, sites, `last_index`, cap
- Mn-strip / default-ignorable strip leaving control residuals (source not restored)
- frozen Gate v2 detection numbers on the historical mark-only GPT-2 corpus, plus historical triple-layer exploratory rescore and the four-layer restore census

These pages do **not** query GPT-2 or SynthID and do **not** promise the same detection outcome for arbitrary user text.

## Honest limits (read these)

### 1. Combined sanitizer reversal (live five-layer)

Live mix inserts a mark, a C0/C1 control, enclosing Me (U+20DD), a cycling Egyptian hieroglyph format control (U+13430-U+13438), and a cycling interlinear annotation control (U+FFF9-U+FFFB) after each eligible grapheme cluster. Insertions follow NFD combining sequences instead of splitting them. Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, Mn then Me then UnicodeSanitizer then frozen Cf-strip, and the required sanitizer bundle leave Me/Cc/Cf or space residuals, so the source is not restored. UnicodeSanitizer turns the annotation controls into spaces, so Cf-strip after it cannot rebuild the original. Exploratory restore census of frozen Gate v2 watermarked sources on seeds 1200000, 1210000, and 1220000 remains the historical four-layer **0/192** restore under Mn then Me then UnicodeSanitizer. Historical triple-layer under that path matches `UnicodeSanitizer(source)` **192/192**. Historical GPT-2 / SynthID combo stress on the prior triple-layer mix remains **0/192** after Mn then UnicodeSanitizer. Frozen Gate v2 confirmation remains the historical mark-only corpus (**0/192** after required sanitizers, **188/192** after Mn/DI strip).

### 2. Everyday letters and emoji are processed

Latin (including U+00E9), Greek, Cyrillic, Han, Kana, Hangul syllables, and emoji clusters are transformed. Curly apostrophes and other punctuation stay in the visible text and are reported as `first_unsupported`. Processed letters and emoji are not reported in that field. `--status` still reports it. Arabic and other joining scripts are left unchanged so cursive joining is not broken. Inputs with **no** eligible letter or emoji sites stay unchanged with exit 0. Exit 0 means I/O succeeded, not that hidden characters were inserted.

`fuckmark --detect` scans for those same insertion characters without transforming. If none are found, it prints that no FuckMark watermark was detected and how to contact `Fhelp@q1z.org`. That scan is not a general AI-watermark detector.

### 3. Frozen scores are not “AI detector rate reduction”

Primary confirmation used GPT-2 / SynthID with 64-token samples (192 pairs). DistilGPT2 n=16 still used the GPT-2 tokenizer. The product fills up to 4096 eligible letter sites (five insertions per site).

That evidence does **not** answer: “Is this text actually useful on the platform I am using?” Statistical watermarking results on a frozen GPT-2 corpus must not be marketed as a general reduction in AI detection rates. See [`docs/limits.md`](docs/limits.md).

### 4. Install is still a terminal tool

Python 3.11+, venv, and a CLI remain the supported install. The no-install demo above is the path for people who need visible feedback first.

## Who it is for

People who paste or pipe **letters or emoji** and want a local, deterministic, detector-blind insertion that keeps visible text identical.

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

## Scan and clean hidden Unicode (defensive)

FuckMark also works the other way. `--scan` audits any text for hidden or suspicious Unicode and reports it without changing the text. `--clean` strips those characters while keeping the visible text. This is a general audit, not a FuckMark-only scan: it covers bidirectional controls (the [Trojan Source](https://trojansource.codes/) class, CVE-2021-42574), zero-width and invisible spacing, Unicode tag characters used to smuggle hidden text into LLM prompts, variation selectors, enclosing marks, deprecated interlinear controls, other `Cf` format controls, C0/C1 controls, private-use codepoints, and noncharacters.

```text
printf 'if (x != \u202eadmin\u202c) {\n' | .venv/bin/fuckmark --scan
.venv/bin/fuckmark --scan --file suspect.txt
.venv/bin/fuckmark --clean --file suspect.txt -o clean.txt
```

`--scan` prints a human report by default, a machine line with `-q`, and a `fuckmark-scan ...` status line to stderr with `--status`. `--clean` removes every flagged category (including FuckMark's own carriers, so `--clean` reverses a mix back to the visible text) and reports how many characters it removed. The same engine is available in the browser tool via `POST /api/scan`, and in Python through `scan_hidden_characters`, `clean_hidden_characters`, and `classify_hidden_codepoint`.

Whitespace tab, newline, carriage return, and space are never flagged, and ordinary combining accents (`Mn`) are left alone. `--clean` strips emoji zero-width joiners and variation selectors as well, so pass a category subset to `clean_hidden_characters(...)` in Python if you need to keep emoji sequences intact.

## What it guarantees

`VISIBLE(original) == VISIBLE(transformed)` under approved-carrier projection. FuckMark inserts U+034F or U+FE00, a C0/C1 control, U+20DD, a cycling U+13430-U+13438 format control, and a cycling U+FFF9-U+FFFB annotation control after eligible letter and emoji grapheme clusters. It does not contract, paraphrase, homoglyph, or add spaces. Transformation selection does not use detectors or watermark keys.

Letter and emoji sites are processed in mixed-Unicode input. Only UTF-8. Inputs with no eligible letter or emoji sites, or that already contain approved carriers, stay unchanged with exit 0 and a stderr reason. That status means I/O succeeded, not that hidden characters were inserted or that a watermark was removed.

Machine text is left intact when recognized: fenced/inline/indented code, HTML tags and entities, markdown destinations and reference labels (including multiline and container forms), URLs including `ftp://`, emails, and paths such as `src/main.py`, `scripts/build`, `C:/My final notes.txt`, and `C:/Users/Alice/My final notes.txt`. Ambiguous prose such as `and/or` stays eligible.

## Frozen GPT-2 / SynthID confirmation (not a product guarantee)

| Check | Result |
| --- | --- |
| Unmodified watermarked text still detected | **188/192** (frozen mark-only corpus) |
| Transformed text after required sanitizers | **0/192** (frozen mark-only corpus) |
| Transformed text after Mn-strip / DI-strip | **188/192** on frozen mark-only; historical triple-layer exploratory **0/192** |
| Transformed text after Mn then UnicodeSanitizer | Historical dual-layer **182/192**; historical triple-layer exploratory **0/192** |
| Transformed text after Mn then Me then UnicodeSanitizer | Four-layer restore census **0/192** (Cf residual; detector not run) |
| Transformed text after Mn then Me then UnicodeSanitizer then Cf-strip | Live five-layer leaves spaces (closed-set remainder is Cf-strip before UnicodeSanitizer) |
| Transformed unwatermarked text | **0/192** |
| Exact visible text | **192/192** |
| Transformed text after UnicodeSanitizer | **0/192** |

Google synthid-text 30-key GPT-2 transformed text: **0/192**. DistilGPT2 combo stress on frozen second-model watermarked sources: historical triple-layer **0/16** after Mn then UnicodeSanitizer (`HYPOTHESIS`).

These numbers are frozen Gate v2 confirmation on GPT-2 / SynthID, 64-token samples, threshold and sanitizer paths as recorded. They are not a universal zero-rate guarantee and are not “AI detector rate reduction” for arbitrary platforms. See [`docs/limits.md`](docs/limits.md) and the [no-install demo](docs/demo.html).

## Limitations

Live five-layer mix does not restore under Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, Mn then Me then UnicodeSanitizer then frozen Cf-strip, or the required sanitizer bundle. Historical four-layer restore census is **0/192** under Mn then Me then UnicodeSanitizer on frozen Gate v2 watermarked sources from seeds 1200000, 1210000, and 1220000. Frozen Gate v2 confirmation is still the historical mark-only arm (**188/192** after Mn/DI strip).

Insertion stops after the first 4096 eligible letter sites (five insertions per site). A longer document is unchanged after that point.

Primary evidence uses GPT-2-generated 64-token samples and GPT-2 BPE. DistilGPT2 still uses that tokenizer family. This is not evidence against generic AI-authorship classifiers, unknown proprietary detectors, every SynthID deployment, or C2PA.

Hidden characters change raw substring search, some editors, and GPT-2 token counts (about 8.9x on the stored Gate v2 watermarked set). Downstream software does not automatically call `visible_contains()`.

Cap 4096 letter sites. See [`docs/limits.md`](docs/limits.md).

Live five-layer mix is Chromium pre-pixel `REJECTED` because enclosing Me (U+20DD) changes glyphs. Historical mark-only mix remains pixel-equal where measured. Older Chromium `contenteditable` VERIFIED rows from 2026-08-26 used a blank-div measurement bug and are not proof of rendering equivalence. Safari/WebKit/terminal pixels remain UNKNOWN. Viewport screenshots cannot prove whole-document equality.

## How it works

Eligible Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji clusters receive an alternating mark (U+034F, then U+FE00), a cycling C0/C1 control, enclosing Me (U+20DD), a cycling Egyptian hieroglyph format control (U+13430-U+13438), and a cycling interlinear annotation control (U+FFF9-U+FFFB). The public command is `fuckmark` / `FuckMark` / `Fuckmark`.

## Research

Frozen evidence, hashes, and protocols: [`docs/research.md`](docs/research.md). Product contract: [`docs/product-contract.md`](docs/product-contract.md). CLI: [`docs/cli.md`](docs/cli.md). Limits matrix: [`docs/limits.md`](docs/limits.md). Demo: [`docs/demo.html`](docs/demo.html).

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
