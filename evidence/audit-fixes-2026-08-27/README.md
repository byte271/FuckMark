# Audit fix evidence (2026-08-27)

This directory records measurements and invalidations for the F01-F07 audit fixes. It does not rewrite historical evidence files.

Audited baseline commit: `be6ae7645fda8b39d1d308722ac249f519e68de5` (package 0.4.0).

## F01 contenteditable rendering

`cycle8-benchmark-render-v1` assigned `element.value` for every surface, then checked `'value' in element`. On a contenteditable div that assignment created a `value` property, so `textContent` never ran. Screenshots compared two blank divs and stored `VERIFIED`.

Those `chromium_contenteditable` VERIFIED rows are not proof of text rendering equivalence:

- `evidence/cycle8-letter-system-benchmark-2026-08-26/local-system.json`
- `evidence/cycle8-letter-system-benchmark-2026-08-26/scorecard.json`
- `evidence/cycle8-mix-margin-2026-08-26/local-system.json`
- `evidence/cycle8-mix-margin-2026-08-26/scorecard.json`

Those files and their SHA-256 sums are unchanged. `render-v2.json` is the replacement measurement (`cycle8-benchmark-render-v2`).

On this host:

- Chromium: Google Chrome 148.0.7778.96
- Font: DejaVu Sans Mono
- contenteditable AAAA vs BBBB: REJECTED
- contenteditable AAAA vs AAAA: VERIFIED
- contenteditable AAAA vs empty: REJECTED
- textarea has the same positive, negative, and nonempty-vs-empty controls
- Safari/WebKit: UNKNOWN
- terminal pixels: UNKNOWN

An unavailable browser returns UNKNOWN, never VERIFIED.

## F02 and F03 protection

Live `hard_machine_intervals` now protects common relative paths without `./`, Windows paths that use `/`, and Markdown reference labels at uses and definitions. That can change mix output bytes versus the frozen `u034f-ufe00-letter-alt-v1` snapshot.

`cycle8-mix-freeze-v1` remains the historical freeze. Its `letter_mix_source_sha256` is pinned to `b1ceec24e584c0e9e7135ef0c89a3bd249b0bda4a45e07aa7190b1b010ba56d4`, the `letter_mix.py` bytes at freeze time. Live `letter_mix.py` may differ. Frozen confirmation output hashes are not regenerated.

## F07 scan refactor

`letter-mix-scan.json` is a same-host before/after-style observation of the post-fix scanner. It is not a cross-machine performance claim. Final compose-time invariant checks remain.

## L01-L04

These stay product limitations, not silent bug closures. See README and `docs/cli.md`.
