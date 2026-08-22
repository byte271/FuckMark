# Installation

FuckMark supports Windows, macOS, and Linux with Python 3.11 or newer. The official installer endpoint is `https://d.q1z.org/mark`.

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

The endpoint selects PowerShell for Windows clients and a small dispatcher for Unix clients. The Unix dispatcher selects the Linux or macOS installer from `uname`. Each platform installer creates an isolated user-level virtual environment and exposes FuckMark without requiring an administrator installation.

## Verify

Open a new terminal after installation and run:

```text
FuckMark --version
```

The command must report FuckMark `v0.1.0`, `release-cli-v3`, and the release-registry identity.

## Manual package installation

Users who do not want to pipe a remote installer into a shell can install the tagged source explicitly:

```text
python -m venv .venv
python -m pip install https://github.com/byte271/FuckMark/archive/refs/tags/v0.1.0.zip
```

Activate the virtual environment using the platform's normal command, then run `FuckMark --version`.

## Update

Run the same one-command installer again. It replaces the package inside the managed virtual environment while preserving the command location.

Website: [mark.q1z.org](https://mark.q1z.org)
