from __future__ import annotations

import argparse
import functools
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TextIO

from .hashing import sha256_json, sha256_text
from .product.domain import PRODUCT_MAX_INPUT_CHARS
from .product.scan import (
    SECURITY_SCAN_CATEGORIES,
    clean_hidden_characters,
    decode_hidden_scan_bytes,
    extract_tag_payload,
    normalize_scan_categories,
    scan_hidden_characters,
)


GUARD_ALGORITHM_VERSION = "fuckmark-guard-v1"
ON_FINDINGS_STRIP = "strip"
ON_FINDINGS_REFUSE = "refuse"
ON_FINDINGS_REPORT = "report"
ON_FINDINGS_CHOICES = (ON_FINDINGS_STRIP, ON_FINDINGS_REFUSE, ON_FINDINGS_REPORT)
GUARD_EXIT_OK = 0
GUARD_EXIT_FINDINGS = 1
GUARD_EXIT_USAGE = 2


class HiddenTextRefused(ValueError):
    def __init__(self, receipt: "GuardReceipt") -> None:
        self.receipt = receipt
        super().__init__(
            "hidden Unicode refused: "
            f"{receipt.total} character(s) across {len(receipt.counts)} categor"
            f"{'y' if len(receipt.counts) == 1 else 'ies'}"
        )


@dataclass(frozen=True, slots=True)
class GuardHit:
    path: str
    total: int
    counts: dict[str, int]
    first: str
    tag_payload: str


@dataclass(frozen=True, slots=True)
class GuardReceipt:
    action: str
    total: int
    removed: int
    counts: dict[str, int]
    hits: tuple[GuardHit, ...]
    tag_payload: str
    input_sha256: str
    output_sha256: str

    @property
    def found(self) -> bool:
        return self.total > 0


def _input_digest(value: Any) -> str:
    if isinstance(value, str):
        return sha256_text(value)
    return sha256_json(value)


def _scan_selected(text: str, categories: frozenset[str]) -> tuple[int, dict[str, int], str, str]:
    scan = scan_hidden_characters(text)
    counts = {name: scan.counts[name] for name in scan.active_categories() if name in categories}
    total = sum(counts.values())
    first = ""
    for finding in scan.findings:
        if finding.category in categories:
            first = f"U+{finding.codepoint:04X}@{finding.index}({finding.category})"
            break
    return total, counts, first, extract_tag_payload(text)


def _walk(
    value: Any,
    categories: frozenset[str],
    on_findings: str,
    path: str,
    hits: list[GuardHit],
) -> tuple[Any, int]:
    removed = 0
    if isinstance(value, str):
        if len(value) > PRODUCT_MAX_INPUT_CHARS:
            raise ValueError(f"input is too large (max {PRODUCT_MAX_INPUT_CHARS} characters)")
        total, counts, first, tag_payload = _scan_selected(value, categories)
        if total == 0:
            return value, 0
        hits.append(
            GuardHit(path=path or "$", total=total, counts=counts, first=first, tag_payload=tag_payload)
        )
        if on_findings == ON_FINDINGS_REPORT:
            return value, 0
        if on_findings == ON_FINDINGS_REFUSE:
            return value, 0
        cleaned, stripped = clean_hidden_characters(value, categories=categories)
        return cleaned, stripped
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            walked, stripped = _walk(item, categories, on_findings, child, hits)
            out[key] = walked
            removed += stripped
        return out, removed
    if isinstance(value, tuple):
        items: list[Any] = []
        for index, item in enumerate(value):
            walked, stripped = _walk(item, categories, on_findings, f"{path}[{index}]", hits)
            items.append(walked)
            removed += stripped
        return tuple(items), removed
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = []
        for index, item in enumerate(value):
            walked, stripped = _walk(item, categories, on_findings, f"{path}[{index}]", hits)
            items.append(walked)
            removed += stripped
        return items, removed
    return value, 0


