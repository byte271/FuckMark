# FuckMark CLI

FuckMark v0.4.0 exposes the same command under `FuckMark`, `Fuckmark`, and `fuckmark`. The public CLI uses `release-cli-v5` and applies frozen letter-mix `u034f-ufe00-letter-alt-v1`.

The public CLI is intentionally smaller than the research harness. It does not load detector code, watermark keys, model weights, network services, Cycle 4/6/7 visible-edit schedulers, or quarantined U+200C diagnostics. It also does not apply contractions. `release_transform_registry()` stays empty; mix is not selected from a greedy rule catalog.

**Priority Zero:** the CLI must not change user-visible text. The authorized transform only inserts U+034F and U+FE00 after eligible ASCII letters. `--visible` writes that projection.

Install instructions for Windows, macOS, and Linux are in [`install.md`](install.md). The official website is [mark.q1z.org](https://mark.q1z.org). The product contract is [`product-contract.md`](product-contract.md).

## Interactive use

Run:

```text
FuckMark
```

Paste the source text and finish with `:done` on its own line. The legacy `ok` terminator remains accepted.

Interactive mode reports the exact project version, processes the text deterministically, prints the raw mix payload, and reports how many product-authorized invisible insertions were applied. It does not copy to the clipboard unless `--copy` is passed. Color is emitted only when standard output is an interactive terminal. `--no-color` and the `NO_COLOR` environment variable disable ANSI output.

## Stream use

Piped input automatically selects stream mode:

```sh
printf 'I do not agree.\n' | FuckMark
```

Standard output is the raw mix payload, not `I don't agree.` Use `--visible` when you want the original visible line.

Use `--stdin` or `--non-interactive` to request the same mode explicitly. Clipboard access is disabled unless `--copy` is provided.

## File use

The positional input path is decoded strictly as UTF-8. Latin-1, ASCII, and Windows-1252 are unsupported product encodings:

```text
FuckMark input.txt
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
FuckMark --stdin --encoding latin-1   # rejected
```

Without `--output`, file-mode output is written to standard output. `--output -` also selects standard output. Named output files are written through an fsynced temporary file and atomically replaced. Input and output paths must differ.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print project, CLI, and release-registry identities. |
| `--stdin`, `--non-interactive` | Read all standard input in explicit stream mode. |
| `-o FILE`, `--output FILE` | Atomically write transformed UTF-8 text to a file. |
| `--copy` | Also copy the written text to the platform clipboard. |
| `--visible` | Write the user-visible projection of the product-authorized payload. |
| `--encoding NAME` | Output encoding. Only `utf-8` is supported. `latin-1`, `ascii`, and `cp1252` are rejected. |
| `-q`, `--quiet` | Hide interactive processing and completion messages. |
| `--no-color` | Disable ANSI terminal color. |

## Fail-closed identity

The CLI returns the original text unchanged when:

- the input is outside ordinary English ASCII v1 (tab / LF / CR / U+0020..U+007E);
- no eligible ASCII letter sites remain after hard machine spans;
- the source already contains U+034F or U+FE00;
- apply, carrier-insertion, or visible-projection checks fail.

Hard machine spans: fenced/inline code, markdown destinations, URLs, emails, IPs, dates, currency, percents, numbers, POSIX/Windows paths, CLI flags. Quote interiors are eligible. Selected-site cap 192.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | Transformation and requested outputs succeeded. |
| 1 | Input, transformation, or output validation failed. |
| 2 | Transformation succeeded, but clipboard transfer failed. The transformed text is still written to the requested non-clipboard destination or printed as fallback output. |

Errors are written to standard error. Empty input is rejected. Clipboard commands are resolved locally and time out after ten seconds.

## Platform clipboard commands

- macOS: `pbcopy`
- Windows: `clip`
- Linux: `wl-copy`, then `xclip`, then `xsel`, then `clip.exe`

`--copy` copies the same bytes that are written (raw mix unless `--visible`).

## Release boundary

Historical contraction, Cycle 6 spacing, Cycle 7 durable visible edits, detector scoring, experimental search, H12 control-mix, and the U+200C diagnostic registry remain outside automatic release behavior. The v1 mix sanitizer gate stays FAIL. Mn-strip and default-ignorable-strip remain recorded stress tests.
