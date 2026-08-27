# Changelog

## v0.4.0 — Product CLI

- Transforms ordinary English ASCII text. Visible words stay exactly the same.
- In a terminal, `fuckmark` opens a paste UI. Finish with `:done`. The result is copied and not printed.
- Pipes, quoted text, files, and `--stdin` write the payload to stdout. `--visible` prints the original visible text. `--copy` copies stream output.
- Unsupported Unicode is returned unchanged. Empty input and invalid UTF-8 fail with an actionable error.
- Confirmed on GPT-2 / SynthID tests: transformed text 0/192 after required sanitizers, exact visible text 192/192. This does not remove every watermark.
- Install from a clone with `python -m pip install .`, or the GitHub Release wheel after checking `SHA256SUMS.txt`.

## v0.3.0

Public CLI left text unchanged (no visible edits). Install and release hardening. Not the current product.

## v0.2.0

Historical contraction CLI. Not the current product.

## v0.1.0

First tagged release.
