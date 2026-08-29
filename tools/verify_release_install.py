from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix

EXPECTED_INPUT = "I do not agree and I cannot stay.\n"
EXPECTED_OUTPUT = apply_letter_alternating_mix(EXPECTED_INPUT)
PROJECT_VERSION = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    kwargs.setdefault("encoding", "utf-8")
    return subprocess.run(command, text=True, check=True, **kwargs)


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_commands(root: Path) -> tuple[Path, ...]:
    scripts = root / ("Scripts" if os.name == "nt" else "bin")
    if os.name == "nt":
        return (scripts / "fuckmark.exe",)
    return tuple(scripts / name for name in ("FuckMark", "Fuckmark", "fuckmark"))


def _artifacts(directory: Path) -> tuple[Path, ...]:
    artifacts = tuple(sorted((*directory.glob("*.whl"), *directory.glob("*.tar.gz"))))
    if len(artifacts) != 2:
        raise RuntimeError("release directory must contain exactly one wheel and one source distribution")
    return artifacts


def _write_checksums(directory: Path, artifacts: tuple[Path, ...]) -> None:
    rows = []
    for artifact in artifacts:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        rows.append(f"{digest}  {artifact.name}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")


def _verify_artifact(artifact: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="fuckmark-release-") as value:
        root = Path(value)
        venv.EnvBuilder(with_pip=True).create(root)
        python = _venv_python(root)
        environment = {
            **os.environ,
            "PIP_CACHE_DIR": str(root / "pip-cache"),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        _run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(artifact)],
            env=environment,
        )
        for command in _venv_commands(root):
            if not command.is_file():
                raise RuntimeError(f"missing installed console command: {command.name}")
            version = _run([str(command), "--version"], capture_output=True, env=environment).stdout
            if f"FuckMark {PROJECT_VERSION}" not in version or "release-cli" in version:
                raise RuntimeError(f"unexpected version output from {command.name}: {version!r}")
            try:
                transformed = _run(
                    [str(command), "--stdin", "-q"],
                    input=EXPECTED_INPUT,
                    capture_output=True,
                    env=environment,
                )
            except subprocess.CalledProcessError as error:
                raise RuntimeError(
                    f"installed CLI failed for {command.name}: stdout={error.stdout!r} stderr={error.stderr!r}"
                ) from error
            if transformed.stdout != EXPECTED_OUTPUT or transformed.stderr:
                raise RuntimeError(
                    f"installed CLI failed for {command.name}: stdout={transformed.stdout!r} stderr={transformed.stderr!r}"
                )
            loud = _run(
                [str(command), "--stdin"],
                input=EXPECTED_INPUT,
                capture_output=True,
                env=environment,
            )
            if loud.stdout != EXPECTED_OUTPUT or "processed=yes" not in loud.stderr:
                raise RuntimeError(
                    f"installed CLI status failed for {command.name}: stdout={loud.stdout!r} stderr={loud.stderr!r}"
                )
            visible = _run(
                [str(command), "--stdin", "--visible", "-q"],
                input=EXPECTED_INPUT,
                capture_output=True,
                env=environment,
            )
            if visible.stdout != EXPECTED_INPUT or visible.stderr:
                raise RuntimeError(
                    f"installed CLI --visible failed for {command.name}: stdout={visible.stdout!r} stderr={visible.stderr!r}"
                )
            quoted = _run(
                [str(command), "-q", "I do not agree."],
                capture_output=True,
                env=environment,
            )
            expected_arg = apply_letter_alternating_mix("I do not agree.")
            if quoted.stdout != expected_arg or quoted.stderr:
                raise RuntimeError(
                    f"installed CLI quoted argument failed for {command.name}: stdout={quoted.stdout!r} stderr={quoted.stderr!r}"
                )
            text_flag = _run(
                [str(command), "--text", "I do not agree.", "-q"],
                capture_output=True,
                env=environment,
            )
            if text_flag.stdout != expected_arg or text_flag.stderr:
                raise RuntimeError(
                    f"installed CLI --text failed for {command.name}: stdout={text_flag.stdout!r} stderr={text_flag.stderr!r}"
                )
            source_file = root / "notes.txt"
            source_file.write_text("I do not agree.\n", encoding="utf-8")
            file_flag = _run(
                [str(command), "--file", str(source_file), "-q"],
                capture_output=True,
                env=environment,
            )
            expected_file = apply_letter_alternating_mix("I do not agree.\n")
            if file_flag.stdout != expected_file or file_flag.stderr:
                raise RuntimeError(
                    f"installed CLI --file failed for {command.name}: stdout={file_flag.stdout!r} stderr={file_flag.stderr!r}"
                )
            status_line = _run(
                [str(command), "--text", "I do not agree.", "--status", "-q"],
                capture_output=True,
                env=environment,
            )
            if (
                status_line.stdout != expected_arg
                or "fuckmark-status" not in status_line.stderr
                or "processed=yes" not in status_line.stderr
            ):
                raise RuntimeError(
                    f"installed CLI --status failed for {command.name}: stdout={status_line.stdout!r} stderr={status_line.stderr!r}"
                )
            help_text = _run([str(command), "--help"], capture_output=True, env=environment).stdout
            if "fuckmark" not in help_text.casefold() or "--visible" not in help_text or ":done" not in help_text:
                raise RuntimeError(f"installed CLI --help failed for {command.name}: {help_text!r}")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_release_install.py DIST_DIRECTORY")
    directory = Path(sys.argv[1]).resolve()
    artifacts = _artifacts(directory)
    _write_checksums(directory, artifacts)
    for artifact in artifacts:
        _verify_artifact(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
