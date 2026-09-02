# FuckMark clipboard — scan, clean, and watch copied text

`fuckmark clipboard` sits at the OS paste edge. It reads whatever is currently
on the clipboard, runs `fuckmark-hidden-scan-v1`, and can strip hidden Unicode
before you paste into a terminal, editor, or chat box.

Default categories match `fuckmark lint`: `bidi_control`, `zero_width`, `tag`,
`control`, `noncharacter`, and `surrogate`. That is the Trojan Source /
zero-width / Unicode-tag smuggling set. It does not judge visible text.

This is the desktop twin of browser paste-safe. It keeps real emoji ZWJ
sequences (both neighbors emoji) and info-level variation selectors.

## Command line

```text
fuckmark clipboard scan                 # read once, report, do not change
fuckmark clipboard scan --json
fuckmark clipboard scan -q
fuckmark clipboard clean                # strip findings in place
fuckmark clipboard watch                # poll until Ctrl+C
fuckmark clipboard watch --clean
fuckmark clipboard watch --once --exit-on-find
fuckmark clipboard watch --interval 0.25 --max-seconds 30
fuckmark clipboard watch --select all
```

`scan` and `clean` run one clipboard read. `watch` polls every `--interval`
seconds (default 0.5) and warns only when the clipboard *contents change* to a
payload that still has findings. Identical text is not re-alerted. `--once`
exits after the first poll. `--exit-on-find` exits when the first hidden
payload appears. `--max-seconds` stops a watch loop even if nothing was found.
`--clean` re-reads the clipboard immediately before rewriting it, so a newer
copy made during the alert is left alone.

`--select security` is the default. `--select all` includes variation
selectors, enclosing marks, format controls, and private-use. Pass an explicit
comma-separated subset to match `fuckmark lint --select`.

`--json` writes a receipt to stdout (`algorithm_version`, `action`, `removed`,
`scan`). Human reports go to stderr. `-q` writes the `fuckmark-scan` machine
line to stdout.

## Exit status

| Status | Meaning |
| ---: | ---: |
| 0 | No findings in the selected categories (or the watch loop ended cleanly). |
| 1 | Findings were present. `clean` still returns 1 after a successful rewrite. |
| 2 | Usage error (missing subcommand, bad `--select`, non-positive `--interval`). |
| 3 | No clipboard tool, or the tool failed. Nothing was rewritten. |

`fuckmark clipboard` is dispatched like `fuckmark lint`. A file named
`clipboard` in the current directory is not read; use `fuckmark --file
clipboard` for that.

## Clipboard tools

| Platform | Read | Write (via existing CLI copy) |
| --- | --- | --- |
| macOS | `pbpaste` | `pbcopy` |
| Linux | `wl-paste`, then `xclip -o`, then `xsel` | `wl-copy`, `xclip`, `xsel`, `clip.exe` |
| Windows | PowerShell `Get-Clipboard -Raw` | `clip` (UTF-16) |

UTF-8 is tried first. If the bytes contain NULs and have even length, the
watcher decodes UTF-16LE instead. That is what Windows PowerShell emits for
plain ASCII without a BOM; treating it as UTF-8 would insert a `U+0000`
control between every letter. A UTF-16 BOM (`FF FE` / `FE FF`) is honored.

Install one of those tools on a desktop session. Headless CI has no clipboard;
tests inject a fake reader and writer and never call the OS.

## Python

```text
from fuckmark.clipboard_watch import (
    clean_clipboard_text,
    evaluate_clipboard_text,
    watch_clipboard,
)

alert = evaluate_clipboard_text(copied)
cleaned, removed, _scan = clean_clipboard_text(copied)
code = watch_clipboard(
    once=True,
    clean=True,
    reader=lambda: copied,
    writer=sink.append,
)
```

`watch_clipboard` accepts `reader`, `writer`, `sleeper`, and `clock` so tests
and embedders do not need a real clipboard. Algorithm id:
`fuckmark-clipboard-watch-v1`.
