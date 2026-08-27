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
Enter :done on a new line when finished.

> I do not agree.
> This can contain multiple lines.
>
> Another paragraph.
> :done

Processing...

✓ Copied to clipboard
```

Blank lines are kept. `:done` ends the session only when it is the entire line. The transformed payload is copied and not printed.

If clipboard copy fails, nothing is printed. Pipe text instead: `printf 'I do not agree.\n' | fuckmark`. Ctrl+C exits cleanly. EOF without `:done` is an error and copies nothing.

Redirected or piped stdin does not open this UI. It is processed as a stream.

## Stream examples

```text
printf 'I do not agree.\n' | fuckmark
fuckmark "I do not agree."
fuckmark notes.txt
fuckmark notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | fuckmark --copy
printf 'I do not agree.\n' | fuckmark --visible
```

Piped or quoted input writes the hidden payload to stdout. `--visible` writes the original visible text. `--copy` also places whatever was written on the clipboard.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print `FuckMark 0.4.0`. |
| `--stdin` | Read all of standard input. |
| `-o FILE`, `--output FILE` | Write UTF-8 output to FILE. |
| `--copy` | Also copy the output to the clipboard. The paste UI always copies. |
| `--visible` | Print the visible text (no hidden characters). |
| `--encoding NAME` | Only `utf-8`. `latin-1`, `ascii`, and `cp1252` are rejected. |
| `-q`, `--quiet` | Hide non-essential status messages. |
| `--no-color` | Disable color on stderr. `NO_COLOR` does the same. |

`--non-interactive` is an alias of `--stdin`.

Quoted text that is not an existing file is transformed as a string. Existing files are read as UTF-8. A path-like argument that is missing (for example `notes.txt`) is an error, not a string. Invalid UTF-8 input is rejected.

## Supported input

Tab, newline, carriage return, and ASCII space through tilde. Other Unicode is returned unchanged (exit 0). Only UTF-8 files.

Machine spans stay intact: fenced/inline code, markdown destinations, URLs, emails, IPs, dates, currency, percents, numbers, POSIX/Windows paths, CLI flags. Quote interiors are eligible. Cap 192 insertion sites.

If the text is already transformed, or has no eligible letters, the CLI returns it unchanged.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | Output was written or copied. Unsupported input is returned unchanged. |
| 1 | No input, bad file, unsupported encoding, missing `:done`, or output could not be written. |
| 2 | Transform succeeded, but clipboard copy failed. Stream modes still write stdout. The paste UI does not print the payload. |
| 130 | Interrupted with Ctrl+C. |

## Clipboard

- macOS: `pbcopy`
- Windows: `clip` (UTF-16)
- Linux: `wl-copy`, then `xclip`, then `xsel`, then `clip.exe`

## Install

See [`install.md`](install.md).
