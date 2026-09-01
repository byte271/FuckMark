# FuckMark lint — hidden-Unicode CI, pre-commit, and editors

`fuckmark lint` scans files and directories for hidden or malicious Unicode and
exits non-zero on findings. It is the defensive scanner (`fuckmark --scan`)
wired for automation: CI gates, pre-commit hooks, and editor integrations.

It catches the classes that read as ordinary text but are not:

- **Trojan Source** bidirectional overrides and isolates (CVE-2021-42574)
- zero-width and invisible spacing characters
- Unicode **tag** characters (hidden text / prompt-injection smuggling)
- C0/C1 controls, noncharacters, and lone surrogates

## Command line

```text
fuckmark lint                       # scan the current directory
fuckmark lint src/ docs/            # scan specific paths
fuckmark lint --json .              # machine-readable report
fuckmark lint --fix .               # strip the findings in place
fuckmark lint --select all .        # fail on every category, not just the security set
fuckmark lint --exclude '*.min.js' src/
```

Exit status: `0` when clean, `1` when findings remain (or when `--fix` changed a
file), `2` for a usage error. Findings and the JSON report go to stdout; the
one-line summary goes to stderr.

### Categories

`--select` chooses which categories cause a failure. The default is the
security-focused set `bidi_control,zero_width,tag,control,noncharacter,surrogate`.
Pass `--select all` to include `variation_selector`, `enclosing_mark`,
`line_separator`, `deprecated`, `format`, and `private_use`, or pass an explicit
comma-separated subset. See [`cli.md`](cli.md) for the full category list.

### What is skipped

Binary files (containing NUL), non-UTF-8 files, files larger than `--max-bytes`
(default 5,000,000), symlinks, and common vendored or VCS directories (`.git`,
`node_modules`, `.venv`, `__pycache__`, `dist`, `build`, and similar). Add more
with repeatable `--exclude GLOB`.

## GitHub Action

Add a step that fails the build when hidden Unicode appears in the tree:

```yaml
name: hidden-unicode
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: byte271/FuckMark@main
        with:
          paths: "."
```

Inputs: `paths` (default `.`), `select` (default security set), `fix`
(`true`/`false`), `json` (`true`/`false`), and `args` (extra raw flags). The
action installs FuckMark from its own checkout, so it always runs the version of
the engine pinned by the `uses:` ref.

## pre-commit

Add FuckMark to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/byte271/FuckMark
    rev: v0.4.1
    hooks:
      - id: fuckmark
```

Use `id: fuckmark-fix` instead to strip findings in place on commit. The hook
runs on text files and receives the staged filenames.

## Editor use

The same JSON contract (`--json`) is what an editor extension consumes to render
inline decorations. The report lists each file, per-category counts, and the
first locations as `{index, codepoint, category}`.
