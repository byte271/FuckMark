from __future__ import annotations

from collections.abc import Sequence

from .._validation import require_clean_string
from ..hashing import sha256_json, sha256_text
from .protected_artifacts import ProtectedSpan, ProtectedSpanManifest, UserProtectedRange
from .protected_patterns import (
    _add_dates,
    _add_ip_addresses,
    _add_regex,
    _add_urls,
    _append,
    _identifier_matches,
    _AUTHOR_YEAR_CITATION_RE,
    _CLI_FLAG_RE,
    _CURRENCY_RE,
    _EMAIL_RE,
    _NUMBER_RE,
    _NUMERIC_CITATION_RE,
    _PERCENT_RE,
)
from .protected_structures import (
    _add_delimited_math,
    _add_dollar_math,
    _add_double_quotations,
    _add_extended_posix_paths,
    _add_extended_windows_paths,
    _add_fenced_code,
    _add_inline_code,
    _add_markdown_destinations,
    _add_posix_paths,
    _add_windows_paths,
    _CURLY_SINGLE_QUOTE_RE,
    _STRAIGHT_SINGLE_QUOTE_RE,
)
from .schema import ProtectedSpanKind

PROTECTED_SPAN_ALGORITHM_VERSION = "protected-span-extractor-v3"


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
        payload = {"start": start, "end": end, "kinds": tuple(kind.value for kind in normalized_kinds), "exact_text": exact_text, "text_hash": text_hash}
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
        if len(set(materialized)) != len(materialized):
            raise ValueError("identifiers must not contain duplicates")
        self._identifiers = tuple(sorted(materialized))

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
        if len({(value.start, value.end) for value in materialized_ranges}) != len(materialized_ranges):
            raise ValueError("user_ranges must not duplicate protected geometry")
        ranges = tuple(sorted(materialized_ranges, key=lambda value: (value.start, value.end, value.label, value.range_hash)))
        for value in ranges:
            if value.end > len(text):
                raise ValueError("user protected range extends beyond text")
        raw: list[tuple[int, int, ProtectedSpanKind]] = []
        _add_fenced_code(raw, text)
        _add_inline_code(raw, text)
        _add_markdown_destinations(raw, text)
        _add_urls(raw, text)
        _add_regex(raw, text, _EMAIL_RE, ProtectedSpanKind.EMAIL)
        _add_ip_addresses(raw, text)
        _add_dates(raw, text)
        _add_regex(raw, text, _CURRENCY_RE, ProtectedSpanKind.CURRENCY)
        _add_regex(raw, text, _PERCENT_RE, ProtectedSpanKind.PERCENTAGE)
        _add_regex(raw, text, _NUMBER_RE, ProtectedSpanKind.NUMBER)
        _add_double_quotations(raw, text)
        _add_regex(raw, text, _CURLY_SINGLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_regex(raw, text, _STRAIGHT_SINGLE_QUOTE_RE, ProtectedSpanKind.QUOTATION)
        _add_posix_paths(raw, text)
        _add_extended_posix_paths(raw, text)
        _add_windows_paths(raw, text)
        _add_extended_windows_paths(raw, text)
        _add_regex(raw, text, _CLI_FLAG_RE, ProtectedSpanKind.CLI_FLAG)
        _add_regex(raw, text, _NUMERIC_CITATION_RE, ProtectedSpanKind.CITATION)
        _add_regex(raw, text, _AUTHOR_YEAR_CITATION_RE, ProtectedSpanKind.CITATION)
        _add_dollar_math(raw, text)
        _add_delimited_math(raw, text)
        for identifier in self._identifiers:
            for start, end in _identifier_matches(text, identifier):
                _append(raw, start, end, ProtectedSpanKind.IDENTIFIER)
        for value in ranges:
            _append(raw, value.start, value.end, ProtectedSpanKind.USER_MARKED_ENTITY)
        spans = _merge_spans(text, raw)
        input_hash = sha256_text(text)
        payload = {"algorithm_version": PROTECTED_SPAN_ALGORITHM_VERSION, "input_hash": input_hash, "identifiers": self._identifiers, "user_ranges": ranges, "spans": spans}
        return ProtectedSpanManifest(PROTECTED_SPAN_ALGORITHM_VERSION, input_hash, self._identifiers, ranges, spans, sha256_json(payload))
