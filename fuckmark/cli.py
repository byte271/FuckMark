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
from .cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from .product.domain import is_supported_product_domain_v1
from .product.encodings import require_supported_product_encoding
from .product.visible_projection import (
    is_carrier_insertion_v1,
    product_approved_carriers_v1,
    project_visible_v1,
)


INTERACTIVE_DONE = ":done"
RELEASE_CLI_ALGORITHM_VERSION = "release-cli-v5"
_ANSI_BLUE = "\033[38;5;39m"
_ANSI_GREEN = "\033[38;5;40m"
_ANSI_YELLOW = "\033[38;5;214m"
_ANSI_BOLD = "\033[1m"
_ANSI_RESET = "\033[0m"
_COPIED = "\u2713 Copied to clipboard"


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
    try:
        approved = product_approved_carriers_v1()
        if approved != frozenset(LETTER_MIX_APPROVED_CARRIERS):
            return ProcessResult(text, 0)
        if not is_supported_product_domain_v1(text):
            return ProcessResult(text, 0)
        if any(ord(character) in approved for character in text):
            return ProcessResult(text, 0)
        applied = apply_letter_alternating_mix(text)
        if applied == text:
            return ProcessResult(text, 0)
        if not is_carrier_insertion_v1(text, applied, approved):
            return ProcessResult(text, 0)
        if project_visible_v1(applied, approved) != text:
            return ProcessResult(text, 0)
        return ProcessResult(applied, len(applied) - len(text))
    except (KeyError, TypeError, ValueError, RuntimeError):
        return ProcessResult(text, 0)


def process_text(text: str) -> str:
    return transform_text(text).output_text


def read_interactive_text(input_stream: TextIO, ui_stream: TextIO, *, color: bool = False) -> list[str] | None:
    ui_stream.write(_styled("FuckMark", _ANSI_BOLD, enabled=color) + "\n")
    ui_stream.write(
        "\n"
        "Paste or type your text below.\n"
        "Enter :done on a new line when finished.\n"
        "\n"
    )
    ui_stream.flush()
    lines: list[str] = []
    while True:
        ui_stream.write("> ")
        ui_stream.flush()
        raw_line = input_stream.readline()
        if raw_line == "":
            return None
        line = raw_line.rstrip("\r\n")
        if line == INTERACTIVE_DONE:
            break
        lines.append(line)
    return lines


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark",
        description=(
            "FuckMark inserts hidden Unicode into ordinary English ASCII text "
            "without changing the visible words."
        ),
        epilog=(
            "With no arguments in a terminal, paste or type text and finish with a\n"
            "line that is only :done. Blank lines are kept. The result is copied to\n"
            "the clipboard and not printed.\n"
            "\n"
            "Examples:\n"
            "  fuckmark\n"
            "  printf 'I do not agree.\\n' | fuckmark\n"
            "  fuckmark \"I do not agree.\"\n"
            "  fuckmark notes.txt -o notes.fm.txt\n"
            "  fuckmark --stdin --copy < notes.txt\n"
            "  fuckmark --stdin --visible < notes.fm.txt\n"
            "\n"
            "Supported input: tab, newline, carriage return, and ASCII space through tilde.\n"
            "Other Unicode is returned unchanged. Only UTF-8 is supported.\n"
            "Visible text stays the same. Use --visible to print that visible text."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        nargs="?",
        metavar="TEXT_OR_FILE",
        help="quoted text or UTF-8 file; omit in a terminal to paste; - reads stdin",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{__project_name__} {__version__}",
    )
    parser.add_argument(
        "--stdin",
        "--non-interactive",
        dest="stdin_mode",
        action="store_true",
        help="read all of standard input",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="write UTF-8 output to FILE instead of standard output",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="copy output to the clipboard; the paste UI always copies",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="print the visible text (no hidden characters)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        metavar="NAME",
        help="output encoding; only utf-8 is supported (latin-1, ascii, and cp1252 are rejected)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="hide non-essential status messages",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable color on stderr",
    )
    return parser


