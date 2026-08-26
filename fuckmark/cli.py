from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from . import __project_name__, __version__
from .product.visible_projection import is_carrier_insertion_v1, product_approved_carriers_v1
from .transforms import TRANSFORM_REGISTRY_ALGORITHM_VERSION, release_transform_registry


CLI_TERMINATORS = frozenset({":done", "ok"})
CLI_SELECTION_SEED = 0
RELEASE_CLI_ALGORITHM_VERSION = "release-cli-v4"
_ANSI_BLUE = "\033[38;5;39m"
_ANSI_GREEN = "\033[38;5;40m"
_ANSI_YELLOW = "\033[38;5;214m"
_ANSI_BOLD = "\033[1m"
_ANSI_RESET = "\033[0m"


class ClipboardUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessResult:
    output_text: str
    change_count: int

    @property
    def changed(self) -> bool:
        return self.change_count > 0


def transform_text(text: str) -> ProcessResult:
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
        return ProcessResult(text, 0)
    try:
        result = registry.apply(enumeration, tuple(selected), seed=CLI_SELECTION_SEED)
    except (KeyError, TypeError, ValueError):
        return ProcessResult(text, 0)
    if not is_carrier_insertion_v1(text, result.output_text, product_approved_carriers_v1()):
        return ProcessResult(text, 0)
    return ProcessResult(result.output_text, len(result.trace.operations))


def process_text(text: str) -> str:
    return transform_text(text).output_text


def read_pasted_text(input_stream: TextIO, output_stream: TextIO) -> str:
    output_stream.write("Paste text below. Finish with :done on its own line.\n\n")
    output_stream.flush()
    lines: list[str] = []
    for raw_line in input_stream:
        line = raw_line.rstrip("\r\n")
        if line.strip().casefold() in CLI_TERMINATORS:
            break
        lines.append(line)
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__project_name__,
        description="Apply FuckMark product-authorized invisible transforms without changing user-visible text.",
        epilog=(
            "Examples:\n"
            "  FuckMark\n"
            "  FuckMark --stdin < input.txt > output.txt\n"
            "  FuckMark input.txt --output output.txt\n"
            "  FuckMark input.txt --copy"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        metavar="FILE",
        help="read UTF-8 text from FILE; use - for standard input",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"{__project_name__} {__version__} "
            f"({RELEASE_CLI_ALGORITHM_VERSION}; {TRANSFORM_REGISTRY_ALGORITHM_VERSION})"
        ),
    )
    parser.add_argument(
        "--stdin",
        "--non-interactive",
        dest="stdin_mode",
        action="store_true",
        help="read standard input and write only transformed text to standard output",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="atomically write UTF-8 output to FILE instead of standard output",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="also copy the transformed text to the system clipboard",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="hide interactive status messages",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI color in interactive output",
    )
    return parser


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
                timeout=10,
            )
            return
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            failures.append(f"{executable}:{type(error).__name__}")
    detail = ", ".join(failures) if failures else "no supported clipboard command found"
    raise ClipboardUnavailableError(detail)


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _styled(text: str, code: str, *, enabled: bool) -> str:
    return f"{code}{text}{_ANSI_RESET}" if enabled else text


def _read_file(path_value: str) -> str:
    try:
        return Path(path_value).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read UTF-8 input file {path_value!r}: {error}") from error


def _same_path(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve(strict=False) == Path(right).expanduser().resolve(strict=False)


def _write_file_atomic(path_value: str, text: str) -> None:
    target = Path(path_value).expanduser()
    parent = target.parent
    if not parent.is_dir():
        raise ValueError(f"output directory does not exist: {parent}")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ValueError(f"cannot write output file {path_value!r}: {error}") from error


def _write_result(text: str, output_path: str | None, output_stream: TextIO) -> None:
    if output_path is None or output_path == "-":
        output_stream.write(text)
        output_stream.flush()
        return
    _write_file_atomic(output_path, text)


def _error(errors: TextIO, message: str) -> int:
    errors.write(f"FuckMark: {message}\n")
    errors.flush()
    return 1


def main(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    clipboard_writer: Callable[[str], None] | None = None,
    argv: Sequence[str] | None = None,
    error_stream: TextIO | None = None,
) -> int:
    parser_argv = argv
    injected = any(value is not None for value in (input_stream, output_stream, clipboard_writer, error_stream))
    if parser_argv is None and injected:
        parser_argv = ()
    arguments = _parser().parse_args(parser_argv)
    source = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output_stream is None else output_stream
    errors = sys.stderr if error_stream is None else error_stream

    if arguments.stdin_mode and arguments.input_file not in (None, "-"):
        return _error(errors, "FILE cannot be combined with --stdin")
    if (
        arguments.output not in (None, "-")
        and arguments.input_file not in (None, "-")
        and _same_path(arguments.input_file, arguments.output)
    ):
        return _error(errors, "input and output paths must be different")

    automatic_pipe = input_stream is None and not _is_tty(source)
    batch_mode = arguments.stdin_mode or arguments.input_file is not None or automatic_pipe
    interactive = not batch_mode
    color = interactive and _is_tty(output) and not arguments.no_color and "NO_COLOR" not in os.environ

    if interactive and not arguments.quiet:
        output.write(_styled(f"{__project_name__} {__version__}", _ANSI_BOLD + _ANSI_BLUE, enabled=color))
        output.write("\nProduct path: exact user-visible text preservation.\n\n")
        output.flush()

    try:
        if arguments.input_file not in (None, "-"):
            text = _read_file(arguments.input_file)
        elif batch_mode:
            text = source.read()
        else:
            text = read_pasted_text(source, output)
    except (OSError, UnicodeError, ValueError) as error:
        return _error(errors, str(error))

    if not text:
        return _error(errors, "no input text received")

    if interactive and not arguments.quiet:
        output.write(_styled("Processing...", _ANSI_BLUE, enabled=color) + "\n")
        output.flush()
    try:
        result = transform_text(text)
    except (KeyError, TypeError, ValueError) as error:
        return _error(errors, f"transformation failed: {error}")

    should_copy = arguments.copy
    copy_failed: Exception | None = None
    if should_copy:
        writer = copy_to_clipboard if clipboard_writer is None else clipboard_writer
        try:
            writer(result.output_text)
        except Exception as error:
            copy_failed = error

    try:
        if batch_mode or arguments.output is not None or copy_failed is not None or (interactive and not should_copy):
            _write_result(result.output_text, arguments.output, output)
            if interactive and (arguments.output is None or arguments.output == "-"):
                output.write("\n")
                output.flush()
    except ValueError as error:
        return _error(errors, str(error))

    if interactive and not arguments.quiet:
        if result.changed:
            noun = "change" if result.change_count == 1 else "changes"
            message = f"Done — {result.change_count} product-authorized invisible {noun} applied."
        else:
            message = "Done — no product-authorized invisible transform; visible text left unchanged."
        output.write(_styled(message, _ANSI_GREEN, enabled=color) + "\n")
        if arguments.output not in (None, "-"):
            output.write(f"Saved to {arguments.output}\n")
        if should_copy and copy_failed is None:
            output.write("Copied to clipboard.\n")
        output.flush()

    if copy_failed is not None:
        errors.write(
            _styled(
                f"FuckMark: clipboard copy failed: {copy_failed}",
                _ANSI_YELLOW,
                enabled=color,
            )
            + "\n"
        )
        errors.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
