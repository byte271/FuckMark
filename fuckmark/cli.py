from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from . import __project_name__, __version__
from .cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    LETTER_MIX_MAX_SELECTED,
    compose_letter_mix,
    select_letter_mix_sites,
)
from .product.domain import (
    PRODUCT_MAX_INPUT_CHARS,
    first_unsupported_product_domain_v1,
    is_supported_product_domain_v1,
)
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


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_CLIPBOARD = 3
EXIT_INTERNAL = 4
EXIT_INTERRUPT = 130
REASON_TRANSFORMED = "transformed"
REASON_SITE_CAP = "site-cap"
REASON_UNSUPPORTED_DOMAIN = "unsupported-domain"
REASON_ALREADY_TRANSFORMED = "already-transformed"
REASON_NO_ELIGIBLE_SITES = "no-eligible-sites"
REASON_INTERNAL_ERROR = "internal-error"
REASON_TOO_LARGE = "too-large"


@dataclass(frozen=True, slots=True)
class ProcessResult:
    output_text: str
    change_count: int
    reason: str = REASON_TRANSFORMED
    last_source_index: int | None = None
    site_count: int = 0
    capped: bool = False
    source_length: int = 0
    first_unsupported: str = ""

    @property
    def changed(self) -> bool:
        return self.change_count > 0

    @property
    def processed(self) -> bool:
        return self.change_count > 0


def _unsupported_token(text: str) -> str:
    found = first_unsupported_product_domain_v1(text)
    if found is None:
        return ""
    return f"U+{found[1]:04X}@{found[0]}"


def _unchanged(text: str, reason: str) -> ProcessResult:
    token = _unsupported_token(text) if reason == REASON_UNSUPPORTED_DOMAIN else ""
    return ProcessResult(
        text,
        0,
        reason=reason,
        source_length=len(text),
        first_unsupported=token,
    )


def transform_text(text: str) -> ProcessResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    try:
        if len(text) > PRODUCT_MAX_INPUT_CHARS:
            return _unchanged(text, REASON_TOO_LARGE)
        approved = product_approved_carriers_v1()
        if approved != frozenset(LETTER_MIX_APPROVED_CARRIERS):
            return _unchanged(text, REASON_INTERNAL_ERROR)
        if any(ord(character) in approved for character in text):
            return _unchanged(text, REASON_ALREADY_TRANSFORMED)
        if not is_supported_product_domain_v1(text):
            return _unchanged(text, REASON_UNSUPPORTED_DOMAIN)
        probe = select_letter_mix_sites(text, max_selected=LETTER_MIX_MAX_SELECTED + 1)
        capped = len(probe) > LETTER_MIX_MAX_SELECTED
        sites = probe[:LETTER_MIX_MAX_SELECTED]
        if not sites:
            return _unchanged(text, REASON_NO_ELIGIBLE_SITES)
        applied = compose_letter_mix(text, sites)
        if applied == text:
            return _unchanged(text, REASON_NO_ELIGIBLE_SITES)
        if not is_carrier_insertion_v1(text, applied, approved):
            return _unchanged(text, REASON_INTERNAL_ERROR)
        if project_visible_v1(applied, approved) != text:
            return _unchanged(text, REASON_INTERNAL_ERROR)
        reason = REASON_SITE_CAP if capped else REASON_TRANSFORMED
        return ProcessResult(
            applied,
            len(applied) - len(text),
            reason=reason,
            last_source_index=sites[-1],
            site_count=len(sites),
            capped=capped,
            source_length=len(text),
        )
    except (KeyError, TypeError, ValueError, RuntimeError):
        return _unchanged(text, REASON_INTERNAL_ERROR)


def process_text(text: str) -> str:
    return transform_text(text).output_text