def _merge_counts(hits: Sequence[GuardHit]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for hit in hits:
        for name, count in hit.counts.items():
            merged[name] = merged.get(name, 0) + count
    return merged


def _build_receipt(
    action: str,
    original: Any,
    output: Any,
    hits: Sequence[GuardHit],
    removed: int,
) -> GuardReceipt:
    counts = _merge_counts(hits)
    total = sum(hit.total for hit in hits)
    payloads = tuple(hit.tag_payload for hit in hits if hit.tag_payload)
    return GuardReceipt(
        action=action,
        total=total,
        removed=removed,
        counts=counts,
        hits=tuple(hits),
        tag_payload="".join(payloads),
        input_sha256=_input_digest(original),
        output_sha256=_input_digest(output),
    )


def receipt_dict(receipt: GuardReceipt) -> dict[str, object]:
    return {
        "algorithm_version": GUARD_ALGORITHM_VERSION,
        "action": receipt.action,
        "found": receipt.found,
        "total": receipt.total,
        "removed": receipt.removed,
        "counts": receipt.counts,
        "tag_payload": receipt.tag_payload,
        "input_sha256": receipt.input_sha256,
        "output_sha256": receipt.output_sha256,
        "hits": [
            {
                "path": hit.path,
                "total": hit.total,
                "counts": hit.counts,
                "first": hit.first,
                "tag_payload": hit.tag_payload,
            }
            for hit in receipt.hits
        ],
    }


class Guard:
    def __init__(
        self,
        *,
        on_findings: str = ON_FINDINGS_STRIP,
        categories: Iterable[str] | None = None,
    ) -> None:
        if on_findings not in ON_FINDINGS_CHOICES:
            raise ValueError("on_findings must be strip, refuse, or report")
        self.on_findings = on_findings
        self.categories = (
            frozenset(SECURITY_SCAN_CATEGORIES)
            if categories is None
            else normalize_scan_categories(categories)
        )

    def inspect(self, value: Any) -> tuple[Any, GuardReceipt]:
        hits: list[GuardHit] = []
        walked, removed = _walk(value, self.categories, self.on_findings, "", hits)
        if hits and self.on_findings == ON_FINDINGS_REFUSE:
            receipt = _build_receipt(ON_FINDINGS_REFUSE, value, value, hits, 0)
            raise HiddenTextRefused(receipt)
        if hits and self.on_findings == ON_FINDINGS_REPORT:
            action = ON_FINDINGS_REPORT
            output = value
            removed = 0
        elif hits:
            action = ON_FINDINGS_STRIP
            output = walked
        else:
            action = "passed"
            output = value
            removed = 0
        return output, _build_receipt(action, value, output, hits, removed)

    def protect(self, value: Any) -> Any:
        output, _receipt = self.inspect(value)
        return output

    def wrap(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            new_args = tuple(self.protect(argument) for argument in args)
            new_kwargs = {key: self.protect(item) for key, item in kwargs.items()}
            return func(*new_args, **new_kwargs)

        return wrapped


_DEFAULT_GUARD = Guard()


def protect(value: Any, *, on_findings: str = ON_FINDINGS_STRIP) -> Any:
    if on_findings == ON_FINDINGS_STRIP:
        return _DEFAULT_GUARD.protect(value)
    return Guard(on_findings=on_findings).protect(value)


def inspect(value: Any, *, on_findings: str = ON_FINDINGS_STRIP) -> tuple[Any, GuardReceipt]:
    return Guard(on_findings=on_findings).inspect(value)


def _guard_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark guard",
        description=(
            "Sanitize text or JSON before it reaches a model. "
            "Strips hidden Unicode (tag smuggling, bidi overrides, zero-width) "
            "and can recover smuggled tag payloads. Does not detect semantic prompt injection."
        ),
    )
    parser.add_argument(
        "source",
        nargs="?",
        metavar="TEXT_OR_FILE",
        help="quoted text or UTF-8 file; omit to read stdin",
    )
    parser.add_argument(
        "--json",
        dest="json_mode",
        action="store_true",
        help="parse stdin/file as JSON and sanitize every string in the structure",
    )
    parser.add_argument(
        "--refuse",
        action="store_true",
        help="exit 1 and keep the original if hidden Unicode is found (do not strip)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="scan only: print a receipt and leave the payload unchanged",
    )
    parser.add_argument(
        "--receipt",
        dest="receipt_output",
        action="store_true",
        help="write the JSON receipt to stderr",
    )
    parser.add_argument(
        "--select",
        default=",".join(SECURITY_SCAN_CATEGORIES),
        metavar="CATS",
        help="comma-separated categories, or 'all'",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="hide the human summary on stderr",
    )
    return parser


def _resolve_categories(select: str) -> frozenset[str]:
    if select.strip().casefold() == "all":
        from .product.scan import SCAN_CATEGORIES

        return frozenset(SCAN_CATEGORIES)
    names = [item.strip() for item in select.split(",") if item.strip()]
    if not names:
        raise ValueError("no categories selected")
    return normalize_scan_categories(names)


def _load_plain(source: str | None, stdin: TextIO) -> str:
    if source in (None, "-", ""):
        buffer = getattr(stdin, "buffer", None)
        if buffer is not None:
            return decode_hidden_scan_bytes(buffer.read())
        return stdin.read()
    from pathlib import Path

    path = Path(source).expanduser()
    if path.is_file():
        return decode_hidden_scan_bytes(path.read_bytes())
    return source


def _emit(stream: TextIO, text: str) -> None:
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        try:
            stream.flush()
        except (OSError, ValueError, UnicodeError):
            pass
        buffer.write(text.encode("utf-8", "surrogatepass"))
        buffer.flush()
        return
    stream.write(text)
    stream.flush()


def _human_summary(receipt: GuardReceipt) -> str:
    if not receipt.found:
        return "FuckMark guard: payload is clean."
    counts = ", ".join(f"{name}={receipt.counts[name]}" for name in receipt.counts)
    extra = ""
    if receipt.tag_payload:
        extra = f" Recovered tag payload: {receipt.tag_payload!r}."
    if receipt.action == ON_FINDINGS_STRIP:
        return (
            f"FuckMark guard: stripped {receipt.removed} hidden characters "
            f"({counts}).{extra}"
        )
    if receipt.action == ON_FINDINGS_REFUSE:
        return f"FuckMark guard: refused {receipt.total} hidden characters ({counts}).{extra}"
    return f"FuckMark guard: found {receipt.total} hidden characters ({counts}).{extra}"


def run_guard_argv(argv: list[str], stdin: TextIO, output: TextIO, errors: TextIO) -> int:
    try:
        arguments = _guard_parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return GUARD_EXIT_OK
        return int(code) if isinstance(code, int) else GUARD_EXIT_USAGE
    if arguments.refuse and arguments.report:
        errors.write("FuckMark: pass --refuse or --report, not both\n")
        errors.flush()
        return GUARD_EXIT_USAGE
    try:
        categories = _resolve_categories(arguments.select)
        raw = _load_plain(arguments.source, stdin)
    except (OSError, UnicodeError, ValueError) as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return GUARD_EXIT_USAGE
    if not raw:
        errors.write("FuckMark: no input. Pipe text, pass a file, or quote a string.\n")
        errors.flush()
        return GUARD_EXIT_USAGE
    if arguments.refuse:
        on_findings = ON_FINDINGS_REFUSE
    elif arguments.report:
        on_findings = ON_FINDINGS_REPORT
    else:
        on_findings = ON_FINDINGS_STRIP
    if arguments.json_mode:
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as error:
            errors.write(f"FuckMark: input is not JSON: {error}\n")
            errors.flush()
            return GUARD_EXIT_USAGE
    else:
        payload = raw
    guard = Guard(on_findings=on_findings, categories=categories)
    try:
        cleaned, receipt = guard.inspect(payload)
    except HiddenTextRefused as error:
        receipt = error.receipt
        if not arguments.quiet:
            errors.write(_human_summary(receipt) + "\n")
            errors.flush()
        if arguments.receipt_output:
            _emit(errors, json.dumps(receipt_dict(receipt), ensure_ascii=False, indent=2) + "\n")
        return GUARD_EXIT_FINDINGS
    if arguments.json_mode:
        rendered = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = cleaned if isinstance(cleaned, str) else json.dumps(cleaned, ensure_ascii=False)
    _emit(output, rendered)
    if not arguments.quiet:
        errors.write(_human_summary(receipt) + "\n")
        errors.flush()
    if arguments.receipt_output:
        _emit(errors, json.dumps(receipt_dict(receipt), ensure_ascii=False, indent=2) + "\n")
    return GUARD_EXIT_OK


def guard_payload(value: Any, *, on_findings: str = ON_FINDINGS_STRIP) -> dict[str, object]:
    if isinstance(value, str) and len(value) > PRODUCT_MAX_INPUT_CHARS:
        return {
            "ok": False,
            "reason": "too-large",
            "backend": "python",
            "max": PRODUCT_MAX_INPUT_CHARS,
        }
    try:
        cleaned, receipt = Guard(on_findings=on_findings).inspect(value)
    except HiddenTextRefused as error:
        return {
            "ok": False,
            "reason": "refused",
            "backend": "python",
            "receipt": receipt_dict(error.receipt),
        }
    return {
        "ok": True,
        "reason": receipt.action,
        "backend": "python",
        "value": cleaned,
        "receipt": receipt_dict(receipt),
    }
