from __future__ import annotations

import ipaddress
import re
from datetime import date, datetime

from .schema import ProtectedSpanKind


_MAX_PROTECTED_ITEMS = 100_000


_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")


_BARE_DOMAIN_RE = re.compile(r"(?i)(?<![@\w.-])(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:xn--[A-Z0-9-]{2,59}|[A-Z]{2,63})(?![A-Z0-9-])(?::\d{1,5})?(?:[/?#][^\s<>\"']*)?")


_EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![\w-])")


_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


_IPV6_TOKEN_RE = re.compile(r"(?<![0-9A-Fa-f:.])[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%[A-Za-z0-9._~-]+)?(?![0-9A-Za-z_.:~-])")


_ISO_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")


_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"


_MONTH_FIRST_DATE_RE = re.compile(rf"(?i)(?<!\w){_MONTH}\s+\d{{1,2}}(?:,)?\s+\d{{4}}(?!\d)")


_DAY_FIRST_DATE_RE = re.compile(rf"(?i)(?<!\d)\d{{1,2}}\s+{_MONTH}\s+\d{{4}}(?!\d)")


_SLASH_DATE_RE = re.compile(r"(?<!\d)(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}/\d{1,2}/\d{1,2})(?!\d)")


_NUMBER_BODY = r"[-+]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?"


_CURRENCY_RE = re.compile(rf"(?i)(?<!\w)(?:[-+]?[ \t]*(?:USD|EUR|GBP|JPY|CNY|RMB)[ \t]*{_NUMBER_BODY}|[-+]?[ \t]*[$€£¥][ \t]*{_NUMBER_BODY}|{_NUMBER_BODY}[ \t]*(?:USD|EUR|GBP|JPY|CNY|RMB))(?!\w)")


_PERCENT_RE = re.compile(rf"(?<![\w.]){_NUMBER_BODY}[ \t]*%(?!\w)")


_NUMBER_RE = re.compile(rf"(?<![\w.]){_NUMBER_BODY}(?!\w)")


_CLI_FLAG_RE = re.compile(r"(?<![\w-])--?[A-Za-z][A-Za-z0-9-]*(?:=[^\s]+)?")


_NUMERIC_CITATION_RE = re.compile(r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]")


_AUTHOR_YEAR_CITATION_RE = re.compile(r"\((?:[A-Z][A-Za-z'’-]+(?:\s+(?:and|&|et\s+al\.)\s+[A-Z][A-Za-z'’-]+)?),\s*\d{4}[a-z]?\)")


def _append(raw: list[tuple[int, int, ProtectedSpanKind]], start: int, end: int, kind: ProtectedSpanKind) -> None:
    if end <= start:
        return
    if len(raw) >= _MAX_PROTECTED_ITEMS:
        raise ValueError("protected span extraction exceeded item limit")
    raw.append((start, end, kind))


def _add_regex(raw: list[tuple[int, int, ProtectedSpanKind]], text: str, pattern: re.Pattern[str], kind: ProtectedSpanKind) -> None:
    for match in pattern.finditer(text):
        _append(raw, match.start(), match.end(), kind)


def _is_escaped(text: str, index: int) -> bool:
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        count += 1
        cursor -= 1
    return count % 2 == 1


def _line_end(text: str, start: int) -> int:
    end = text.find("\n", start)
    return len(text) if end < 0 else end


def _trim_terminal_punctuation(text: str, start: int, end: int) -> tuple[int, int]:
    while end > start and text[end - 1] in ".,;:!?":
        end -= 1
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    changed = True
    while changed and end > start:
        changed = False
        candidate = text[start:end]
        for opening, closing in pairs:
            if candidate.endswith(closing) and candidate.count(closing) > candidate.count(opening):
                end -= 1
                changed = True
                break
    return start, end


def _add_urls(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for pattern in (_URL_RE, _BARE_DOMAIN_RE):
        for match in pattern.finditer(text):
            start, end = _trim_terminal_punctuation(text, match.start(), match.end())
            _append(raw, start, end, ProtectedSpanKind.URL)


def _add_ip_addresses(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _IPV4_RE.finditer(text):
        try:
            parsed = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if parsed.version == 4:
            _append(raw, match.start(), match.end(), ProtectedSpanKind.IPV4)
    for match in _IPV6_TOKEN_RE.finditer(text):
        candidate = match.group()
        if candidate.count(":") < 2:
            continue
        end = match.end()
        while candidate.endswith("."):
            candidate = candidate[:-1]
            end -= 1
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if parsed.version == 6:
            _append(raw, match.start(), end, ProtectedSpanKind.IPV6)


def _valid_english_date(value: str) -> bool:
    compact = re.sub(r"\s+", " ", value.strip())
    compact = re.sub(r"(?i)\bSept\b", "Sep", compact)
    for pattern in ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
        try:
            datetime.strptime(compact, pattern)
            return True
        except ValueError:
            pass
    return False


def _add_dates(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _ISO_DATE_RE.finditer(text):
        try:
            date.fromisoformat(match.group())
        except ValueError:
            continue
        _append(raw, match.start(), match.end(), ProtectedSpanKind.DATE)
    for pattern in (_MONTH_FIRST_DATE_RE, _DAY_FIRST_DATE_RE):
        for match in pattern.finditer(text):
            if _valid_english_date(match.group()):
                _append(raw, match.start(), match.end(), ProtectedSpanKind.DATE)
    for match in _SLASH_DATE_RE.finditer(text):
        value = match.group()
        formats = ("%Y/%m/%d",) if len(value.split("/", 1)[0]) == 4 else ("%m/%d/%Y", "%m/%d/%y")
        if any(_valid_date_format(value, pattern) for pattern in formats):
            _append(raw, match.start(), match.end(), ProtectedSpanKind.DATE)


def _valid_date_format(value: str, pattern: str) -> bool:
    try:
        datetime.strptime(value, pattern)
        return True
    except ValueError:
        return False


def _identifier_matches(text: str, identifier: str) -> tuple[tuple[int, int], ...]:
    escaped = re.escape(identifier)
    if identifier[0].isalnum() or identifier[0] == "_":
        escaped = rf"(?<!\w){escaped}"
    if identifier[-1].isalnum() or identifier[-1] == "_":
        escaped = rf"{escaped}(?!\w)"
    return tuple((match.start(), match.end()) for match in re.finditer(escaped, text))
