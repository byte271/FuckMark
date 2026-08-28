# Website and public installer copy

This file is the controlled source for [mark.q1z.org](https://mark.q1z.org) and the `https://d.q1z.org/mark` endpoints. Repository CI cannot update those hosts. The live HTML and User-Agent-specific PowerShell response must match this page after each release.

Do not pipe `https://d.q1z.org/mark` into a shell. Do not invoke that URL with `iex`. Those commands are disallowed.

## Lead with the no-install demo

Deploy [`demo.html`](demo.html) as `https://mark.q1z.org/demo.html`. Keep it a static file that works from `file://` with baked CLI samples. The live page must show:

- character differences for fixed samples (U+034F / U+FE00 plus C0/C1 residuals)
- processed vs not processed, reason, insertions, sites, `last_index`, capped
- Mn-strip / default-ignorable strip leaving control residuals (source not restored; exploratory dual-layer 0/64)
- frozen Gate v2 numbers with GPT-2 / 64-token / historical mark-only scope

Do not run detectors on visitor paste. Do not present demo numbers as a guarantee for arbitrary user text.

Homepage copy should link the demo before install instructions.

## What the product does

FuckMark inserts U+034F or U+FE00, a C0/C1 control, and enclosing Me (U+20DD) into eligible ASCII letter sites. Visible projection stays identical; Me may decorate glyphs. v0.4.1 (this tree) already inserts those characters. Mixed Unicode with ASCII letters is processed.

It is not a general watermark remover.

## Honest limits on the homepage

1. Live triple-layer mix does not restore under Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, or the required sanitizer bundle (exploratory 0/64). Frozen Gate v2 confirmation is the historical mark-only arm (188/192 after Mn/DI strip).
2. Mixed Unicode with ASCII letters is processed. Inputs with no eligible ASCII letters stay unchanged with exit 0. That is not a completed transformation.
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

Gate v2 confirmation (GPT-2 / SynthID, 64-token samples, historical mark-only): unmodified watermarked **188/192**; transformed after required sanitizers **0/192**; visible text **192/192**. Live triple-layer exploratory rescore of seed 1200000 watermarked sources: **0/64** after Mn then UnicodeSanitizer and after required-bundle then UnicodeSanitizer. Cap 4096 letter sites. See [`limits.md`](limits.md) and [`demo.html`](demo.html).
