from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from .config import json_utf8_text
from .product.scan import (
    SCAN_CATEGORIES,
    SECURITY_SCAN_CATEGORIES,
    HiddenFinding,
    ScanResult,
    normalize_scan_categories,
    scan_dict,
    scan_hidden_characters,
    scan_human_report,
    scan_machine_line,
)


CLIPBOARD_EXIT_OK = 0
CLIPBOARD_EXIT_FINDINGS = 1
CLIPBOARD_EXIT_USAGE = 2
CLIPBOARD_EXIT_UNAVAILABLE = 3
WATCH_ALGORITHM_VERSION = "fuckmark-clipboard-watch-v1"
DEFAULT_INTERVAL_SECONDS = 0.5
_ZWJ = 0x200D
_SEVERITY_RANK = {"info": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True, slots=True)
class ClipboardSnapshot:
    text: str
    digest: str


@dataclass(frozen=True, slots=True)
class ClipboardAlert:
    result: ScanResult
    cleaned: str
    removed: int


class ClipboardUnavailableError(RuntimeError):
    pass


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def snapshot_text(text: str) -> ClipboardSnapshot:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return ClipboardSnapshot(text=text, digest=_digest(text))


def _read_commands() -> tuple[tuple[str, ...], ...]:
    if sys.platform == "darwin":
        return (("pbpaste",),)
    if sys.platform == "win32":
        return (
            ("powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"),
            ("powershell.exe", "-NoProfile", "-Command", "Get-Clipboard -Raw"),
        )
    return (
        ("wl-paste",),
        ("xclip", "-selection", "clipboard", "-o"),
        ("xsel", "--clipboard", "--output"),
    )


def _decode_clipboard_bytes(raw: bytes, *, utf16_le_without_bom: bool = False) -> str:
    if not raw:
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError as error:
            raise ClipboardUnavailableError("clipboard bytes were not valid UTF-8 or UTF-16") from error
    try:
        utf8_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_text = None
    if utf16_le_without_bom and b"\x00" in raw and len(raw) % 2 == 0:
        try:
            utf16_le = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            utf16_le = None
        else:
            if "\x00" not in utf16_le:
                return utf16_le
    if utf8_text is not None:
        return utf8_text
    for encoding in ("utf-16", "utf-16-le"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ClipboardUnavailableError("clipboard bytes were not valid UTF-8 or UTF-16")


def read_clipboard() -> str:
    failures: list[str] = []
    for command in _read_commands():
        executable = command[0]
        if shutil.which(executable) is None:
            continue
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=10,
            )
            name = executable.replace("\\", "/").rsplit("/", 1)[-1].casefold()
            return _decode_clipboard_bytes(
                completed.stdout,
                utf16_le_without_bom=name in {"powershell", "powershell.exe"},
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, UnicodeError) as error:
            failures.append(f"{executable}:{type(error).__name__}")
    detail = ", ".join(failures) if failures else "no supported clipboard read command found"
    raise ClipboardUnavailableError(detail)


def write_clipboard(text: str) -> None:
    from .cli import ClipboardUnavailableError as WriteError
    from .cli import copy_to_clipboard

    try:
        copy_to_clipboard(text)
    except WriteError as error:
        raise ClipboardUnavailableError(str(error)) from error


def _is_emoji_neighbor(codepoint: int) -> bool:
    if codepoint < 0 or codepoint == _ZWJ:
        return False
    if 0xFE00 <= codepoint <= 0xFE0F:
        return True
    if 0xE0100 <= codepoint <= 0xE01EF:
        return True
    if 0x1F1E6 <= codepoint <= 0x1F1FF:
        return True
    if 0x1F000 <= codepoint <= 0x1FAFF:
        return True
    if 0x2600 <= codepoint <= 0x27BF:
        return True
    return codepoint in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}


def _keep_emoji_joiner(text: str, index: int, codepoint: int) -> bool:
    if codepoint != _ZWJ:
        return False
    prev = ord(text[index - 1]) if index > 0 else -1
    nxt = ord(text[index + 1]) if index + 1 < len(text) else -1
    return _is_emoji_neighbor(prev) and _is_emoji_neighbor(nxt)


def _keep_finding(text: str, finding: HiddenFinding) -> bool:
    if finding.category == "zero_width" and _keep_emoji_joiner(text, finding.index, finding.codepoint):
        return True
    return finding.category == "variation_selector" and finding.severity == "info"


def _scan_all(text: str) -> ScanResult:
    return scan_hidden_characters(text, max_findings=max(len(text), 1))


def clean_clipboard_text(text: str, *, categories: frozenset[str] | None = None) -> tuple[str, int, ScanResult]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    selected = frozenset(SECURITY_SCAN_CATEGORIES) if categories is None else categories
    result = _scan_all(text)
    drop: set[int] = set()
    for finding in result.findings:
        if finding.category not in selected:
            continue
        if _keep_finding(text, finding):
            continue
        drop.add(finding.index)
    cleaned = "".join(character for index, character in enumerate(text) if index not in drop)
    return cleaned, len(drop), result


