# Installation

Python 3.11 or newer is required. The public CLI currently returns input text unchanged: v0.3.0 has no product-authorized invisible carrier.

Install only a GitHub Release wheel and check `SHA256SUMS.txt` from that same release. Do not pipe `https://d.q1z.org/mark` into a shell. That endpoint still installs live `main` without a checksum.

## Tagged wheel (recommended)

v0.3.0 wheel SHA-256:

```text
cb4ee7b6c06d1dde8c612c237df78f68f8364bc74bf469086288e55a2d5c9325  fuckmark-0.3.0-py3-none-any.whl
```

```text
python3 -m venv .venv
.venv/bin/python -m pip install https://github.com/byte271/FuckMark/releases/download/v0.3.0/fuckmark-0.3.0-py3-none-any.whl
```

On Windows, create the venv with `py -3.12 -m venv .venv` and use `.venv\Scripts\python.exe`.

Download `SHA256SUMS.txt` from the same release and confirm the installed wheel digest before trusting the environment:

```text
https://github.com/byte271/FuckMark/releases/download/v0.3.0/SHA256SUMS.txt
```

## In-repo installer (tagged wheel + checksum)

These scripts download the GitHub Release wheel, verify `SHA256SUMS.txt`, install into a user virtualenv, and print `fuckmark --help`. They do not start the CLI, do not use sudo, and do not install Python. They default to `v0.3.0`.

Linux / macOS, from a clone:

```sh
sh tools/install/unix.sh
```

Windows PowerShell, from a clone:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install/windows.ps1
```

Optional override: `FUCKMARK_RELEASE_TAG=v0.3.0`.

## Verify

```text
fuckmark --version
```

For v0.3.0 the command must begin with:

```text
FuckMark 0.3.0
```

It also reports `release-cli-v4`. Transforming text currently prints the same visible input.

## Install from a local clone

```text
python -m pip install .
```

For development and tests:

```text
python -m pip install -e ".[dev]"
```

The core package has no runtime dependencies. Research workflows that reproduce open SynthID experiments install pinned model/runtime dependencies through `requirements-smoke.txt`. The H14 DejaVu font-metric scan, the H16 HarfBuzz shaping closure scan, and the H16 tokenizer probe use optional extra `research` (`fonttools`, `uharfbuzz`, `tokenizers`), none of which is a runtime dependency:

```text
python -m pip install -e ".[research]"
```

## Update

Install a newer tagged wheel the same way and verify `FuckMark --version` against that tag. Do not follow a moving `main.zip`.

## Troubleshooting

If the command is not found, open a new terminal so PATH updates load.

On Linux, clipboard copying with `--copy` requires one of `wl-copy`, `xclip`, `xsel`, or `clip.exe`. The CLI still prints output if clipboard transfer is unavailable.

Website: [mark.q1z.org](https://mark.q1z.org). The website one-click installer is not the source of truth for this repository.
