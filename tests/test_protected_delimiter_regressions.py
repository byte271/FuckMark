from fuckmark.transforms import ProtectedSpanExtractor, ProtectedSpanKind, default_transform_registry


def _single_math_span(text: str):
    spans = tuple(
        span
        for span in ProtectedSpanExtractor().extract(text).spans
        if ProtectedSpanKind.MATH in span.kinds
    )
    assert len(spans) == 1
    return spans[0]


def test_escaped_display_math_closer_does_not_terminate_protection() -> None:
    text = r"$$do not \$$ and do not wait"
    span = _single_math_span(text)
    assert span.exact_text == text
    assert not default_transform_registry().enumerate(text).candidates


def test_longer_dollar_run_does_not_close_display_math() -> None:
    text = "$$do not $$$x$ and do not wait"
    span = _single_math_span(text)
    assert span.exact_text == text
    assert not default_transform_registry().enumerate(text).candidates


def test_double_dollar_run_does_not_close_inline_math() -> None:
    text = "$do not $$x$$ and do not wait"
    span = _single_math_span(text)
    assert span.exact_text == text
    assert not default_transform_registry().enumerate(text).candidates
