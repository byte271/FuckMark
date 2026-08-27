# FuckMark CLI

The same command is installed as `fuckmark`, `FuckMark`, and `Fuckmark`.

It inserts hidden Unicode into ordinary English ASCII text. The words on screen do not change. Standard output is the transformed text so pipes stay script-friendly. Status and errors go to stderr.

```text
fuckmark --help
```

## Examples

```text
printf 'I do not agree.\n' | fuckmark
fuckmark "I do not agree."
fuckmark notes.txt
fuckmark notes.txt -o notes.fm.txt
printf 'I do not agree.\n' | fuckmark --copy
printf 'I do not agree.\n' | fuckmark --visible
```

Piped or quoted input writes the hidden payload. `--visible` writes the original visible text. `--copy` also places whatever was written on the clipboard.

Interactive mode (a TTY with no file, quoted text, or pipe): paste text, then a line with only `:done`. The payload still goes to stdout. The `ok` terminator still works.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print `FuckMark 0.4.0` plus internal algorithm ids. |
| `--stdin` | Read all of standard input. |
| `-o FILE`, `--output FILE` | Write UTF-8 output to FILE. |
| `--copy` | Also copy the output to the clipboard. |
| `--visible` | Print the visible text (no hidden characters). |
| `--encoding NAME` | Only `utf-8`. `latin-1`, `ascii`, and `cp1252` are rejected. |
| `-q`, `--quiet` | Hide stderr status in interactive mode. |
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
| 0 | Output was written. Unsupported input is returned unchanged. |
| 1 | No input, bad file, unsupported encoding, or output could not be written. |
| 2 | Transform succeeded, but clipboard copy failed. The text was still written. |

## Clipboard

- macOS: `pbcopy`
- Windows: `clip` (UTF-16)
- Linux: `wl-copy`, then `xclip`, then `xsel`, then `clip.exe`

## Install

See [`install.md`](install.md). Product contract: [`product-contract.md`](product-contract.md).
