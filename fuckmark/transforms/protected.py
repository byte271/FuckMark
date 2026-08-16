from __future__ import annotations

import ipaddress
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from .._validation import require_clean_string
from ..hashing import sha256_json, sha256_text
from .protected_artifacts import ProtectedSpan, ProtectedSpanManifest, UserProtectedRange
from .schema import ProtectedSpanKind


PROTECTED_SPAN_ALGORITHM_VERSION = "protected-span-extractor-v1"


_FENCED_CODE_RE = re.compile(r"(?ms)(?:```.*?```|~~~.*?~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_MARKDOWN_DESTINATION_RE = re.compile(r"(?<=\]\()[^\)\n]+(?=\))")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")
_EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![\w.-])")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6_TOKEN_RE = re.compile(r"(?<![0-9A-Fa-f:])[0-9A-Fa-f:]{3,}(?![0-9A-Fa-f:])")
_ISO_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_CURRENCY_RE = re.compile(r"(?i)(?<!\w)(?:[-+]?\s?[$€£¥]\s?\d[\d,]*(?:\.\d+)?|[$€£¥]\s?[-+]?\d[\d,]*(?:\.\d+)?|[-+]?\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|JPY|CNY|RMB))(?!\w)")
_PERCENT_RE = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%(?!\w)")
_NUMBER_RE = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?(?!\w)")
_DOUBLE_QUOTE_RE = re.compile(r'"(?:[^"\\\n]|\\.)+"')
_CURLY_DOUBLE_QUOTE_RE = re.compile(r"“[^”\n]+”")
_CURLY_SINGLE_QUOTE_RE = re.compile(r"‘[^’\n]{2,}’")
_STRAIGHT_SINGLE_QUOTE_RE = re.compile(r"(?<!\w)'[^'\n]{2,}'(?!\w)")
_POSIX_PATH_RE = re.compile(r"(?<![\w:])(?:~?/|\./|\.\./)(?:[A-Za-z0-9._~+@%-]+/)*[A-Za-z0-9._~+@%-]+/?")
_WINDOWS_PATH_RE = re.compile(r"(?i)(?<![A-Z0-9_])(?:[A-Z]:\\|\\\\[A-Z0-9._$-]+\\)(?:[^\\/:*?\"<>|\s]+\\)*[^\\/:*?\"<>|\s]+")
_CLI_FLAG_RE = re.compile(r"(?<![\w-])--?[A-Za-z][A-Za-z0-9-]*(?:=[^\s]+)?")
_NUMERIC_CITATION_RE = re.compile(r"\[(?:\d+(?:\s*[-,]\s*\d+)*)\]")
_AUTHOR_YEAR_CITATION_RE = re.compile(r"\((?:[A-Z][A-Za-z'’-]+(?:\s+(?:and|&|et\s+al\.)\s+[A-Z][A-Za-z'’-]+)?),\s*\d{4}[a-z]?\)")
_DOLLAR_MATH_RE = re.compile(r"(?s)\$\$.*?\$\$|(?<!\\)\$(?!\$)[^$\n]+(?<!\\)\$")
_PAREN_MATH_RE = re.compile(r"(?s)\\\([^\n]+?\\\)|\\\[[^\n]+?\\\]")



def _add_match(raw: list[tuple[int, int, ProtectedSpanKind]], start: int, end: int, kind: ProtectedSpanKind) -> None:
    if end > start:
        raw.append((start, end, kind))


def _add_regex(raw: list[tuple[int, int, ProtectedSpanKind]], text: str, pattern: re.Pattern[str], kind: ProtectedSpanKind) -> None:
    for match in pattern.finditer(text):
        _add_match(raw, match.start(), match.end(), kind)


def _trim_url(text: str, start: int, end: int) -> tuple[int, int]:
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
    for match in _URL_RE.finditer(text):
        start, end = _trim_url(text, match.start(), match.end())
        _add_match(raw, start, end, ProtectedSpanKind.URL)


def _add_posix_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _POSIX_PATH_RE.finditer(text):
        start, end = match.span()
        while end > start and text[end - 1] in ".,;:!?":
            end -= 1
        _add_match(raw, start, end, ProtectedSpanKind.POSIX_PATH)


