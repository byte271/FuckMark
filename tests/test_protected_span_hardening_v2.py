from dataclasses import replace

import pytest

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import (
    CandidateEnumeration,
    HardInvariantReason,
    HardInvariantReport,
    InvariantStatus,
    LiteralTransformRule,
    ProtectedSpan,
    ProtectedSpanExtractor,
    ProtectedSpanKind,
    TransformCandidate,
    TransformFamily,
    TransformOperation,
    TransformRegistry,
    TransformResult,
    TransformTier,
    TransformationTrace,
    UserProtectedRange,
    default_transform_registry,
    validate_hard_invariants,
)


def _kind_spans(text: str, kind: ProtectedSpanKind):
    return tuple(span for span in ProtectedSpanExtractor().extract(text).spans if kind in span.kinds)

def _single_kind(text: str, kind: ProtectedSpanKind):
    spans = _kind_spans(text, kind)
    assert len(spans) == 1
    return spans[0]


def test_email_with_sentence_period_is_protected_without_period() -> None:
    span = _single_kind("Contact user@example.com.", ProtectedSpanKind.EMAIL)
    assert span.exact_text == "user@example.com"


def test_bare_domain_with_sentence_period_is_protected_without_period() -> None:
    span = _single_kind("See example.com.", ProtectedSpanKind.URL)
    assert span.exact_text == "example.com"


def test_nested_markdown_destination_is_fully_protected() -> None:
    span = _single_kind("Read [x](foo(bar)baz).", ProtectedSpanKind.MARKDOWN_DESTINATION)
    assert span.exact_text == "foo(bar)baz"


def test_unclosed_markdown_destination_is_fail_closed_to_line_end() -> None:
    span = _single_kind("Read [x](foo(bar)baz", ProtectedSpanKind.MARKDOWN_DESTINATION)
    assert span.exact_text == "foo(bar)baz"


def test_unclosed_fenced_code_is_protected_to_eof() -> None:
    text = "```python\ndo not edit\nstill code"
    span = _single_kind(text, ProtectedSpanKind.CODE)
    assert span.exact_text == text
    enum = default_transform_registry().enumerate(text)
    assert not enum.candidates
    assert enum.rejections


def test_unclosed_inline_code_is_protected_to_line_end() -> None:
    text = "Use `do not edit"
    span = _single_kind(text, ProtectedSpanKind.CODE)
    assert span.exact_text == "`do not edit"
    assert not default_transform_registry().enumerate(text).candidates


def test_unclosed_dollar_math_is_protected_to_line_end() -> None:
    text = "$do not change"
    span = _single_kind(text, ProtectedSpanKind.MATH)
    assert span.exact_text == text
    assert not default_transform_registry().enumerate(text).candidates


def test_unclosed_paren_math_is_protected_to_line_end() -> None:
    text = r"\(do not change"
    span = _single_kind(text, ProtectedSpanKind.MATH)
    assert span.exact_text == text
    assert not default_transform_registry().enumerate(text).candidates


def test_currency_dollar_does_not_freeze_rest_of_sentence_as_math() -> None:
    text = "It costs $12.50 and we do not leave."
    manifest = ProtectedSpanExtractor().extract(text)
    math = tuple(span for span in manifest.spans if ProtectedSpanKind.MATH in span.kinds)
    assert not math
    enum = default_transform_registry().enumerate(text)
    assert any(candidate.source_text == "do not" for candidate in enum.candidates)


def test_sep_month_date_is_protected() -> None:
    span = _single_kind("Sep 16, 2026", ProtectedSpanKind.DATE)
    assert span.exact_text == "Sep 16, 2026"


def test_day_first_english_date_is_protected() -> None:
    span = _single_kind("16 September 2026", ProtectedSpanKind.DATE)
    assert span.exact_text == "16 September 2026"


def test_space_percentage_is_one_protected_span() -> None:
    span = _single_kind("50 %", ProtectedSpanKind.PERCENTAGE)
    assert span.exact_text == "50 %"


def test_leading_decimal_percentage_is_protected() -> None:
    span = _single_kind(".5%", ProtectedSpanKind.PERCENTAGE)
    assert span.exact_text == ".5%"


def test_leading_decimal_number_is_protected() -> None:
    span = _single_kind(".5", ProtectedSpanKind.NUMBER)
    assert span.exact_text == ".5"


def test_currency_code_prefix_is_protected() -> None:
    span = _single_kind("USD 12.50", ProtectedSpanKind.CURRENCY)
    assert span.exact_text == "USD 12.50"


def test_ipv6_unspecified_address_is_protected() -> None:
    span = _single_kind("::", ProtectedSpanKind.IPV6)
    assert span.exact_text == "::"


def test_ipv4_mapped_ipv6_is_protected() -> None:
    span = _single_kind("::ffff:192.0.2.128", ProtectedSpanKind.IPV6)
    assert span.exact_text == "::ffff:192.0.2.128"


def test_ipv4_mapped_ipv6_trailing_period_is_not_part_of_span() -> None:
    span = _single_kind("Address ::ffff:192.0.2.128.", ProtectedSpanKind.IPV6)
    assert span.exact_text == "::ffff:192.0.2.128"


