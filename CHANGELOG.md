# Changelog

## Unreleased

Audit fixes F01-F07 against `be6ae7645fda8b39d1d308722ac249f519e68de5`. Package version remains 0.4.0. Frozen confirmation files and their SHA-256 sums are unchanged.

- F01: contenteditable rendering sets `textContent`. The 2026-08-26 Chromium contenteditable VERIFIED rows compared blank divs and are not proof of text rendering equivalence. Replacement measurement: `evidence/audit-fixes-2026-08-27/`.
- F02: common relative paths without `./` and Windows paths that use `/` keep exact original bytes.
- F03: Markdown reference labels are protected at uses and definitions. Link checks use reference resolution, not only visible projection.
- F04: file and stdin I/O keep LF, CRLF, CR, mixed endings, and a missing final newline.
- F05: `--text` is literal text. `--file` requires an existing UTF-8 file. Ordinary sentences are not treated as missing files.
- F06: stdin is decoded as strict UTF-8. Invalid bytes exit nonzero with no payload and no clipboard copy.
- F07: letter-mix site selection no longer hashes the whole document per candidate. Compose-time invariant checks remain.

Live mix bytes can differ from frozen `u034f-ufe00-letter-alt-v1` output hashes when a newly protected span is present. Visible projection remains the source. `cycle8-mix-freeze-v1` still pins `letter_mix_source_sha256` to the freeze-time file.

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