def _add_windows_paths(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _WINDOWS_PATH_RE.finditer(text):
        start, end = match.span()
        while end > start and text[end - 1] in ".,;:!?":
            end -= 1
        _add_match(raw, start, end, ProtectedSpanKind.WINDOWS_PATH)


def _add_ip_addresses(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _IPV4_RE.finditer(text):
        try:
            parsed = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if parsed.version == 4:
            _add_match(raw, match.start(), match.end(), ProtectedSpanKind.IPV4)
    for match in _IPV6_TOKEN_RE.finditer(text):
        candidate = match.group()
        if candidate.count(":") < 2:
            continue
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if parsed.version == 6:
            _add_match(raw, match.start(), match.end(), ProtectedSpanKind.IPV6)


def _add_dates(raw: list[tuple[int, int, ProtectedSpanKind]], text: str) -> None:
    for match in _ISO_DATE_RE.finditer(text):
        try:
            date.fromisoformat(match.group())
        except ValueError:
            continue
        _add_match(raw, match.start(), match.end(), ProtectedSpanKind.DATE)


def _identifier_matches(text: str, identifier: str) -> Sequence[tuple[int, int]]:
    escaped = re.escape(identifier)
    if identifier[0].isalnum() or identifier[0] == "_":
        escaped = rf"(?<!\w){escaped}"
    if identifier[-1].isalnum() or identifier[-1] == "_":
        escaped = rf"{escaped}(?!\w)"
    return tuple((match.start(), match.end()) for match in re.finditer(escaped, text))


def _merge_spans(text: str, raw: Sequence[tuple[int, int, ProtectedSpanKind]]) -> tuple[ProtectedSpan, ...]:
    ordered = sorted(raw, key=lambda value: (value[0], value[1], value[2].value))
    if not ordered:
        return ()
    groups: list[tuple[int, int, set[ProtectedSpanKind]]] = []
    for start, end, kind in ordered:
        if not groups or start >= groups[-1][1]:
            groups.append((start, end, {kind}))
            continue
        previous_start, previous_end, kinds = groups[-1]
        kinds.add(kind)
        groups[-1] = (previous_start, max(previous_end, end), kinds)
    output: list[ProtectedSpan] = []
    for start, end, kinds in groups:
        exact_text = text[start:end]
        normalized_kinds = tuple(sorted(kinds, key=lambda value: value.value))
        text_hash = sha256_text(exact_text)
        payload = {
            "start": start,
            "end": end,
            "kinds": tuple(kind.value for kind in normalized_kinds),
            "exact_text": exact_text,
            "text_hash": text_hash,
        }
        output.append(ProtectedSpan(start, end, normalized_kinds, exact_text, text_hash, sha256_json(payload)))
    return tuple(output)


class ProtectedSpanExtractor:
    __slots__ = ("_identifiers",)

    def __init__(self, identifiers: Sequence[str] = ()) -> None:
        if not isinstance(identifiers, Sequence) or isinstance(identifiers, (str, bytes, bytearray)):
            raise TypeError("identifiers must be a sequence of strings")
        materialized = tuple(identifiers)
        if any(not isinstance(value, str) for value in materialized):
            raise TypeError("identifiers must contain strings")
        for value in materialized:
            require_clean_string("identifier", value)
        normalized = tuple(sorted(set(materialized)))
        self._identifiers = normalized

    @property
    def identifiers(self) -> tuple[str, ...]:
        return self._identifiers

    def extract(self, text: str, user_ranges: Sequence[UserProtectedRange] = ()) -> ProtectedSpanManifest:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not isinstance(user_ranges, Sequence) or isinstance(user_ranges, (str, bytes, bytearray)):
            raise TypeError("user_ranges must be a sequence")
        materialized_ranges = tuple(user_ranges)
        if any(not isinstance(value, UserProtectedRange) for value in materialized_ranges):
            raise TypeError("user_ranges must contain UserProtectedRange values")
        ranges = tuple(sorted(materialized_ranges, key=lambda value: (value.start, value.end, value.label)))
        for value in ranges:
            if value.end > len(text):
                raise ValueError("user protected range extends beyond text")
        raw: list[tuple[int, int, ProtectedSpanKind]] = []
        _add_regex(raw, text, _FENCED_CODE_RE, ProtectedSpanKind.CODE)
        _add_regex(raw, text, _INLINE_CODE_RE, ProtectedSpanKind.CODE)
        _add_regex(raw, text, _MARKDOWN_DESTINATION_RE, ProtectedSpanKind.MARKDOWN_DESTINATION)
        _add_urls(raw, text)
        _add_regex(raw, text, _EMAIL_RE, ProtectedSpanKind.EMAIL)
        _add_ip_addresses(raw, text)
        _add_dates(raw, text)
        _add_regex(raw, text, _CURRENCY_RE, ProtectedSpanKind.CURRENCY)
        _add_regex(raw, text, _PERCENT_RE, ProtectedSpanKind.PERCENTAGE)
        _add_regex(raw, text, _NUMBER_RE, ProtectedSpanKind.NUMBER)
        _add_regex(raw, text, _DOUBLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_regex(raw, text, _CURLY_DOUBLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_regex(raw, text, _CURLY_SINGLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_regex(raw, text, _STRAIGHT_SINGLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_posix_paths(raw, text)
        _add_windows_paths(raw, text)
        _add_regex(raw, text, _CLI_FLAG_RE, ProtectedSpanKind.CLI_FLAG)
        _add_regex(raw, text, _NUMERIC_CITATION_RE, ProtectedSpanKind.CITATION)
        _add_regex(raw, text, _AUTHOR_YEAR_CITATION_RE, ProtectedSpanKind.CITATION)
        _add_regex(raw, text, _DOLLAR_MATH_RE, ProtectedSpanKind.MATH)
        _add_regex(raw, text, _PAREN_MATH_RE, ProtectedSpanKind.MATH)
        for identifier in self._identifiers:
            for start, end in _identifier_matches(text, identifier):
                _add_match(raw, start, end, ProtectedSpanKind.IDENTIFIER)
        for value in ranges:
            _add_match(raw, value.start, value.end, ProtectedSpanKind.USER_MARKED_ENTITY)
        spans = _merge_spans(text, raw)
        input_hash = sha256_text(text)
        payload = {
            "algorithm_version": PROTECTED_SPAN_ALGORITHM_VERSION,
            "input_hash": input_hash,
            "identifiers": self._identifiers,
            "user_ranges": ranges,
            "spans": spans,
        }
        return ProtectedSpanManifest(
            PROTECTED_SPAN_ALGORITHM_VERSION,
            input_hash,
            self._identifiers,
            ranges,
            spans,
            sha256_json(payload),
        )


