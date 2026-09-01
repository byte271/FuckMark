# Changelog

## Unreleased

- Defensive hidden-Unicode scanner and cleaner (`fuckmark-hidden-scan-v1`). `fuckmark --scan` audits any text for hidden or suspicious Unicode without changing it; `fuckmark --clean` strips it while keeping the visible text. Coverage is general, not FuckMark-only: bidirectional controls (Trojan Source, CVE-2021-42574), zero-width and invisible spacing, Unicode tag characters (hidden-text / prompt-injection smuggling), variation selectors, enclosing marks, deprecated interlinear controls, other `Cf` format controls, C0/C1 controls, private-use codepoints, and noncharacters. Tab, newline, carriage return, and space are never flagged, and ordinary combining accents (`Mn`) are left alone.
- `--scan` prints a human report by default, a machine line with `-q`, and a `fuckmark-scan ...` status line to stderr with `--status`. `--clean` removes every flagged category (so it reverses a FuckMark mix back to the visible text) and reports the count removed. `--detect`, `--scan`, and `--clean` are mutually exclusive; neither `--scan` nor `--clean` combines with `--visible`.
- `fuckmark web` serves the same engine at `POST /api/scan`. New Python API: `scan_hidden_characters`, `clean_hidden_characters`, `classify_hidden_codepoint`, `scan_dict`, `scan_human_report`, `scan_machine_line`, `ScanResult`, and `HiddenFinding` (exported from `fuckmark` and `fuckmark.product`).
- Frozen confirmation files, hashes, mix mechanisms, and the published wheel are unchanged. Package version stays 0.4.1.

## v0.4.1

Audit findings D01-D16, E01-E04, L01-L06, P01, and G01 against `d7dc98b7ee99fc46b767c93444a9f051fdbea2ba`. Do not retag v0.4.0. Frozen confirmation files and their SHA-256 sums are unchanged.

- Live mix is five-layer (`u034f-ufe00-cc-me-cf-ia-letter-alt-v1`, `release-cli-v12`): each eligible grapheme cluster gets U+034F or U+FE00, a C0/C1 control, enclosing Me (U+20DD), a cycling Egyptian hieroglyph format control (U+13430-U+13438), and a cycling interlinear annotation control (U+FFF9-U+FFFB). UnicodeSanitizer turns those annotation controls into spaces, so Mn then Me then UnicodeSanitizer then frozen Cf-strip no longer restores the source. Sites are Latin, Greek, Cyrillic, Han, Kana, Hangul syllables, and emoji. NFD Latin is marked after the combining sequence so normalization does not split the cluster. Visible projection stays identical. Mn-strip, default-ignorable strip, UnicodeSanitizer orderings, Mn then Me then UnicodeSanitizer, and the required sanitizer bundle no longer restore the source. Chromium pre-pixel probes reject the live Me-layer mix; historical mark-only remains pixel-equal where measured. The Egyptian Cf cycle stays the Unicode 14 assigned range U+13430-U+13438.
- Exploratory restore census of frozen Gate v2 watermarked sources on seeds 1200000, 1210000, and 1220000 (n=192, detector not run): four-layer **0/192** restore under Mn then Me then UnicodeSanitizer, and **0/192** match to `UnicodeSanitizer(source)`, with Cf residual on every row. Historical triple-layer under that same path matches `UnicodeSanitizer(source)` **192/192**. Confirmation artifacts were not rewritten.
- Exploratory GPT-2 / SynthID rescore of those same frozen sources remains historical triple-layer evidence (`u034f-ufe00-cc-me-letter-alt-v1`): **0/192** on raw, Mn-strip, DI-strip, UnicodeSanitizer, Mn then US, DI then US, US then Mn, required-bundle, and bundle then US. Historical dual-layer / mark-only under Mn then US returns to **182/192** detections.
- Exploratory DistilGPT2 rescore of frozen seed 1090000 watermarked sources (n=16, `HYPOTHESIS`) remains historical triple-layer evidence: identity **16/16**. Historical triple-layer **0/16** after Mn then UnicodeSanitizer and after required-bundle then UnicodeSanitizer. Frozen DistilGPT2 scorecard was not rewritten.
- Latin letters outside ASCII, Han syllables, and emoji-only input are processed. Curly apostrophes stay in the visible text and are reported as `first_unsupported`. Processed letters and emoji are not leftovers. Joining scripts such as Arabic stay unchanged. Site cap is 4096 (five insertions per site).
- `--detect` and the no-install demo scan for FuckMark insertion characters only. A miss prints that no watermark was detected and points to `Fhelp@q1z.org`. That scan is not a general AI-watermark detector.
- Website tool source is now in-repo: `docs/mark.html` (plus `docs/rec.html` gate), packaged as `fuckmark/webui/mark.html`. It uses the same closed-set scan, strips approved insertions on a hit, and on a miss shows an English no-watermark card with mailto `Fhelp@q1z.org`. It no longer strips emoji VS / ZWJ ranges.
- `fuckmark web` serves that local browser tool for beginners who prefer a page over the CLI (`http://127.0.0.1:8765/mark.html`). Detect and strip go through a local Python API (`GET /api/health`, `POST /api/remove-marks`) that calls `detect_fuckmark_insertions` and `project_visible_v1`. Static `mark.q1z.org` has no Python process and keeps the in-browser fallback.
- Product authorization v2 records the five-layer path. Gate v2 confirmation hashes stay historical. The v1 mix publishability report records the historical triple-layer fixture measurements and remains `product_authorized: false`.
- Public copy, installer messages, and this source tree describe carrier insertion. They no longer say the CLI returns text unchanged. `docs/website.md` is the controlled website/installer copy. Do not pipe `https://d.q1z.org/mark` into a shell.
- Package version is 0.4.1. The published v0.4.0 wheel remains the last GitHub Release artifact and does not implement `--text` / `--file`.
- Markdown reference labels may span lines and line endings (LF, CRLF, CR). Definitions may put the destination on the next line and may appear in blockquotes or lists. Multiline inline destinations are protected. HTML tags, HTML entities, and indented code are protected.
- Extensionless relative paths such as `scripts/build`, last-component spaces such as `C:/My final notes.txt` and `C:/Users/Alice/My final notes.txt`, and `ftp://` URIs are protected. `and/or` remains eligible.
- CLI outcomes: stderr always reports processed vs not processed, reason, insertions, sites, `last_index`, `source_length`, and capped unless `-q`, including stream success. Successful transforms note that Mn-strip, default-ignorable strip, UnicodeSanitizer combinations, and Cf-strip after UnicodeSanitizer leave Me/Cc/Cf residuals and spaces. `--status` includes `processed`, `source_length`, and `first_unsupported`, including for `too-large` and internal failure. `--inspect` prints a character-level map. `--detect` scans for approved insertions without transforming. Clipboard partial success is exit 3. Usage errors remain exit 2. Internal transform failure is exit 4. Output is written before clipboard copy. Stdout write failures no longer escape as a traceback.
- Public copy states that frozen GPT-2 / SynthID 0/192 results do not answer platform usefulness and are not a general AI-detector rate reduction.
- No-install demo: `docs/demo.html` (baked CLI samples, character diffs, Mn/DI residual checks, frozen GPT-2 scores, local FuckMark detector). Deploy as `mark.q1z.org/demo.html`. Demo numbers are not a guarantee for user text.
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
