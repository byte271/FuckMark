# Changelog

## v0.4.1

Audit findings D01-D16, E01-E04, L01-L06, P01, and G01 against `d7dc98b7ee99fc46b767c93444a9f051fdbea2ba`. Do not retag v0.4.0. Frozen confirmation files and their SHA-256 sums are unchanged.

- Live mix is triple-layer (`u034f-ufe00-cc-me-letter-alt-v1`, `release-cli-v7`): each eligible ASCII letter gets U+034F or U+FE00, a C0/C1 control, and enclosing Me (U+20DD). Visible projection stays identical. Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, and the required sanitizer bundle no longer restore the source. Chromium pre-pixel probes reject the live Me-layer mix; historical mark-only remains pixel-equal where measured.
- Exploratory GPT-2 / SynthID rescore of frozen Gate v2 watermarked sources on seeds 1200000, 1210000, and 1220000 (n=192): triple-layer **0/192** on raw, Mn-strip, DI-strip, UnicodeSanitizer, Mn then US, DI then US, US then Mn, required-bundle, and bundle then US. Historical dual-layer / mark-only under Mn then US returns to **182/192** detections. Confirmation artifacts were not rewritten.
- Exploratory DistilGPT2 rescore of frozen seed 1090000 watermarked sources (n=16, `HYPOTHESIS`): identity **16/16** (scores replay the frozen second-model identity scores). Live triple-layer **0/16** after Mn then UnicodeSanitizer and after required-bundle then UnicodeSanitizer. Historical dual-layer under Mn then UnicodeSanitizer returns to **16/16**. Frozen DistilGPT2 scorecard was not rewritten.
- Mixed Unicode with ASCII letters is processed. Curly apostrophes, accents, and emoji stay in the visible text and are reported as `first_unsupported`. Site cap is 4096 (three insertions per site).
- Product authorization v2 records the triple-layer path. Gate v2 confirmation hashes stay historical. The v1 mix publishability report records stress-strip PASS and remains `product_authorized: false`.
- Public copy, installer messages, and this source tree describe carrier insertion. They no longer say the CLI returns text unchanged. `docs/website.md` is the controlled website/installer copy. Do not pipe `https://d.q1z.org/mark` into a shell.
- Package version is 0.4.1. The published v0.4.0 wheel remains the last GitHub Release artifact and does not implement `--text` / `--file`.
- Markdown reference labels may span lines and line endings (LF, CRLF, CR). Definitions may put the destination on the next line and may appear in blockquotes or lists. Multiline inline destinations are protected. HTML tags, HTML entities, and indented code are protected.
- Extensionless relative paths such as `scripts/build`, last-component spaces such as `C:/My final notes.txt` and `C:/Users/Alice/My final notes.txt`, and `ftp://` URIs are protected. `and/or` remains eligible.
- CLI outcomes: stderr always reports processed vs not processed, reason, insertions, sites, `last_index`, `source_length`, and capped unless `-q`, including stream success. Successful transforms note that Mn-strip and default-ignorable strip leave control residuals. `--status` includes `processed`, `source_length`, and `first_unsupported`, including for `too-large` and internal failure. `--inspect` prints a character-level map. Clipboard partial success is exit 3. Usage errors remain exit 2. Internal transform failure is exit 4. Output is written before clipboard copy. Stdout write failures no longer escape as a traceback.
- Public copy states that frozen GPT-2 / SynthID 0/192 results do not answer platform usefulness and are not a general AI-detector rate reduction.
- No-install demo: `docs/demo.html` (baked CLI samples, character diffs, Mn/DI residual checks, frozen GPT-2 scores). Deploy as `mark.q1z.org/demo.html`. Demo numbers are not a guarantee for user text.
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
