# Website and public installer copy

This file is the controlled source for [mark.q1z.org](https://mark.q1z.org) and the `https://d.q1z.org/mark` endpoints. Repository CI cannot update those hosts. The live HTML and User-Agent-specific PowerShell response must match this page after each release.

Do not pipe `https://d.q1z.org/mark` into a shell. Do not invoke that URL with `iex`. Those commands are disallowed.

## Lead with the no-install demo

Deploy [`demo.html`](demo.html) as `https://mark.q1z.org/demo.html`. Keep it a static file that works from `file://` with baked CLI samples. The live page must show:

- character differences for fixed samples (U+034F / U+FE00)
- processed vs not processed, reason, insertions, sites, `last_index`, capped
- Mn-strip / default-ignorable strip restoring the source (0/192 required-sanitizer success and 188/192 restore failure)
- frozen Gate v2 numbers with GPT-2 / 64-token / 192-site-cap scope

Do not run detectors on visitor paste. Do not present demo numbers as a guarantee for arbitrary user text.

Homepage copy should link the demo before install instructions.

## What the product does

FuckMark inserts U+034F and U+FE00 into ordinary English ASCII text without changing the visible words. v0.4.1 (this tree) already inserts those characters. It does not return the input unchanged until a future release.

It is not a general watermark remover.

## Honest limits on the homepage

1. Clearing combining marks or default-ignorable characters restores the source and restores frozen detections to 188/192.
2. Curly apostrophes, accents, emoji, and other non-ASCII leave the whole input unchanged with exit 0. That is not a completed transformation.
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

Gate v2 confirmation (GPT-2 / SynthID, 64-token samples): unmodified watermarked **188/192**; transformed after required sanitizers **0/192**; visible text **192/192**. Stripping combining marks or default-ignorable characters restores the source and **188/192** detections. English ASCII only. Cap 192 letter sites. See [`limits.md`](limits.md) and [`demo.html`](demo.html).
