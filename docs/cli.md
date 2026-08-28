# FuckMark CLI

The same command is installed as `fuckmark`, `FuckMark`, and `Fuckmark`.

It inserts hidden Unicode into ordinary English ASCII text. The words on screen do not change.

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
English ASCII only. Curly apostrophes, accents, and emoji are not processed.
Enter :done on a new line when finished.

> I do not agree.
> This can contain multiple lines.
>
> Another paragraph.
> :done

Processing...

✓ Copied to clipboard
FuckMark: processed: inserted 54 hidden characters.
FuckMark: processed=yes reason=transformed insertions=54 sites=54 last_index=... source_length=... capped=no.
FuckMark: stripping combining marks or default-ignorable characters restores the source.
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
fuckmark --text "I don’t agree." --status
```


Piped or quoted input writes the hidden payload to stdout. `--visible` writes the original visible text. `--copy` also places whatever was written on the clipboard. Stream mode stays silent on full success unless `--status` or `--inspect`. No-ops and the site cap always report on stderr unless `-q`.

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
| `-q`, `--quiet` | Hide non-essential status messages. |
| `--status` | Write one `fuckmark-status` line to stderr (`result`, `processed`, `insertions`, `sites`, `last_index`, `source_length`, `capped`, `first_unsupported`). |
| `--inspect` | Write a character-level coverage map to stderr. Stdout stays the payload. |
| `--no-color` | Disable color on stderr. `NO_COLOR` does the same. |

`--non-interactive` is an alias of `--stdin`.

## Supported input

Tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged (exit 0). Exit 0 means I/O succeeded. It does not mean that a transformation occurred or that a watermark was removed. Only UTF-8 files.

Example: `I don't agree.` with U+2019 is reason `unsupported-domain`, `processed=no`, and `first_unsupported=U+2019@5`. The straight ASCII apostrophe in `I don't agree.` is processed.

Machine spans stay intact: fenced/inline/indented code, HTML tags and entities, markdown destinations (including multiline), markdown reference labels (including multiline, container, and CR line endings), URLs (including `ftp://`), emails, IPs, dates, currency, percents, numbers, POSIX/Windows paths (including `src/main.py`, `scripts/build`, `C:/My final notes.txt`, `C:/Users/Alice/My final notes.txt`), CLI flags. Quote interiors are eligible. Cap 192 insertion sites. Insertions fill the first 192 eligible letter sites and then stop, so the tail of a long document is unchanged.

If the text is already transformed, has no eligible letters, or is outside the ASCII domain, the CLI returns it unchanged and reports that on stderr unless `-q`. `--status` always reports the reason, including for `too-large` and internal failure. Exit 0 still means I/O succeeded, not watermark removal.

Same visible words are not the same as identical Markdown, path, or search behavior in other programs. Reports must not treat visible-projection equality as Markdown or filesystem equality.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | Output was written or copied. Unsupported Unicode, already-transformed text, no eligible sites, and the site cap are reported on stderr. This is not watermark removal. |
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