def evaluate_clipboard_text(text: str, *, categories: frozenset[str] | None = None) -> ClipboardAlert:
    selected = frozenset(SECURITY_SCAN_CATEGORIES) if categories is None else categories
    cleaned, removed, full = clean_clipboard_text(text, categories=selected)
    findings = tuple(
        finding
        for finding in full.findings
        if finding.category in selected and not _keep_finding(text, finding)
    )
    counts: dict[str, int] = {}
    peak = ""
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
        if _SEVERITY_RANK.get(finding.severity, -1) > _SEVERITY_RANK.get(peak, -1):
            peak = finding.severity
    filtered = ScanResult(
        source_length=full.source_length,
        total=sum(counts.values()),
        counts=counts,
        findings=findings,
        truncated=False,
        fuckmark_carriers=full.fuckmark_carriers,
        highest_severity=peak,
    )
    return ClipboardAlert(result=filtered, cleaned=cleaned, removed=removed)


def watch_clipboard(
    *,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    clean: bool = False,
    exit_on_find: bool = False,
    max_seconds: float | None = None,
    categories: frozenset[str] | None = None,
    reader: Callable[[], str] | None = None,
    writer: Callable[[str], None] | None = None,
    sleeper: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
    on_alert: Callable[[ClipboardAlert, ClipboardSnapshot], None] | None = None,
    on_clean: Callable[[ClipboardAlert, ClipboardSnapshot], None] | None = None,
) -> int:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if max_seconds is not None and max_seconds < 0:
        raise ValueError("max_seconds must not be negative")
    read = reader or read_clipboard
    write = writer or write_clipboard
    sleep = sleeper or time.sleep
    now = clock or time.monotonic
    started = now()
    last_digest = ""
    while True:
        text = read()
        snap = snapshot_text(text)
        if snap.digest != last_digest:
            last_digest = snap.digest
            alert = evaluate_clipboard_text(snap.text, categories=categories)
            if alert.result.detected:
                if on_alert is not None:
                    on_alert(alert, snap)
                if clean and alert.removed:
                    latest = snapshot_text(read())
                    if latest.digest != snap.digest:
                        last_digest = ""
                        continue
                    write(alert.cleaned)
                    last_digest = snapshot_text(alert.cleaned).digest
                    if on_clean is not None:
                        on_clean(alert, snap)
                if exit_on_find or once:
                    return CLIPBOARD_EXIT_FINDINGS
            elif once:
                return CLIPBOARD_EXIT_OK
        if once:
            return CLIPBOARD_EXIT_OK
        if max_seconds is not None and (now() - started) >= max_seconds:
            return CLIPBOARD_EXIT_OK
        sleep(interval_seconds)


def _resolve_categories(select: str) -> frozenset[str]:
    if select.strip().casefold() == "all":
        return frozenset(SCAN_CATEGORIES)
    names = [item.strip() for item in select.split(",") if item.strip()]
    if not names:
        raise ValueError("no categories selected")
    return normalize_scan_categories(names)


def _clipboard_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark clipboard",
        description=(
            "Watch or scan the OS clipboard for hidden Unicode "
            "(Trojan Source bidi, zero-width, tag smuggling)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan the current clipboard once")
    scan.add_argument("--json", action="store_true", dest="json_mode")
    scan.add_argument("-q", "--quiet", action="store_true")
    scan.add_argument(
        "--select",
        default="security",
        help="comma-separated categories, 'security' (default), or 'all'",
    )
    clean = sub.add_parser("clean", help="strip hidden Unicode from the clipboard in place")
    clean.add_argument("--json", action="store_true", dest="json_mode")
    clean.add_argument("-q", "--quiet", action="store_true")
    clean.add_argument("--select", default="security")
    watch = sub.add_parser("watch", help="poll the clipboard and warn on new hidden payloads")
    watch.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    watch.add_argument("--once", action="store_true", help="poll once then exit")
    watch.add_argument("--clean", action="store_true", help="rewrite the clipboard when findings appear")
    watch.add_argument("--exit-on-find", action="store_true")
    watch.add_argument("--max-seconds", type=float, default=None)
    watch.add_argument("--json", action="store_true", dest="json_mode")
    watch.add_argument("-q", "--quiet", action="store_true")
    watch.add_argument("--select", default="security")
    return parser


def _categories_from_select(select: str) -> frozenset[str]:
    key = select.strip().casefold()
    if key in {"", "security", "default"}:
        return frozenset(SECURITY_SCAN_CATEGORIES)
    return _resolve_categories(select)


def _emit(stream: TextIO, text: str) -> None:
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")
    stream.flush()