def _looks_like_missing_file(value: str) -> bool:
    expanded = Path(value).expanduser()
    if expanded.exists():
        return False
    separators = [os.sep]
    if os.altsep:
        separators.append(os.altsep)
    if any(separator in value for separator in separators) or value.startswith("~"):
        return True
    suffix = expanded.suffix
    return len(suffix) >= 2


def _load_source_argument(value: str) -> str:
    expanded = Path(value).expanduser()
    if expanded.is_dir():
        raise ValueError(f"{value} is a directory. Pass a UTF-8 text file or quote the text.")
    if expanded.is_file():
        return _read_file(str(expanded))
    if _looks_like_missing_file(value):
        raise ValueError(
            f"file not found: {value}. Pass an existing UTF-8 file, or quote the text: fuckmark \"...\""
        )
    return value


def _clipboard_hint(*, tool_failed: bool) -> str:
    if sys.platform == "win32":
        return "Windows clip.exe could not receive the Unicode payload."
    if sys.platform == "darwin":
        return "macOS pbcopy is missing or failed."
    if tool_failed:
        return "A clipboard tool ran but failed. On a desktop session retry --copy."
    return "Install wl-copy, xclip, or xsel, then retry --copy."


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


def _clipboard_uses_utf16(command: tuple[str, ...]) -> bool:
    return Path(command[0]).name.casefold() in {"clip", "clip.exe"}


