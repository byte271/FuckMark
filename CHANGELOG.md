# Changelog

## v0.4.1

Audit findings D01-D16, E01-E04, L01-L06, P01, and G01 against `d7dc98b7ee99fc46b767c93444a9f051fdbea2ba`. Do not retag v0.4.0. Frozen confirmation files and their SHA-256 sums are unchanged.

- Public copy, installer messages, and this source tree describe carrier insertion. They no longer say the CLI returns text unchanged. `docs/website.md` is the controlled website/installer copy. Do not pipe `https://d.q1z.org/mark` into a shell.
- Package version is 0.4.1. The published v0.4.0 wheel remains the last GitHub Release artifact and does not implement `--text` / `--file`.
- Markdown reference labels may span lines and line endings (LF, CRLF, CR). Definitions may put the destination on the next line and may appear in blockquotes or lists. Multiline inline destinations are protected. HTML tags, HTML entities, and indented code are protected.
- Extensionless relative paths such as `scripts/build`, last-component spaces such as `C:/My final notes.txt` and `C:/Users/Alice/My final notes.txt`, and `ftp://` URIs are protected. `and/or` remains eligible.
- CLI outcomes: stderr reasons and `--status` distinguish transformed, unsupported Unicode, already-transformed, no eligible sites, site-cap, and internal failure. `--status` includes `processed`, `source_length`, and `first_unsupported`, including for `too-large` and internal failure. `--inspect` prints a character-level map. Interactive runs state coverage and sanitizer reversal. Clipboard partial success is exit 3. Usage errors remain exit 2. Internal transform failure is exit 4. Output is written before clipboard copy. Stdout write failures no longer escape as a traceback.
- No-install demo: `docs/demo.html` (baked CLI samples, character diffs, reversal, frozen GPT-2 scores). Deploy as `mark.q1z.org/demo.html`. Demo numbers are not a guarantee for user text.
- Unix installer PATH uses `FUCKMARK_BIN`. Windows `fuckmark.cmd` is ASCII for `cmd.exe`; non-ASCII Python paths use an ASCII `.cmd` trampoline to UTF-8 `fuckmark.ps1`.
- Transfer replay tests compare live output hashes to stored hashes. Documented unwatermarked DeepMind drift is listed; unexplained drift fails.
- Historical Cycle 7 Stage A README checksum mismatch is a CRLF-vs-LF provenance note, not a rewritten README.
- Limits, sanitizer, length, tokenizer, and compatibility matrices: `docs/limits.md`.

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
