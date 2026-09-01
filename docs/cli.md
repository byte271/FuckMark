# FuckMark CLI

The same command is installed as `fuckmark`, `FuckMark`, and `Fuckmark`.

It inserts hidden Unicode into ordinary letters and emoji. The words on screen do not change.

```text
fuckmark --help
```

## Paste UI

In a terminal, with no file, quoted text, or pipe:

```text
fuckmark
```

```text
FuckMark

Paste or type your text below.
Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji sites are processed.
Other characters stay in the visible text.
Enter :done on a new line when finished.

> I do not agree.
> This can contain multiple lines.
>
> Another paragraph.
> :done

Processing...

✓ Copied to clipboard
FuckMark: processed: inserted 216 hidden characters.
FuckMark: processed=yes reason=transformed insertions=216 sites=54 last_index=... source_length=... capped=no.
FuckMark: Mn-strip, default-ignorable strip, UnicodeSanitizer combinations, and Cf-strip after UnicodeSanitizer leave Me/Cc/Cf residuals and spaces.
```

Blank lines are kept. `:done` ends the session only when it is the entire line. The transformed payload is copied and not printed. Interactive stderr always states processed vs not processed, insertions, sites, `last_index`, `source_length`, and cap.

If clipboard copy fails, nothing is printed. Pipe text instead: `printf 'I do not agree.\n' | fuckmark`. Ctrl+C exits cleanly. EOF without `:done` is an error and copies nothing.

Redirected or piped stdin does not open this UI. It is processed as a stream.

## Stream examples

```text
printf 'I do not agree.\n' | fuckmark
fuckmark --text "I do not agree."
fuckmark --text "I agree. You are right"
fuckmark --text "Version 1.2 works"
fuckmark --text "Use input/output here"
fuckmark --text=-starts-with-hyphen
fuckmark --file notes.txt
fuckmark --file "my notes.txt" -o notes.fm.txt
fuckmark notes.txt
fuckmark notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | fuckmark --copy
printf 'I do not agree.\n' | fuckmark --visible
printf 'I do not agree.\n' | fuckmark --status >/tmp/fm.out
printf 'I do not agree.\n' | fuckmark --inspect >/tmp/fm.out
fuckmark --detect --text "I do not agree."
printf 'paste\n' | fuckmark --detect
fuckmark --scan --file suspect.txt
fuckmark --clean --file suspect.txt -o clean.txt
fuckmark lint src/
fuckmark guard --json < messages.json
fuckmark web
fuckmark --text "I don’t agree." --status
```


Piped or quoted input writes the hidden payload to stdout. `--visible` writes the original visible text. `--copy` also places whatever was written on the clipboard. Stderr always reports processed vs not processed, reason, insertions, sites, `last_index`, `source_length`, and capped unless `-q`. Successful transforms note that Mn-strip, default-ignorable strip, UnicodeSanitizer combinations, and Cf-strip after UnicodeSanitizer leave Me/Cc/Cf residuals and spaces. Use `-q` when a pipe must keep stderr empty.

## Input modes

| Form | Behavior |
| --- | --- |
| `--text TEXT` | Always a literal string. Use this for sentences, decimals, slashes, or text that looks like a path. `--text=-foo` is literal text that starts with a hyphen. |
| `--file FILE` | Always a file. Missing files are errors. Directories are errors. |
| positional operand | If that path exists as a file, it is read. If it looks like a missing path (`notes.txt`, `src/main.py`, `~/mail`, or a slash), it is an error. Otherwise it is literal text. |
| `--stdin` or `-` | Read all of standard input as bytes and decode them as strict UTF-8. |
| no operand, terminal | Paste UI. |
| no operand, pipe | Stream mode. |

`--text`, `--file`, and `--stdin` are mutually exclusive. Quotes group arguments for the shell. They do not switch FuckMark into text mode. If `notes.txt` exists and you want the string `notes.txt`, use `--text notes.txt`.

Existing files are read as UTF-8 bytes with no newline conversion. LF, CRLF, CR, mixed endings, and a missing final newline are preserved. Invalid UTF-8 is rejected: nonzero exit, no stdout payload, no clipboard copy, and no traceback.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print `FuckMark 0.4.1`. |
| `--text TEXT` | Transform TEXT as a literal string. |
| `--file FILE` | Read UTF-8 from FILE. |
| `--stdin` | Read all of standard input. |
| `-o FILE`, `--output FILE` | Write UTF-8 output to FILE. The file is written before any clipboard copy. |
| `--copy` | Also copy the output to the clipboard. The paste UI always copies. |
| `--visible` | Print the visible text (no hidden characters). |
| `--encoding NAME` | Only `utf-8`. `latin-1`, `ascii`, and `cp1252` are rejected. |
| `-q`, `--quiet` | Hide processed/reason/coverage status messages on stderr. |
| `--status` | Write one `fuckmark-status` line to stderr (`result`, `processed`, `insertions`, `sites`, `last_index`, `source_length`, `capped`, `first_unsupported`). |
| `--inspect` | Write a character-level coverage map to stderr. Stdout stays the payload. |
| `--detect` | Scan for FuckMark insertions without transforming. Stdout is the detect report. If none are found, the report includes `Fhelp@q1z.org`. |
| `--scan` | Audit any text for hidden or suspicious Unicode without transforming. Stdout is the scan report (human by default, `fuckmark-scan ...` machine line with `-q`). |
| `--clean` | Strip hidden or suspicious Unicode while keeping the visible text. Stdout is the cleaned payload. Reports the count removed on stderr. |
| `--no-color` | Disable color on stderr. `NO_COLOR` does the same. |

