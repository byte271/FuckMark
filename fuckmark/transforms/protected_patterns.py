from __future__ import annotations

import ipaddress
import re
from datetime import date

from .schema import ProtectedSpanKind

_MAX_PROTECTED_ITEMS = 100_000
_HWS = r"[^\S\r\n]"
_URL_RE = re.compile(r"\b(?ai:https?://|www\.)[^\s<>\"']+")
_BARE_DOMAIN_RE = re.compile(r"(?<![@\\/\w.-])(?ai:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:xn--[A-Z0-9-]{2,59}|[A-Z]{2,63})(?![A-Z0-9-]))(?::\d{1,5})?(?:[/?#][^\s<>\"']*)?")
_EMAIL_RE = re.compile(r"(?<![\w.+-])(?ai:[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+)(?![\w-])")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6_TOKEN_RE = re.compile(r"(?<![0-9A-Fa-f:.])[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%[A-Za-z0-9._~-]+)?(?![0-9A-Za-z_.:~-])")
_ISO_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_MONTH = r"(?ai:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_MONTH_FIRST_DATE_RE = re.compile(rf"(?<!\w){_MONTH}{_HWS}+\d{{1,2}}(?:,)?{_HWS}+\d{{4}}(?!\d)")
_DAY_FIRST_DATE_RE = re.compile(rf"(?<!\d)\d{{1,2}}{_HWS}+{_MONTH}{_HWS}+\d{{4}}(?!\d)")
_SLASH_DATE_RE = re.compile(r"(?<!\d)(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}/\d{1,2}/\d{1,2})(?!\d)")
_NUMBER_BODY = r"[-+]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?"
_CURRENCY_CODE = r"(?ai:USD|EUR|GBP|JPY|CNY|RMB)"
_CURRENCY_RE = re.compile(rf"(?<!\w)(?:[-+]?{_HWS}*{_CURRENCY_CODE}{_HWS}*{_NUMBER_BODY}|[-+]?{_HWS}*[$€£¥]{_HWS}*{_NUMBER_BODY}|{_NUMBER_BODY}{_HWS}*{_CURRENCY_CODE})(?!\w)")
_PERCENT_RE = re.compile(rf"(?<![\w.]){_NUMBER_BODY}{_HWS}*%(?!\w)")
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
    if end <= start:
        return start, end
    counts = {"(": 0, ")": 0, "[": 0, "]": 0, "{": 0, "}": 0}
    for character in text[start:end]:
        if character in counts:
            counts[character] += 1
    opening_for = {")": "(", "]": "[", "}": "{"}
    while end > start:
        closing = text[end - 1]
        opening = opening_for.get(closing)
        if opening is None or counts[closing] <= counts[opening]:
            break
        counts[closing] -= 1
        end -= 1
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


_MONTH_NUMBERS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _valid_date_parts(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


def _valid_english_date(value: str) -> bool:
    compact = re.sub(_HWS + "+", " ", value.strip()).replace(",", "")
    parts = compact.split(" ")
    if len(parts) != 3:
        return False
    if parts[0].isdigit():
        day_text, month_text, year_text = parts
    else:
        month_text, day_text, year_text = parts
    month = _MONTH_NUMBERS.get(month_text.lower())
    if month is None or not day_text.isdigit() or not year_text.isdigit():
        return False
    return _valid_date_parts(int(year_text), month, int(day_text))


def _valid_slash_date(value: str) -> bool:
    parts = value.split("/")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return False
    first, second, third = parts
    if len(first) == 4:
        return _valid_date_parts(int(first), int(second), int(third))
    year = int(third) if len(third) == 4 else 2000 + int(third)
    return _valid_date_parts(year, int(first), int(second)) or _valid_date_parts(year, int(second), int(first))


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
        if _valid_slash_date(match.group()):
            _append(raw, match.start(), match.end(), ProtectedSpanKind.DATE)

def _identifier_matches(text: str, identifier: str) -> tuple[tuple[int, int], ...]:
    escaped = re.escape(identifier)
    if identifier[0].isalnum() or identifier[0] == "_":
        escaped = rf"(?<!\w){escaped}"
    if identifier[-1].isalnum() or identifier[-1] == "_":
        escaped = rf"{escaped}(?!\w)"
    return tuple((match.start(), match.end()) for match in re.finditer(escaped, text))
