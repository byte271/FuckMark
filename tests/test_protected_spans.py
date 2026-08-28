from fuckmark.transforms import ProtectedSpanExtractor, ProtectedSpanKind, UserProtectedRange


def _single(text: str):
    spans = ProtectedSpanExtractor().extract(text).spans
    assert len(spans) == 1
    return spans[0]


def test_url_trailing_period_is_not_protected() -> None:
    span = _single("https://example.com/path.")
    assert span.exact_text == "https://example.com/path"
    assert ProtectedSpanKind.URL in span.kinds


def test_url_query_parameters_are_protected() -> None:
    span = _single("https://example.com/a?x=1&y=two")
    assert span.exact_text == "https://example.com/a?x=1&y=two"
    assert ProtectedSpanKind.URL in span.kinds


def test_email_parentheses_are_not_part_of_span() -> None:
    manifest = ProtectedSpanExtractor().extract("Contact (a.b+tag@example.com).")
    span = next(value for value in manifest.spans if ProtectedSpanKind.EMAIL in value.kinds)
    assert span.exact_text == "a.b+tag@example.com"


def test_ipv4_is_protected() -> None:
    span = _single("192.168.10.4")
    assert ProtectedSpanKind.IPV4 in span.kinds


def test_ipv6_is_protected() -> None:
    span = _single("2001:db8::1")
    assert ProtectedSpanKind.IPV6 in span.kinds


def test_negative_integer_is_protected() -> None:
    span = _single("-42")
    assert ProtectedSpanKind.NUMBER in span.kinds


def test_decimal_is_protected() -> None:
    span = _single("3.14159")
    assert ProtectedSpanKind.NUMBER in span.kinds


def test_currency_is_protected() -> None:
    span = _single("$12.50")
    assert ProtectedSpanKind.CURRENCY in span.kinds


def test_percentage_is_protected() -> None:
    span = _single("12.5%")
    assert ProtectedSpanKind.PERCENTAGE in span.kinds


def test_iso_date_is_protected() -> None:
    span = _single("2026-08-16")
    assert ProtectedSpanKind.DATE in span.kinds


def test_invalid_iso_date_is_not_classified_as_date() -> None:
    manifest = ProtectedSpanExtractor().extract("2026-99-99")
    assert all(ProtectedSpanKind.DATE not in span.kinds for span in manifest.spans)
    assert tuple(span.exact_text for span in manifest.spans) == ("2026", "99", "99")


def test_inline_code_is_protected() -> None:
    span = _single("`do not edit`")
    assert span.exact_text == "`do not edit`"
    assert ProtectedSpanKind.CODE in span.kinds


def test_fenced_python_is_protected() -> None:
    text = "```python\ndo not edit\n```"
    span = _single(text)
    assert span.exact_text == text
    assert ProtectedSpanKind.CODE in span.kinds


def test_fenced_json_is_protected() -> None:
    text = "```json\n{\"value\": 12}\n```"
    span = _single(text)
    assert span.exact_text == text
    assert ProtectedSpanKind.CODE in span.kinds


def test_markdown_destination_is_protected() -> None:
    manifest = ProtectedSpanExtractor().extract("Read [docs](https://example.com/a).")
    span = next(value for value in manifest.spans if ProtectedSpanKind.MARKDOWN_DESTINATION in value.kinds)
    assert span.exact_text == "https://example.com/a"


def test_markdown_reference_labels_are_protected_at_use_and_definition() -> None:
    manifest = ProtectedSpanExtractor().extract("[click][ref]\n\n[ref]: https://example.com\n")
    labels = tuple(value.exact_text for value in manifest.spans if ProtectedSpanKind.MARKDOWN_LABEL in value.kinds)
    assert labels.count("ref") == 2
    dest = next(value for value in manifest.spans if ProtectedSpanKind.MARKDOWN_DESTINATION in value.kinds)
    assert dest.exact_text == "https://example.com"


def test_double_quoted_sentence_is_protected() -> None:
    span = _single('"Do not change this."')
    assert ProtectedSpanKind.QUOTATION in span.kinds


def test_single_quoted_sentence_is_protected_without_treating_apostrophe_as_quote() -> None:
    manifest = ProtectedSpanExtractor().extract("'Do not change this.' It isn't quoted.")
    quotes = tuple(value for value in manifest.spans if ProtectedSpanKind.QUOTATION in value.kinds)
    assert len(quotes) == 1
    assert quotes[0].exact_text == "'Do not change this.'"


def test_posix_path_is_protected() -> None:
    span = _single("/var/tmp/report.json")
    assert ProtectedSpanKind.POSIX_PATH in span.kinds


def test_windows_path_is_protected_without_consuming_following_words() -> None:
    manifest = ProtectedSpanExtractor().extract(r"Open C:\Temp\report.json with care.")
    span = next(value for value in manifest.spans if ProtectedSpanKind.WINDOWS_PATH in value.kinds)
    assert span.exact_text == r"C:\Temp\report.json"


def test_cli_flag_is_protected() -> None:
    span = _single("--dry-run")
    assert ProtectedSpanKind.CLI_FLAG in span.kinds


def test_numeric_citation_is_protected() -> None:
    span = _single("[12, 14-16]")
    assert ProtectedSpanKind.CITATION in span.kinds


def test_author_year_citation_is_protected() -> None:
    span = _single("(Smith, 2024)")
    assert ProtectedSpanKind.CITATION in span.kinds


def test_math_expression_is_protected() -> None:
    span = _single("$x^2 + y^2 = z^2$")
    assert ProtectedSpanKind.MATH in span.kinds


def test_overlapping_protected_categories_merge() -> None:
    span = _single("https://example.com/a?x=12")
    assert ProtectedSpanKind.URL in span.kinds
    assert ProtectedSpanKind.POSIX_PATH in span.kinds
    assert ProtectedSpanKind.NUMBER in span.kinds


def test_configured_identifier_is_protected() -> None:
    manifest = ProtectedSpanExtractor(("API_TOKEN",)).extract("Keep API_TOKEN unchanged.")
    span = next(value for value in manifest.spans if ProtectedSpanKind.IDENTIFIER in value.kinds)
    assert span.exact_text == "API_TOKEN"


def test_user_marked_entity_is_protected() -> None:
    text = "Keep Project Aurora unchanged."
    start = text.index("Project Aurora")
    user_range = UserProtectedRange.create(start, start + len("Project Aurora"), "entity")
    manifest = ProtectedSpanExtractor().extract(text, (user_range,))
    span = next(value for value in manifest.spans if ProtectedSpanKind.USER_MARKED_ENTITY in value.kinds)
    assert span.exact_text == "Project Aurora"