`--detect`, `--scan`, and `--clean` are mutually exclusive. Neither `--scan` nor `--clean` combines with `--visible`.

### Hidden-Unicode scan and clean

`--scan` and `--clean` are the defensive inverse of the mix. The scan is general, not FuckMark-only. Flagged categories: `bidi_control` (Trojan Source, CVE-2021-42574), `zero_width`, `variation_selector`, `tag` (hidden-text / prompt-injection smuggling), `enclosing_mark`, `line_separator`, `deprecated` (interlinear annotation and deprecated format controls), `format` (other `Cf`), `control` (C0/C1), `private_use`, `noncharacter`, and `surrogate`. Tab, newline, carriage return, and space are never flagged; ordinary combining accents (`Mn`) are left alone.

`--clean` removes every flagged category, so it reverses a FuckMark mix back to the visible text. It also removes emoji zero-width joiners and variation selectors; the Python `clean_hidden_characters(text, categories=...)` call accepts a category subset when emoji sequences must be preserved. The browser tool exposes the same engine at `POST /api/scan`.

### `fuckmark guard`

Sanitize text or JSON before it reaches a model. Strips the security category set by default (same as `fuckmark lint`) and can recover Unicode-tag smuggling as `tag_payload` on the receipt. Does not detect semantic prompt injection.

```text
printf 'user text\n' | fuckmark guard
fuckmark guard --json < messages.json
fuckmark guard --refuse --receipt --json < messages.json
```

`--json` walks every string. `--refuse` exits 1 and writes nothing when hidden Unicode is present. `--report` scans without changing the payload. `--receipt` writes the JSON receipt to stderr. Python: `protect()`, `inspect()`, `Guard`, `HiddenTextRefused`. Reference: [`guard.md`](guard.md).

### `fuckmark web`

Open the local browser tool (same UI as `docs/mark.html`). Aimed at beginners who prefer a page over pipes and flags. The server also exposes a Python API: `GET /api/health`, `POST /api/remove-marks`, `POST /api/scan`, and `POST /api/guard` (sanitize text or chat messages before a model call).

```text
fuckmark web
fuckmark web --no-open
fuckmark web --port 9000
```

Default URL: `http://127.0.0.1:8765/mark.html`. Press Ctrl+C to stop the server.

`--non-interactive` is an alias of `--stdin`.

## Supported input

Latin, Greek, Cyrillic, Han, Kana, Hangul syllable, and emoji grapheme clusters are processed. Punctuation such as curly apostrophes stays in the visible text and is reported as `first_unsupported`. Mixed letters and emoji are not leftovers. Exit 0 means I/O succeeded. It does not mean that a transformation occurred or that a watermark was removed. Only UTF-8 files.

Example: `I don` + U+2019 + `t agree.` is processed (`reason=transformed`, `first_unsupported=U+2019@5`). U+00E9-only input is processed and `first_unsupported` is empty. A string with no eligible letter or emoji sites is `unsupported-domain` or `no-eligible-sites`.

`--detect` does not mix. It reports whether approved FuckMark insertions are present. A miss is not proof that some other watermark exists. Contact `Fhelp@q1z.org` if you believe there is a watermark the scan did not find.

Machine spans stay intact: fenced/inline/indented code, HTML tags and entities, markdown destinations (including multiline), markdown reference labels (including multiline, container, and CR line endings), URLs (including `ftp://`), emails, IPs, dates, currency, percents, numbers, POSIX/Windows paths (including `src/main.py`, `scripts/build`, `C:/My final notes.txt`, `C:/Users/Alice/My final notes.txt`), CLI flags. Quote interiors are eligible. Cap 4096 letter sites, five insertions per site. Insertions fill the first 4096 eligible letter or emoji sites and then stop, so the tail of a long document is unchanged.

If the text is already transformed or has no eligible letters, the CLI returns it unchanged and reports that on stderr unless `-q`. `--status` always reports the reason, including for `too-large` and internal failure. Exit 0 still means I/O succeeded, not watermark removal.

Same visible words are not the same as identical Markdown, path, or search behavior in other programs. Reports must not treat visible-projection equality as Markdown or filesystem equality.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | Output was written or copied. Already-transformed text, no eligible sites, and the site cap are reported on stderr. This is not watermark removal. |
| 1 | No input, bad file, invalid UTF-8, unsupported encoding, missing `:done`, input too large, or output could not be written. |
| 2 | Usage error (`argparse`: unknown option or bad flags). Transformation did not run. |
| 3 | Transform I/O succeeded, but clipboard copy failed. Stream modes still write stdout. The paste UI does not print the payload. |
| 4 | Internal transform failure. Source is returned unchanged. Do not treat this as a completed transformation. |
| 130 | Interrupted with Ctrl+C. |

## Clipboard

- macOS: `pbcopy`
- Windows: `clip` (UTF-16)
- Linux: `wl-copy`, then `xclip`, then `xsel`, then `clip.exe`

## Install

See [`install.md`](install.md).