def copy_to_clipboard(text: str) -> None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    failures: list[str] = []
    for command in _clipboard_commands():
        executable = command[0]
        if shutil.which(executable) is None:
            continue
        try:
            if _clipboard_uses_utf16(command):
                subprocess.run(
                    command,
                    input=text.encode("utf-16"),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
            else:
                subprocess.run(
                    command,
                    input=text,
                    text=True,
                    encoding="utf-8",
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
            return
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, UnicodeError) as error:
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
    except UnicodeError as error:
        raise ValueError(f"cannot decode {path_value!r} as UTF-8: {error}") from error
    except OSError as error:
        raise ValueError(f"cannot read {path_value!r}: {error}") from error


def _same_path(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve(strict=False) == Path(right).expanduser().resolve(strict=False)


def _ensure_utf8(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    encoding = getattr(stream, "encoding", None)
    if isinstance(encoding, str) and encoding.replace("-", "").casefold() == "utf8":
        return
    try:
        reconfigure(encoding="utf-8", errors="strict")
    except (OSError, ValueError, AttributeError):
        return


def _write_stdout_utf8(output_stream: TextIO, text: str) -> None:
    try:
        output_stream.write(text)
        output_stream.flush()
        return
    except UnicodeError:
        pass
    buffer = getattr(output_stream, "buffer", None)
    if buffer is None:
        raise ValueError("standard output cannot encode UTF-8 product payload")
    try:
        output_stream.flush()
    except UnicodeError:
        pass
    buffer.write(text.encode("utf-8"))
    buffer.flush()


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
        _write_stdout_utf8(output_stream, text)
        return
    _write_file_atomic(output_path, text)


def _error(errors: TextIO, message: str) -> int:
    errors.write(f"FuckMark: {message}\n")
    errors.flush()
    return 1


def _status(errors: TextIO, message: str, *, enabled: bool, code: str) -> None:
    errors.write(_styled(message, code, enabled=enabled) + "\n")
    errors.flush()


def main(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    clipboard_writer: Callable[[str], None] | None = None,
    argv: Sequence[str] | None = None,
    error_stream: TextIO | None = None,
) -> int:
    source = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output_stream is None else output_stream
    errors = sys.stderr if error_stream is None else error_stream
    try:
        return _run(
            source,
            output,
            errors,
            clipboard_writer,
            argv,
            injected=any(
                value is not None
                for value in (input_stream, output_stream, clipboard_writer, error_stream)
            ),
        )
    except KeyboardInterrupt:
        try:
            errors.write("\n")
            errors.flush()
        except (OSError, UnicodeError, ValueError):
            pass
        return 130


def _run(
    source: TextIO,
    output: TextIO,
    errors: TextIO,
    clipboard_writer: Callable[[str], None] | None,
    argv: Sequence[str] | None,
    *,
    injected: bool,
) -> int:
    parser_argv = argv
    if parser_argv is None and injected:
        parser_argv = ()
    arguments = _parser().parse_args(parser_argv)
    _ensure_utf8(source)
    _ensure_utf8(output)
    _ensure_utf8(errors)

    try:
        require_supported_product_encoding(arguments.encoding)
    except ValueError:
        return _error(
            errors,
            "only UTF-8 is supported; latin-1, ascii, and cp1252 are rejected",
        )

    source_arg = arguments.source
    wants_stdin = arguments.stdin_mode or source_arg == "-"
    if wants_stdin and source_arg not in (None, "-"):
        return _error(errors, "pass quoted text, a file, or --stdin, not both")
    if (
        arguments.output not in (None, "-")
        and source_arg not in (None, "-")
        and Path(source_arg).expanduser().is_file()
        and _same_path(source_arg, arguments.output)
    ):
        return _error(errors, "input and output files must be different")

    literal_or_file = source_arg not in (None, "-") and not arguments.stdin_mode
    interactive = (not wants_stdin) and (not literal_or_file) and _is_tty(source)
    color = _is_tty(errors) and not arguments.no_color and "NO_COLOR" not in os.environ

    try:
        if literal_or_file:
            text = _load_source_argument(str(source_arg))
        elif interactive:
            captured = read_interactive_text(source, errors, color=color)
            if captured is None:
                return _error(errors, "ended without :done. Nothing copied.")
            if not captured:
                return _error(errors, "no input. Paste or type text, then :done.")
            text = "\n".join(captured)
        else:
            text = source.read()
    except UnicodeError:
        return _error(errors, "input is not valid UTF-8. Only UTF-8 is supported.")
    except (OSError, ValueError) as error:
        return _error(errors, str(error))

    if not interactive and not text:
        return _error(
            errors,
            "no input. Pipe text, pass a file, or quote a string. Example: printf 'I do not agree.\\n' | fuckmark",
        )

    if interactive:
        _status(errors, "Processing...", enabled=color, code=_ANSI_BLUE)
    try:
        result = transform_text(text)
    except (KeyError, TypeError, ValueError) as error:
        return _error(errors, f"could not transform the text: {error}")

    output_text = result.output_text
    if arguments.visible:
        output_text = project_visible_v1(output_text, product_approved_carriers_v1())

    should_copy = arguments.copy or interactive
    copy_failed: Exception | None = None
    if should_copy:
        writer = copy_to_clipboard if clipboard_writer is None else clipboard_writer
        try:
            writer(output_text)
        except Exception as error:
            copy_failed = error

    wrote_payload = False
    if (not interactive) or arguments.output not in (None, "-"):
        try:
            _write_result(output_text, arguments.output, output)
            wrote_payload = True
        except ValueError as error:
            return _error(errors, str(error))

    if interactive and copy_failed is None:
        _status(errors, _COPIED, enabled=color, code=_ANSI_GREEN)

    if copy_failed is not None:
        tool_failed = "no supported clipboard command found" not in str(copy_failed)
        if wrote_payload:
            follow = "The transformed text was still written."
        else:
            follow = (
                "Nothing was printed. Pipe text if you need stdout: "
                "printf 'I do not agree.\\n' | fuckmark"
            )
        _status(
            errors,
            f"FuckMark: clipboard copy failed ({copy_failed}). {_clipboard_hint(tool_failed=tool_failed)} "
            f"{follow}",
            enabled=color,
            code=_ANSI_YELLOW,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
