# Installation

FuckMark v0.2.0 supports Windows, macOS, and Linux with Python 3.11 or newer. The official installer endpoint is `https://d.q1z.org/mark`.

## Linux

```sh
curl -fsSL https://d.q1z.org/mark | sh
```

## macOS

```sh
curl -fsSL https://d.q1z.org/mark | sh
```

## Windows

Run PowerShell:

```powershell
irm https://d.q1z.org/mark | iex
```

The endpoint selects PowerShell for Windows clients and a Unix dispatcher for Linux/macOS clients. The installer creates an isolated user-level virtual environment and exposes FuckMark without requiring an administrator installation.

## Verify

Open a new terminal after installation and run:

```text
FuckMark --version
```

For v0.2.0, the command must begin with:

```text
FuckMark 0.2.0
```

It also reports the release CLI and transform-registry algorithm identities.

## Manual tagged installation

Users who do not want to pipe a remote installer into a shell can install the immutable tagged source explicitly:

```text
python -m venv .venv
python -m pip install https://github.com/byte271/FuckMark/archive/refs/tags/v0.2.0.zip
```

Activate the virtual environment using the platform's normal command, then run `FuckMark --version`.

## Install from a local clone

From the repository root:

```text
python -m pip install .
```

For development and tests:

```text
python -m pip install -e ".[dev]"
```

The core package has no runtime dependencies. Research workflows that reproduce open SynthID experiments install their pinned model/runtime dependencies separately through `requirements-smoke.txt` and the workflow definitions.

## Update

Run the same one-command installer again. It replaces the package inside the managed virtual environment while preserving the command location.

After any update, verify the installed version with `FuckMark --version`.

## Troubleshooting

If the command is not found immediately after installation, open a new terminal so the updated user PATH is loaded.

On Linux, clipboard copying requires one of `wl-copy`, `xclip`, `xsel`, or `clip.exe`. The CLI still produces transformed output if clipboard transfer is unavailable.

Website: [mark.q1z.org](https://mark.q1z.org)
