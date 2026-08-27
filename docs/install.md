# Installation

Python 3.11 or newer. The public CLI is `fuckmark` / `FuckMark` / `Fuckmark`.

Do not pipe `https://d.q1z.org/mark` into a shell.

## From this repository (works now)

```text
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fuckmark --version
```

On Windows, create the venv with `py -3.12 -m venv .venv` and use `.venv\Scripts\python.exe`.

After this tree is on `main`, `python3 -m pip install git+https://github.com/byte271/FuckMark.git` installs the same product. Until then, install from a clone.

## Tagged wheel (after `v0.4.0` is published)

The GitHub Release wheel is the checksummed install. It does not exist until the immutable `v0.4.0` tag and `workflow_dispatch` publication in [`release.md`](release.md).

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

These scripts download the GitHub Release wheel, verify `SHA256SUMS.txt`, install into a user virtualenv, and print `fuckmark --help`. They do not start the CLI, do not use sudo, and do not install Python. They default to `v0.4.0` and 404 until that release exists.

Linux / macOS, from a clone:

```text
sh tools/install/unix.sh
```

Windows PowerShell, from a clone:

```text
powershell -ExecutionPolicy Bypass -File tools/install/windows.ps1
```

Optional override: `FUCKMARK_RELEASE_TAG=v0.4.0`.

## Verify

```text
fuckmark --version
printf 'I do not agree.\n' | fuckmark --visible
```

`--version` must print `FuckMark 0.4.0`. `--visible` must print `I do not agree.`

In a terminal, `fuckmark` with no arguments opens the paste UI. Finish with `:done`. The result is copied, not printed.

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

## Troubleshooting

If the command is not found, open a new terminal so PATH updates load.

On Linux, clipboard copy needs `wl-copy`, `xclip`, `xsel`, or `clip.exe`. Stream `--copy` still prints the text if copy fails (exit 2). The paste UI does not print the payload; pipe text if you need stdout.

Website: [mark.q1z.org](https://mark.q1z.org).
