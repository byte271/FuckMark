# FuckMark CLI

FuckMark v0.3.0 exposes the same command under `FuckMark`, `Fuckmark`, and `fuckmark`. The public CLI uses `release-cli-v4` and the product visible-invariance registry.

The public CLI is intentionally smaller than the research harness. It does not load detector code, watermark keys, model weights, network services, Cycle 4/6/7 visible-edit schedulers, or quarantined U+200C diagnostics. It also does not apply contractions.

**Priority Zero:** the CLI must not change user-visible text. Until a product-authorized invisible carrier exists, the CLI fail-closes and returns the input unchanged.

Install instructions for Windows, macOS, and Linux are in [`install.md`](install.md). The official website is [mark.q1z.org](https://mark.q1z.org). The product contract is [`product-contract.md`](product-contract.md).

## Interactive use

Run:

```text
FuckMark
```

Paste the source text and finish with `:done` on its own line. The legacy `ok` terminator remains accepted.

Interactive mode reports the exact project version, processes the text deterministically, prints the result, and reports whether any product-authorized invisible transform was applied. It does not copy to the clipboard unless `--copy` is passed. Color is emitted only when standard output is an interactive terminal. `--no-color` and the `NO_COLOR` environment variable disable ANSI output.

## Stream use

Piped input automatically selects stream mode:

```sh
printf 'I do not agree.\n' | FuckMark
```

Current product output is the same visible line, not `I don't agree.`

Use `--stdin` or `--non-interactive` to request the same mode explicitly. Standard output contains only transformed text. Clipboard access is disabled unless `--copy` is provided.

## File use

The positional input path is decoded strictly as UTF-8:

```text
FuckMark input.txt
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
```

Without `--output`, file-mode output is written to standard output. `--output -` also selects standard output. Named output files are written through an fsynced temporary file and atomically replaced. Input and output paths must differ.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print project, CLI, and release-registry identities. |
| `--stdin`, `--non-interactive` | Read all standard input in explicit stream mode. |
| `-o FILE`, `--output FILE` | Atomically write transformed UTF-8 text to a file. |
| `--copy` | Also copy transformed text to the platform clipboard. |
| `-q`, `--quiet` | Hide interactive processing and completion messages. |
| `--no-color` | Disable ANSI terminal color. |

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

## Release boundary

The CLI uses only `release_transform_registry()`, which means the exact visible-projection product contract, not "semantically conservative English edits." Historical contraction, Cycle 6 spacing, Cycle 7 durable visible edits, detector scoring, experimental search, and the U+200C diagnostic registry remain outside automatic release behavior.
