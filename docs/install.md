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

`python3 -m pip install git+https://github.com/byte271/FuckMark.git` installs the same product from `main`.

## Tagged wheel

v0.4.0 wheel SHA-256:

```text
5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f  fuckmark-0.4.0-py3-none-any.whl
```

The GitHub Release wheel is the checksummed install.

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

These scripts download the GitHub Release wheel, verify `SHA256SUMS.txt`, install into a user virtualenv, and print `fuckmark --help`. They do not start the CLI, do not use sudo, and do not install Python. They default to `v0.4.0`.

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
