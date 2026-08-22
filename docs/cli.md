# FuckMark CLI

FuckMark v0.1.0 exposes the same entry point under `FuckMark`, `Fuckmark`, and `fuckmark`. All aliases use `release-cli-v3` and the same content-addressed release transform registry.

Install instructions for Windows, macOS, and Linux are maintained in [`install.md`](install.md). The official website is [mark.q1z.org](https://mark.q1z.org).

## Interactive use

Run `FuckMark` from a terminal, paste the source text, and finish with `:done` on its own line. The legacy `ok` terminator is retained for compatibility. The CLI reports the exact version, processes the text deterministically, shows the number of accepted changes, and copies the result to the platform clipboard.

Color is emitted only when standard output is an interactive terminal. `--no-color` and the `NO_COLOR` environment variable disable it.

## Stream use

Piped input is detected automatically:

```text
printf 'I do not agree.\n' | FuckMark
```

Use `--stdin` or `--non-interactive` to request the same mode explicitly. Standard output contains only transformed text. Clipboard access is disabled unless `--copy` is provided, so the mode is safe for pipelines.

## File use

The positional input path is decoded strictly as UTF-8:

```text
FuckMark input.txt
FuckMark input.txt --output output.txt
FuckMark input.txt --copy
```

Without `--output`, file-mode output is written to standard output. `--output -` also selects standard output. A named output file is written through an fsynced temporary file and atomically replaced. Input and output paths must differ.

## Options

| Option | Behavior |
| --- | --- |
| `--version` | Print project, CLI, and release-registry identities. |
| `--stdin`, `--non-interactive` | Read all standard input in explicit stream mode. |
| `-o FILE`, `--output FILE` | Atomically write the transformed UTF-8 text to a file. |
| `--copy` | Also copy transformed text to the system clipboard. |
| `-q`, `--quiet` | Hide interactive processing and completion messages. |
| `--no-color` | Disable ANSI terminal color. |

## Exit status

| Status | Meaning |
| ---: | --- |
| 0 | Transformation and requested outputs succeeded. |
| 1 | Input, transformation, or output validation failed. |
| 2 | Transformation succeeded, but clipboard transfer failed. The transformed text is still written to the requested non-clipboard destination or printed in interactive fallback mode. |

Errors are written to standard error. Empty input is rejected. Clipboard commands are resolved locally and time out after ten seconds; the CLI has no network path.

## Release boundary

The CLI uses only `release_transform_registry()`. Development profiles, detector code, experimental search, and the quarantined visible-projection registry are never imported or selected by the public command.
