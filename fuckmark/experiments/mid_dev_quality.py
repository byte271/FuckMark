from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

from ..alignment import align_tokens
from ..observations import structural_observation_diff, summarize_structural_observations
from ..transforms.protected import ProtectedSpanExtractor
from ..transforms.protected_patterns import _NUMBER_RE
from ..transforms.schema import ProtectedSpanKind


_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")


def word_units(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return tuple(match.group(0) for match in _WORD_RE.finditer(text))


def word_edit_distance(left: str, right: str) -> int:
    a = word_units(left)
    b = word_units(right)
    previous = list(range(len(b) + 1))
    for index, left_value in enumerate(a, start=1):
        current = [index]
        for right_index, right_value in enumerate(b, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def word_edit_rate(source: str, transformed: str) -> float:
    count = len(word_units(source))
    if count == 0:
        return 0.0 if source == transformed else 1.0
    return min(1.0, word_edit_distance(source, transformed) / count)


def _multiset_preserved_fraction(source: Counter[str], transformed: Counter[str]) -> float:
    total = sum(source.values())
    if total == 0:
        return 1.0
    preserved = sum(min(count, transformed.get(value, 0)) for value, count in source.items())
    return preserved / total


def numbers_preserved_fraction(source: str, transformed: str) -> float:
    source_values = Counter(match.group(0) for match in _NUMBER_RE.finditer(source))
    transformed_values = Counter(match.group(0) for match in _NUMBER_RE.finditer(transformed))
    return _multiset_preserved_fraction(source_values, transformed_values)


def _protected_values(text: str, kind: ProtectedSpanKind) -> Counter[str]:
    manifest = ProtectedSpanExtractor().extract(text)
    return Counter(
        span.exact_text
        for span in manifest.spans
        if kind in span.kinds
    )


def urls_preserved_fraction(source: str, transformed: str) -> float:
    return _multiset_preserved_fraction(
        _protected_values(source, ProtectedSpanKind.URL),
        _protected_values(transformed, ProtectedSpanKind.URL),
    )


def protected_span_violation_count(source: str, transformed: str) -> int:
    source_manifest = ProtectedSpanExtractor().extract(source)
    transformed_manifest = ProtectedSpanExtractor().extract(transformed)
    source_values = Counter(
        (tuple(kind.value for kind in span.kinds), span.exact_text)
        for span in source_manifest.spans
    )
    transformed_values = Counter(
        (tuple(kind.value for kind in span.kinds), span.exact_text)
        for span in transformed_manifest.spans
    )
    return sum(
        abs(source_values[value] - transformed_values[value])
        for value in set(source_values) | set(transformed_values)
    )


def old_observation_replacement_ratio(
    source_token_ids: Sequence[int],
    transformed_token_ids: Sequence[int],
    ngram_len: int,
) -> float:
    source = tuple(source_token_ids)
    transformed = tuple(transformed_token_ids)
    alignment = align_tokens(source, transformed)
    diffs = structural_observation_diff(source, transformed, ngram_len, alignment)
    summary = summarize_structural_observations(source, transformed, ngram_len, diffs)
    if summary.original_count == 0:
        return 0.0
    return (summary.replaced_count + summary.unmapped_count) / summary.original_count
