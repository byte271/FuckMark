from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import TextIO

from .transforms import release_transform_registry


CLI_TERMINATOR = "ok"
CLI_SELECTION_SEED = 0


class ClipboardUnavailableError(RuntimeError):
    pass


def process_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    registry = release_transform_registry()
    enumeration = registry.enumerate(text)
    selected: list[str] = []
    occupied_until = 0
    for candidate in enumeration.candidates:
        if candidate.start < occupied_until:
            continue
        selected.append(candidate.candidate_id)
        occupied_until = candidate.end
    if not selected:
        return text
    result = registry.apply(enumeration, tuple(selected), seed=CLI_SELECTION_SEED)
    return result.output_text


def read_pasted_text(input_stream: TextIO, output_stream: TextIO) -> str:
    output_stream.write("Paste text below. Type ok on its own line and press Enter when finished.\n")
    output_stream.flush()
    lines: list[str] = []
    for raw_line in input_stream:
        line = raw_line.rstrip("\r\n")
        if line.strip().casefold() == CLI_TERMINATOR:
            break
        lines.append(line)
    return "\n".join(lines)


def _clipboard_commands() -> tuple[tuple[str, ...], ...]:
    if sys.platform == "darwin":
        return (("pbcopy",),)
    if sys.platform == "win32":
        return (("clip",),)
    return (
        ("wl-copy",),
        ("xclip", "-selection", "clipboard"),
        ("xsel", "--clipboard", "--input"),
        ("clip.exe",),
    )


def copy_to_clipboard(text: str) -> None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    failures: list[str] = []
    for command in _clipboard_commands():
        executable = command[0]
        if shutil.which(executable) is None:
            continue
        try:
            subprocess.run(
                command,
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            return
        except (OSError, subprocess.CalledProcessError) as error:
            failures.append(f"{executable}:{type(error).__name__}")
    detail = ", ".join(failures) if failures else "no supported clipboard command found"
    raise ClipboardUnavailableError(detail)


def main(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    clipboard_writer: Callable[[str], None] | None = None,
) -> int:
    source = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output_stream is None else output_stream
    writer = copy_to_clipboard if clipboard_writer is None else clipboard_writer
    text = read_pasted_text(source, output)
    if not text:
        output.write("No text received.\n")
        output.flush()
        return 1
    output.write("Processing...\n")
    output.flush()
    try:
        transformed = process_text(text)
    except Exception as error:
        output.write(f"Failed: {error}\n")
        output.flush()
        return 1
    try:
        writer(transformed)
    except Exception as error:
        output.write(f"Processed, but clipboard copy failed: {error}\n")
        output.write(transformed)
        output.write("\n")
        output.flush()
        return 2
    if transformed == text:
        output.write("Success. No eligible changes. Original text copied to clipboard.\n")
    else:
        output.write("Success. Copied to clipboard.\n")
    output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