def read_interactive_text(input_stream: TextIO, ui_stream: TextIO, *, color: bool = False) -> list[str] | None:
    ui_stream.write(_styled("FuckMark", _ANSI_BOLD, enabled=color) + "\n")
    ui_stream.write(
        "\n"
        "Paste or type your text below.\n"
        "English ASCII only. Curly apostrophes, accents, and emoji are not processed.\n"
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
            "  fuckmark --text \"I do not agree.\"\n"
            "  fuckmark \"I do not agree.\"\n"
            "  fuckmark --text \"I agree. You are right\"\n"
            "  fuckmark --file notes.txt -o notes.fm.txt\n"
            "  fuckmark notes.txt -o notes.fm.txt\n"
            "  fuckmark --stdin --copy < notes.txt\n"
            "  fuckmark --stdin --visible < notes.fm.txt\n"
            "\n"
            "Supported input: tab, newline, carriage return, and ASCII space through tilde.\n"
            "Other Unicode (including curly apostrophes) is returned unchanged with exit 0.\n"
            "Exit 0 means I/O succeeded, not that hidden characters were inserted.\n"
            "Only UTF-8 is supported. Visible text stays the same.\n"
            "Use --visible to print that visible text.\n"
            "Use --text for literal strings and --file for existing UTF-8 files.\n"
            "By default, stderr reports processed vs not processed, reason,\n"
            "insertions, sites, last_index, source_length, and capped. Use -q to hide that.\n"
            "Use --status for a machine-readable outcome line on stderr.\n"
            "Use --inspect for a character-level insertion map on stderr.\n"
            "Stripping combining marks or default-ignorable characters restores the source."
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
        "--text",
        dest="text_literal",
        metavar="TEXT",
        help="transform TEXT as a literal string (not a filename)",
    )
    parser.add_argument(
        "--file",
        dest="file_explicit",
        metavar="FILE",
        help="read UTF-8 bytes from FILE without newline conversion",
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
        help="hide processed/reason/coverage status messages on stderr",
    )
    parser.add_argument(
        "--status",
        dest="status_report",
        action="store_true",
        help="write a machine-readable outcome line to stderr",
    )
    parser.add_argument(
        "--inspect",
        dest="inspect_report",
        action="store_true",
        help="write a character-level coverage map to stderr; stdout stays the payload",
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
    if " " in suffix or "\t" in suffix:
        return False
    return re.fullmatch(r"\.[A-Za-z][A-Za-z0-9]{0,11}", suffix) is not None


def _load_source_argument(value: str) -> str:
    expanded = Path(value).expanduser()
    if expanded.is_dir():
        raise ValueError(f"{value} is a directory. Pass a UTF-8 text file or --text.")
    if expanded.is_file():
        return _read_file(str(expanded))
    if _looks_like_missing_file(value):
        raise ValueError(
            f"file not found: {value}. Pass an existing UTF-8 file with --file, or a literal string with --text."
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


def _decode_utf8_bytes(data: bytes, origin: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{origin} is not valid UTF-8. Only UTF-8 is supported.") from error
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        raise ValueError(f"{origin} is not valid UTF-8. Only UTF-8 is supported.")
    return text


def _read_file(path_value: str) -> str:
    path = Path(path_value).expanduser()
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read {path_value!r}: {error}") from error
    return _decode_utf8_bytes(data, path_value)


def _read_stream_text(source: TextIO) -> str:
    buffer = getattr(source, "buffer", None)
    if buffer is not None:
        return _decode_utf8_bytes(buffer.read(), "input")
    text = source.read()
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        raise ValueError("input is not valid UTF-8. Only UTF-8 is supported.")
    return text


def _same_path(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve(strict=False) == Path(right).expanduser().resolve(strict=False)


def _ensure_utf8(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="strict", newline="")
    except (OSError, ValueError, AttributeError, TypeError):
        try:
            reconfigure(encoding="utf-8", errors="strict")
        except (OSError, ValueError, AttributeError):
            return


def _abandon_stdio(stream: TextIO) -> None:
    try:
        handle = stream.fileno()
    except (OSError, ValueError, AttributeError):
        return
    try:
        stream.flush()
    except (OSError, ValueError, UnicodeError, BrokenPipeError):
        pass
    try:
        null_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null_fd, handle)
        finally:
            os.close(null_fd)
    except OSError:
        pass
    try:
        stream.close()
    except (OSError, ValueError):
        pass


def _write_stdout_utf8(output_stream: TextIO, text: str) -> None:
    buffer = getattr(output_stream, "buffer", None)
    try:
        if buffer is not None:
            try:
                output_stream.flush()
            except UnicodeError:
                pass
            buffer.write(text.encode("utf-8"))
            buffer.flush()
            return
        output_stream.write(text)
        output_stream.flush()
    except BrokenPipeError as error:
        _abandon_stdio(output_stream)
        raise ValueError("standard output pipe closed") from error
    except OSError as error:
        _abandon_stdio(output_stream)
        detail = getattr(error, "strerror", None) or str(error)
        raise ValueError(f"cannot write standard output: {detail}") from error
    except UnicodeError as error:
        raise ValueError("standard output cannot encode UTF-8 product payload") from error


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


def _human_reason(result: ProcessResult) -> str:
    if result.reason == REASON_TRANSFORMED:
        return f"processed: inserted {result.change_count} hidden characters"
    if result.reason == REASON_SITE_CAP:
        return (
            f"processed with coverage limit: inserted {result.change_count} hidden characters, "
            f"then stopped at the {LETTER_MIX_MAX_SELECTED}-site cap; trailing text is unchanged"
        )
    if result.reason == REASON_UNSUPPORTED_DOMAIN:
        loc = result.first_unsupported or "non-ASCII"
        note = (
            f"not processed: unsupported Unicode ({loc}). "
            "Accents, emoji, CJK, and curly quotes disable the whole input"
        )
        if result.first_unsupported.startswith("U+2019@"):
            note += (
                ". English curly apostrophes are not ASCII, so a sentence such as "
                "I don\u2019t agree. is returned unchanged"
            )
        note += (
            ". Exit 0 means I/O succeeded, not that hidden characters were inserted"
        )
        return note
    if result.reason == REASON_ALREADY_TRANSFORMED:
        return "not processed: input already contains the payload"
    if result.reason == REASON_NO_ELIGIBLE_SITES:
        return "not processed: no eligible ASCII letter sites"
    if result.reason == REASON_TOO_LARGE:
        return f"not processed: input is too large (max {PRODUCT_MAX_INPUT_CHARS} characters)"
    return "not processed: transformation failed internally; source returned unchanged"


def _coverage_line(result: ProcessResult) -> str:
    last = "" if result.last_source_index is None else str(result.last_source_index)
    capped = "yes" if result.capped else "no"
    processed = "yes" if result.processed else "no"
    return (
        f"processed={processed} reason={result.reason} "
        f"insertions={result.change_count} sites={result.site_count} "
        f"last_index={last} source_length={result.source_length} capped={capped}"
    )


def _machine_status_line(result: ProcessResult) -> str:
    last = "" if result.last_source_index is None else str(result.last_source_index)
    capped = "yes" if result.capped else "no"
    processed = "yes" if result.processed else "no"
    unsupported = result.first_unsupported
    return (
        "fuckmark-status "
        f"result={result.reason} processed={processed} insertions={result.change_count} "
        f"sites={result.site_count} last_index={last} "
        f"source_length={result.source_length} capped={capped} "
        f"first_unsupported={unsupported}"
    )


def _inspect_map(result: ProcessResult) -> str:
    pieces: list[str] = []
    for character in result.output_text:
        codepoint = ord(character)
        if codepoint == 0x034F:
            pieces.append("[U+034F]")
        elif codepoint == 0xFE00:
            pieces.append("[U+FE00]")
        elif character == "\n":
            pieces.append("\\n")
        elif character == "\r":
            pieces.append("\\r")
        elif character == "\t":
            pieces.append("\\t")
        else:
            pieces.append(character)
    blob = "".join(pieces)
    if len(blob) > 8000:
        return blob[:8000] + "..."
    return blob


def _emit_inspect(errors: TextIO, result: ProcessResult) -> None:
    errors.write(f"fuckmark-inspect {_coverage_line(result)}\n")
    if result.first_unsupported:
        errors.write(f"fuckmark-inspect-unsupported {result.first_unsupported}\n")
    if result.change_count > 0:
        errors.write(f"fuckmark-inspect-map {_inspect_map(result)}\n")
        errors.write(
            "fuckmark-inspect-note stripping combining marks or "
            "default-ignorable characters restores the source\n"
        )
    elif result.reason == REASON_UNSUPPORTED_DOMAIN:
        errors.write(
            "fuckmark-inspect-note the whole input is returned unchanged; "
            "exit 0 is not proof of insertion\n"
        )
    errors.flush()


def _emit_outcome(
    errors: TextIO,
    result: ProcessResult,
    *,
    interactive: bool,
    quiet: bool,
    status_report: bool,
    inspect_report: bool,
    color: bool,
) -> None:
    if status_report:
        errors.write(_machine_status_line(result) + "\n")
        errors.flush()
    if inspect_report:
        _emit_inspect(errors, result)
    if result.reason == REASON_INTERNAL_ERROR or result.reason == REASON_TOO_LARGE:
        return
    if quiet:
        return
    warn = result.reason != REASON_TRANSFORMED and result.reason != REASON_SITE_CAP
    code = _ANSI_YELLOW if warn else _ANSI_GREEN
    _status(errors, f"FuckMark: {_human_reason(result)}.", enabled=color, code=code)
    _status(errors, f"FuckMark: {_coverage_line(result)}.", enabled=color, code=code)
    if result.change_count > 0:
        _status(
            errors,
            "FuckMark: stripping combining marks or default-ignorable characters restores the source.",
            enabled=color,
            code=_ANSI_YELLOW,
        )


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
    except BrokenPipeError:
        try:
            errors.write("FuckMark: standard output pipe closed\n")
            errors.flush()
        except (OSError, UnicodeError, ValueError, BrokenPipeError):
            pass
        _abandon_stdio(output)
        return EXIT_ERROR
    except KeyboardInterrupt:
        try:
            errors.write("\n")
            errors.flush()
        except (OSError, UnicodeError, ValueError, BrokenPipeError):
            pass
        return EXIT_INTERRUPT
    except OSError as error:
        try:
            detail = getattr(error, "strerror", None) or str(error)
            errors.write(f"FuckMark: cannot write standard output: {detail}\n")
            errors.flush()
        except (OSError, UnicodeError, ValueError, BrokenPipeError):
            pass
        _abandon_stdio(output)
        return EXIT_ERROR


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
    text_literal = arguments.text_literal
    file_explicit = arguments.file_explicit
    wants_stdin = arguments.stdin_mode or source_arg == "-"
    if text_literal is not None and file_explicit is not None:
        return _error(errors, "pass --text or --file, not both")
    if wants_stdin and (text_literal is not None or file_explicit is not None):
        return _error(errors, "pass --text, --file, or --stdin, not both")
    if wants_stdin and source_arg not in (None, "-"):
        return _error(errors, "pass quoted text, a file, or --stdin, not both")
    if text_literal is not None and source_arg is not None:
        return _error(errors, "pass --text or a positional operand, not both")
    if file_explicit is not None and source_arg is not None:
        return _error(errors, "pass --file or a positional operand, not both")
    file_for_overwrite = file_explicit if file_explicit is not None else source_arg
    if (
        arguments.output not in (None, "-")
        and file_for_overwrite not in (None, "-")
        and Path(str(file_for_overwrite)).expanduser().is_file()
        and _same_path(str(file_for_overwrite), arguments.output)
    ):
        return _error(errors, "input and output files must be different")

    literal_or_file = (
        text_literal is not None
        or file_explicit is not None
        or (source_arg not in (None, "-") and not arguments.stdin_mode)
    )
    interactive = (not wants_stdin) and (not literal_or_file) and _is_tty(source)
    color = _is_tty(errors) and not arguments.no_color and "NO_COLOR" not in os.environ

    try:
        if text_literal is not None:
            text = text_literal
        elif file_explicit is not None:
            expanded = Path(file_explicit).expanduser()
            if expanded.is_dir():
                raise ValueError(f"{file_explicit} is a directory. Pass a UTF-8 text file.")
            if not expanded.is_file():
                raise ValueError(f"file not found: {file_explicit}")
            text = _read_file(str(expanded))
        elif literal_or_file:
            text = _load_source_argument(str(source_arg))
        elif interactive:
            captured = read_interactive_text(source, errors, color=color)
            if captured is None:
                return _error(errors, "ended without :done. Nothing copied.")
            if not captured:
                return _error(errors, "no input. Paste or type text, then :done.")
            text = "\n".join(captured)
        else:
            text = _read_stream_text(source)
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

    if result.reason == REASON_TOO_LARGE:
        _emit_outcome(
            errors,
            result,
            interactive=interactive,
            quiet=arguments.quiet,
            status_report=arguments.status_report,
            inspect_report=arguments.inspect_report,
            color=color,
        )
        return _error(errors, _human_reason(result))
    if result.reason == REASON_INTERNAL_ERROR:
        _emit_outcome(
            errors,
            result,
            interactive=interactive,
            quiet=arguments.quiet,
            status_report=arguments.status_report,
            inspect_report=arguments.inspect_report,
            color=color,
        )
        _error(errors, _human_reason(result))
        return EXIT_INTERNAL

    output_text = result.output_text
    if arguments.visible:
        output_text = project_visible_v1(output_text, product_approved_carriers_v1())

    wrote_payload = False
    if (not interactive) or arguments.output not in (None, "-"):
        try:
            _write_result(output_text, arguments.output, output)
            wrote_payload = True
        except (ValueError, OSError) as error:
            return _error(errors, str(error))

    should_copy = arguments.copy or interactive
    copy_failed: Exception | None = None
    if should_copy:
        writer = copy_to_clipboard if clipboard_writer is None else clipboard_writer
        try:
            writer(output_text)
        except Exception as error:
            copy_failed = error

    if interactive and copy_failed is None:
        _status(errors, _COPIED, enabled=color, code=_ANSI_GREEN)

    _emit_outcome(
        errors,
        result,
        interactive=interactive,
        quiet=arguments.quiet,
        status_report=arguments.status_report,
        inspect_report=arguments.inspect_report,
        color=color,
    )

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
        return EXIT_CLIPBOARD
    return EXIT_OK


if __name__ == "__main__":
    status = EXIT_ERROR
    try:
        status = main()
    except SystemExit as error:
        code = error.code
        if code is None:
            status = EXIT_OK
        elif isinstance(code, int):
            status = code
        else:
            status = EXIT_ERROR
    except BrokenPipeError:
        status = EXIT_ERROR
    except KeyboardInterrupt:
        status = EXIT_INTERRUPT
    except OSError:
        status = EXIT_ERROR
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError, BrokenPipeError):
            pass
    _abandon_stdio(sys.stdout)
    os._exit(status)