def test_escaped_backtick_does_not_freeze_rest_of_line() -> None:
    text = r"Use \`literal and do not wait."
    enum = default_transform_registry().enumerate(text)
    assert any(candidate.source_text == "do not" for candidate in enum.candidates)


def test_escaped_markdown_closer_does_not_create_destination() -> None:
    text = r"Literal \](do not wait) outside Markdown."
    enum = default_transform_registry().enumerate(text)
    assert any(candidate.source_text == "do not" for candidate in enum.candidates)


def test_bare_domain_query_is_fully_protected() -> None:
    span = _single_kind("example.com?x=do-not", ProtectedSpanKind.URL)
    assert span.exact_text == "example.com?x=do-not"


def test_punycode_bare_domain_is_protected() -> None:
    span = _single_kind("xn--e1afmkfd.xn--p1ai", ProtectedSpanKind.URL)
    assert span.exact_text == "xn--e1afmkfd.xn--p1ai"


def test_ipv6_zone_identifier_is_protected() -> None:
    span = _single_kind("fe80::1%eth0", ProtectedSpanKind.IPV6)
    assert span.exact_text == "fe80::1%eth0"


def test_negative_currency_sign_before_symbol_is_protected() -> None:
    span = _single_kind("-$12.50", ProtectedSpanKind.CURRENCY)
    assert span.exact_text == "-$12.50"


def test_month_first_date_without_comma_is_protected() -> None:
    span = _single_kind("Sep 16 2026", ProtectedSpanKind.DATE)
    assert span.exact_text == "Sep 16 2026"


def test_sept_abbreviation_is_protected() -> None:
    span = _single_kind("Sept 16, 2026", ProtectedSpanKind.DATE)
    assert span.exact_text == "Sept 16, 2026"


def test_us_slash_date_is_protected() -> None:
    span = _single_kind("08/16/2026", ProtectedSpanKind.DATE)
    assert span.exact_text == "08/16/2026"


def test_iso_order_slash_date_is_protected() -> None:
    span = _single_kind("2026/08/16", ProtectedSpanKind.DATE)
    assert span.exact_text == "2026/08/16"


def test_windows_path_with_spaces_blocks_candidate_inside_path() -> None:
    text = r"C:\Program Files\do not edit\file.txt"
    manifest = ProtectedSpanExtractor().extract(text)
    span = next(span for span in manifest.spans if ProtectedSpanKind.WINDOWS_PATH in span.kinds)
    assert span.exact_text == text
    enum = default_transform_registry().enumerate(text)
    assert not enum.candidates
    assert any(rejection.source_text == "do not" for rejection in enum.rejections)


def test_posix_path_with_spaces_blocks_candidate_inside_path() -> None:
    text = "/home/user/My Files/do not edit/file.txt"
    manifest = ProtectedSpanExtractor().extract(text)
    span = next(span for span in manifest.spans if ProtectedSpanKind.POSIX_PATH in span.kinds)
    assert span.exact_text == text
    enum = default_transform_registry().enumerate(text)
    assert not enum.candidates
    assert any(rejection.source_text == "do not" for rejection in enum.rejections)


def test_extended_path_scanner_does_not_consume_following_prose_after_extension() -> None:
    windows = r"Open C:\Temp\report.json with care."
    win_span = next(span for span in ProtectedSpanExtractor().extract(windows).spans if ProtectedSpanKind.WINDOWS_PATH in span.kinds)
    assert win_span.exact_text == r"C:\Temp\report.json"
    posix = "Open /var/tmp/report.json with care."
    posix_span = next(span for span in ProtectedSpanExtractor().extract(posix).spans if ProtectedSpanKind.POSIX_PATH in span.kinds)
    assert posix_span.exact_text == "/var/tmp/report.json"


def test_unclosed_ascii_double_quote_is_fail_closed_to_line_end() -> None:
    text = 'He said "do not change'
    span = _single_kind(text, ProtectedSpanKind.QUOTATION)
    assert span.exact_text == '"do not change'
    assert not default_transform_registry().enumerate(text).candidates


def test_unclosed_curly_double_quote_is_fail_closed_to_line_end() -> None:
    text = "He said “do not change"
    span = _single_kind(text, ProtectedSpanKind.QUOTATION)
    assert span.exact_text == "“do not change"
    assert not default_transform_registry().enumerate(text).candidates


def test_escaped_ascii_quote_does_not_open_protected_quotation() -> None:
    text = r'He wrote \"do not change and do not wait.'
    enumeration = default_transform_registry().enumerate(text)
    assert len(enumeration.candidates) == 2


def test_extended_posix_path_does_not_escape_from_url_into_later_path() -> None:
    text = "See https://example.com/a do not wait; then /tmp/x."
    enumeration = default_transform_registry().enumerate(text)
    assert any(candidate.source_text == "do not" for candidate in enumeration.candidates)
    url = next(span for span in enumeration.protected_manifest.spans if ProtectedSpanKind.URL in span.kinds)
    assert url.exact_text == "https://example.com/a"


def test_extended_posix_path_does_not_escape_markdown_destination() -> None:
    text = "Read [x](/a) and do not wait; then /tmp/x."
    enumeration = default_transform_registry().enumerate(text)
    assert any(candidate.source_text == "do not" for candidate in enumeration.candidates)
