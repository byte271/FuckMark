# Installation

Python 3.11 or newer. The public CLI is `fuckmark` / `FuckMark` / `Fuckmark`.

Prefer a browser over the CLI? After install, run `fuckmark web` to open the local paste tool. Before installing, you can also open [`mark.html`](mark.html) or the research demo [`demo.html`](demo.html) with `file://`. After website deploy: [mark.q1z.org/mark.html](https://mark.q1z.org/mark.html) and [mark.q1z.org/demo.html](https://mark.q1z.org/demo.html).

Do not pipe `https://d.q1z.org/mark` into a shell. The live website must match [`website.md`](website.md).

This source tree is **0.4.1**. The last published GitHub Release wheel is **v0.4.0**. That wheel does not implement `--text` or `--file`. Do not retag v0.4.0. The v0.4.1 wheel SHA-256 is recorded after the GitHub Release exists.

## From this repository (works now)

Linux / macOS, from a clean shell with no FuckMark on PATH:

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fuckmark --version
.venv/bin/fuckmark web
printf 'I do not agree.\n' | .venv/bin/fuckmark --visible
```

`fuckmark web` opens `http://127.0.0.1:8765/mark.html` for beginners who do not want pipes or flags. Detect and strip on that page talk to the local Python API.

Keep using `.venv/bin/fuckmark` unless you activate the venv:

```text
. .venv/bin/activate
fuckmark --version
fuckmark web
```

Windows PowerShell:

```text
git clone https://github.com/byte271/FuckMark.git
cd FuckMark
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\fuckmark.exe --version
```

`python3 -m pip install git+https://github.com/byte271/FuckMark.git` installs the same product from `main` after this branch merges.

## Tagged wheel

v0.4.0 wheel SHA-256 (last published GitHub Release; missing `--text` / `--file`):

```text
5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f  fuckmark-0.4.0-py3-none-any.whl
```

```text
python3 -m venv .venv
.venv/bin/python -m pip install https://github.com/byte271/FuckMark/releases/download/v0.4.0/fuckmark-0.4.0-py3-none-any.whl
```

Download `SHA256SUMS.txt` from the same release and confirm the wheel digest before trusting the environment:

```text
https://github.com/byte271/FuckMark/releases/download/v0.4.0/SHA256SUMS.txt
```

The historical v0.3.0 wheel SHA-256 is:

```text
cb4ee7b6c06d1dde8c612c237df78f68f8364bc74bf469086288e55a2d5c9325  fuckmark-0.3.0-py3-none-any.whl
```

That tag is not retagged.

## In-repo installer (tagged wheel + checksum)

These scripts download the GitHub Release wheel, verify `SHA256SUMS.txt`, install into a user virtualenv, and print `fuckmark --help`. They do not start the CLI, do not use sudo, and do not install Python. They default to `v0.4.1` once that GitHub Release exists. Until then, install from this clone as above. Override: `FUCKMARK_RELEASE_TAG=v0.4.0` for the last published wheel.

Linux / macOS, from a clone:

```text
sh tools/install/unix.sh
```

Windows PowerShell, from a clone:

```text
powershell -ExecutionPolicy Bypass -File tools/install/windows.ps1
```

`FUCKMARK_BIN` is the launcher directory and the directory added to PATH. `FUCKMARK_HOME` is the venv root. The Windows `fuckmark.cmd` launcher is ASCII so `cmd.exe` can run it. When the Python path is non-ASCII, an ASCII `.cmd` trampoline calls a UTF-8 `fuckmark.ps1`.

## Verify

```text
.venv/bin/fuckmark --version
printf 'I do not agree.\n' | .venv/bin/fuckmark --visible
printf 'I do not agree.\n' | .venv/bin/fuckmark --status >/tmp/fm.out
```

This tree prints `FuckMark 0.4.1`. `--visible` prints `I do not agree.` `--status` writes a `fuckmark-status` line to stderr. Installation success is not watermark removal.

In a terminal, `fuckmark` with no arguments opens the paste UI. Finish with `:done`. The result is copied, not printed. Stderr says whether hidden characters were inserted.

If clipboard copy fails, pipe text: `printf 'I do not agree.\n' | .venv/bin/fuckmark`.

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## Troubleshooting

If the command is not found, use the venv path from the install step, or open a new terminal so PATH updates load.

On Linux, clipboard copy needs `wl-copy`, `xclip`, `xsel`, or `clip.exe`. Stream `--copy` still prints the text if copy fails (exit 3). The paste UI does not print the payload; pipe text if you need stdout.

Website: [mark.q1z.org](https://mark.q1z.org). Controlled copy: [`website.md`](website.md).
