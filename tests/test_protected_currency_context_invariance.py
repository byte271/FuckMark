from __future__ import annotations

import pytest

from fuckmark.transforms import validate_hard_invariants
from fuckmark.transforms.protected import ProtectedSpanExtractor


def _currency_spans(text: str) -> list[str]:
    return [
        text[span.start : span.end]
        for span in ProtectedSpanExtractor().extract(text).spans
        if "currency" in tuple(kind.value for kind in span.kinds)
    ]


def test_currency_extraction_is_invariant_under_preceding_whitespace() -> None:
    assert _currency_spans("for $100") == ["$100"]
    assert _currency_spans("for  $100") == ["$100"]
    assert _currency_spans("a  $5 and $100") == ["$5", "$100"]
    assert _currency_spans("cost:  $100,000 total") == ["$100,000"]


def test_signed_currency_forms_still_extract() -> None:
    assert _currency_spans("- $5") == ["- $5"]
    assert _currency_spans("+EUR  3.50") == ["+EUR  3.50"]
    assert _currency_spans("USD  5") == ["USD  5"]


def test_spacing_before_currency_no_longer_breaks_hard_invariants() -> None:
    source = "Apple has been selling its iPhones for $100, and buyers notice."
    transformed = "Apple has been  selling its iPhones for  $100,  and buyers notice."
    report = validate_hard_invariants(source, transformed)
    assert report.status.value == "pass"
    assert [r.value for r in report.reasons] == []