def _report_alert(
    alert: ClipboardAlert,
    *,
    output: TextIO,
    errors: TextIO,
    json_mode: bool,
    quiet: bool,
    action: str,
) -> None:
    payload = {
        "algorithm_version": WATCH_ALGORITHM_VERSION,
        "action": action,
        "removed": alert.removed,
        "scan": scan_dict(alert.result),
    }
    if json_mode:
        _emit(output, json_utf8_text(payload))
        return
    if quiet:
        _emit(output, scan_machine_line(alert.result).rstrip("\n"))
        return
    _emit(errors, scan_human_report(alert.result).rstrip("\n"))
    if action == "cleaned":
        _emit(errors, f"FuckMark clipboard: stripped {alert.removed} hidden characters from the clipboard.")
    elif alert.result.detected:
        _emit(errors, "FuckMark clipboard: hidden Unicode detected in clipboard contents.")


def run_clipboard_argv(argv: list[str], output: TextIO, errors: TextIO) -> int:
    try:
        arguments = _clipboard_parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return CLIPBOARD_EXIT_OK
        return int(code) if isinstance(code, int) else CLIPBOARD_EXIT_USAGE
    try:
        categories = _categories_from_select(arguments.select)
    except ValueError as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return CLIPBOARD_EXIT_USAGE
    command = arguments.command
    if command == "scan":
        try:
            text = read_clipboard()
        except ClipboardUnavailableError as error:
            errors.write(f"FuckMark: clipboard unavailable ({error})\n")
            errors.flush()
            return CLIPBOARD_EXIT_UNAVAILABLE
        alert = evaluate_clipboard_text(text, categories=categories)
        _report_alert(
            alert,
            output=output,
            errors=errors,
            json_mode=arguments.json_mode,
            quiet=arguments.quiet,
            action="scan",
        )
        return CLIPBOARD_EXIT_FINDINGS if alert.result.detected else CLIPBOARD_EXIT_OK
    if command == "clean":
        try:
            text = read_clipboard()
        except ClipboardUnavailableError as error:
            errors.write(f"FuckMark: clipboard unavailable ({error})\n")
            errors.flush()
            return CLIPBOARD_EXIT_UNAVAILABLE
        alert = evaluate_clipboard_text(text, categories=categories)
        if alert.removed:
            try:
                write_clipboard(alert.cleaned)
            except ClipboardUnavailableError as error:
                errors.write(f"FuckMark: clipboard write failed ({error})\n")
                errors.flush()
                return CLIPBOARD_EXIT_UNAVAILABLE
        _report_alert(
            alert,
            output=output,
            errors=errors,
            json_mode=arguments.json_mode,
            quiet=arguments.quiet,
            action="cleaned" if alert.removed else "scan",
        )
        return CLIPBOARD_EXIT_FINDINGS if alert.result.detected else CLIPBOARD_EXIT_OK
    if command == "watch":
        if arguments.interval <= 0:
            errors.write("FuckMark: --interval must be positive\n")
            errors.flush()
            return CLIPBOARD_EXIT_USAGE
        if arguments.max_seconds is not None and arguments.max_seconds < 0:
            errors.write("FuckMark: --max-seconds must not be negative\n")
            errors.flush()
            return CLIPBOARD_EXIT_USAGE
        if not arguments.quiet and not arguments.json_mode and not arguments.once:
            _emit(errors, "FuckMark clipboard: watching for hidden Unicode. Ctrl+C to stop.")

        def on_alert(alert: ClipboardAlert, _snap: ClipboardSnapshot) -> None:
            _report_alert(
                alert,
                output=output,
                errors=errors,
                json_mode=arguments.json_mode,
                quiet=arguments.quiet,
                action="watch",
            )

        def on_clean(alert: ClipboardAlert, _snap: ClipboardSnapshot) -> None:
            if arguments.json_mode or arguments.quiet:
                return
            _emit(
                errors,
                f"FuckMark clipboard: stripped {alert.removed} hidden characters from the clipboard.",
            )

        try:
            return watch_clipboard(
                interval_seconds=arguments.interval,
                once=arguments.once,
                clean=arguments.clean,
                exit_on_find=arguments.exit_on_find,
                max_seconds=arguments.max_seconds,
                categories=categories,
                on_alert=on_alert,
                on_clean=on_clean,
            )
        except ClipboardUnavailableError as error:
            errors.write(f"FuckMark: clipboard unavailable ({error})\n")
            errors.flush()
            return CLIPBOARD_EXIT_UNAVAILABLE
        except ValueError as error:
            errors.write(f"FuckMark: {error}\n")
            errors.flush()
            return CLIPBOARD_EXIT_USAGE
        except KeyboardInterrupt:
            errors.write("\n")
            errors.flush()
            return CLIPBOARD_EXIT_OK
    errors.write("FuckMark: unknown clipboard command\n")
    errors.flush()
    return CLIPBOARD_EXIT_USAGE
