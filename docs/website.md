# Website and public installer copy

This file is the controlled source for [mark.q1z.org](https://mark.q1z.org) and the `https://d.q1z.org/mark` endpoints. Repository CI cannot update those hosts. The live HTML and User-Agent-specific PowerShell response must match this page after each release.

Do not pipe `https://d.q1z.org/mark` into a shell. Do not invoke that URL with `iex`. Those commands are disallowed.

## Lead with the browser tool, then the research demo

Deploy these static files (repository CI cannot push them; copy after each release):

| Repo file | Public URL |
| --- | --- |
| [`mark.html`](mark.html) | `https://mark.q1z.org/mark.html` (browser tool) |
| [`scan.html`](scan.html) + [`scan.js`](scan.js) | `https://mark.q1z.org/scan.html` (hidden-Unicode reveal; deploy both files) |
| [`rec.html`](rec.html) | gate that waits for `go.txt`, then opens `mark.html?demo=1` |
| [`demo.html`](demo.html) | `https://mark.q1z.org/demo.html` (research / CLI samples) |

### `mark.html` (product paste UI)

On **Remove marks** it runs the same closed-set FuckMark insertion scan as `fuckmark --detect` (U+034F, U+FE00, C0/C1, U+20DD, U+13430-U+13438, U+FFF9-U+FFFB).

- Hit: strip those insertions, copy the cleaned text, keep visible words.
- Miss: show the English no-watermark card and the contact form that mails `Fhelp@q1z.org`.

Do not strip emoji variation selectors, ZWJ, or other non-approved characters. Do not query GPT-2, SynthID, or any remote detector. Icon scripts may load from a CDN.

Local beginners can run `fuckmark web` after install. That serves the same `mark.html` tool from the package (`fuckmark/webui/mark.html`, kept identical to `docs/mark.html`) on `http://127.0.0.1:8765/mark.html`, plus a local Python API:

- `GET /api/health` reports `backend: "python"`
- `POST /api/remove-marks` with `{ "text": "..." }` calls `detect_fuckmark_insertions` and `project_visible_v1`
- Local-only extras on `fuckmark web`: `POST /api/scan`, `POST /api/guard`, `POST /api/normalize`, and `/scan.html`

The page uses that API when the local server is up. Static `https://mark.q1z.org/mark.html` and `file://` have no Python process, so those deploys keep the in-browser scan.

### `scan.html` (hidden-Unicode reveal)

Static, JS-first. Paste text or open a file; the page classifies hidden characters with `fuckmark-hidden-scan-v1` (`scan.js`, the same port as the editor extension). Language (`auto`, JavaScript/C-like, Python, SQL, HTML) selects comment syntax so Trojan Source commenting-out and stretched-string encodings rank `critical`. Copy uses the security category set. **Fix Trojan Source** strips only bidirectional controls.

Deploy `scan.html` and `scan.js` next to each other. `file://` works. Under `fuckmark web`, an optional checkbox uses `POST /api/scan` on the local Python engine; text still does not leave the machine. Do not embed raw hidden characters in the HTML file; examples are built with `String.fromCodePoint`.

### `demo.html` (research walkthrough)

Keep it a static file that works from `file://` with baked CLI samples. The live page must show:

- character differences for fixed samples (U+034F / U+FE00 plus C0/C1 / Me / Cf / annotation residuals)
- processed vs not processed, reason, insertions, sites, `last_index`, capped
- local closed-set FuckMark insertion scan on visitor paste (not GPT-2 / SynthID)
- Mn-strip / default-ignorable strip leaving control residuals (source not restored; four-layer restore census 0/192)
- frozen Gate v2 numbers with GPT-2 / 64-token / historical mark-only scope

If none are found, the demo offers contact at `Fhelp@q1z.org`. Do not present demo numbers as a guarantee for arbitrary user text.

Homepage copy should link `mark.html` (tool), `scan.html` (hidden Unicode), and `demo.html` (evidence) before install instructions.

## What the product does

FuckMark inserts U+034F or U+FE00, a C0/C1 control, enclosing Me (U+20DD), a cycling Egyptian hieroglyph format control (U+13430-U+13438), and a cycling interlinear annotation control (U+FFF9-U+FFFB) into eligible Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji grapheme clusters. Visible projection stays identical; Me may decorate glyphs. v0.4.1 (this tree) already inserts those characters. Accented Latin, Han, and emoji-only inputs are processed.

It is not a general watermark remover.

## Honest limits on the homepage

1. Live five-layer mix does not restore under Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, Mn then Me then UnicodeSanitizer then frozen Cf-strip, or the required sanitizer bundle. Frozen Gate v2 confirmation is the historical mark-only arm (188/192 after Mn/DI strip).
2. Latin, Greek, Cyrillic, Han, Kana, Hangul syllables, and emoji are processed. Inputs with no eligible letter or emoji sites stay unchanged with exit 0. That is not a completed transformation.
3. Frozen 0/192 results are GPT-2 / SynthID confirmation on 64-token samples. They do not answer whether text is useful on a user's platform and are not a general AI-detector rate reduction.
4. Install remains Python 3.11+ and a CLI; the static demo is the no-install path.

## Install (Linux / macOS)

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fuckmark --version
```

## Install (Windows)

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\fuckmark.exe --version
```

Tagged wheel: GitHub Release `SHA256SUMS.txt` only. Last published wheel: v0.4.0. Source tree: 0.4.1.

## Results to show, with boundaries

Gate v2 confirmation (GPT-2 / SynthID, 64-token samples, historical mark-only): unmodified watermarked **188/192**; transformed after required sanitizers **0/192**; visible text **192/192**. Historical triple-layer exploratory rescore of frozen Gate v2 watermarked sources (seeds 1200000, 1210000, 1220000): **0/192** after Mn then UnicodeSanitizer and after required-bundle then UnicodeSanitizer. Live four-layer restore census on those same sources: **0/192** restore under Mn then Me then UnicodeSanitizer. Cap 4096 letter sites. See [`limits.md`](limits.md) and [`demo.html`](demo.html).
