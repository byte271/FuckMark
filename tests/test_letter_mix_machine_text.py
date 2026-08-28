from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    apply_letter_alternating_mix,
    hard_machine_intervals,
    select_letter_mix_sites,
)
from fuckmark.product.visible_projection import project_visible_v1
from fuckmark.transforms.protected import ProtectedSpanExtractor
from fuckmark.transforms.protected_markdown import resolve_markdown_reference_hrefs
from fuckmark.transforms.schema import ProtectedSpanKind


def _strip(text: str) -> str:
    return project_visible_v1(text, LETTER_MIX_APPROVED_CARRIERS)


def test_relative_and_windows_forward_slash_paths_keep_exact_bytes() -> None:
    cases = (
        ("Read src/main.py now.", "src/main.py"),
        ("Read docs/README.md now.", "docs/README.md"),
        ("Open C:/Users/Alice/notes.txt now.", "C:/Users/Alice/notes.txt"),
    )
    for source, path in cases:
        applied = apply_letter_alternating_mix(source)
        assert path in applied
        assert path.encode("utf-8") in applied.encode("utf-8")
        assert _strip(applied) == source
        assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
        intervals = hard_machine_intervals(source)
        assert any(source[start:end] == path for start, end in intervals)
        before, _, after = source.partition(path)
        assert any(character.isascii() and character.isalpha() for character in before + after)
        assert any(index < source.index(path) or index >= source.index(path) + len(path) for index in select_letter_mix_sites(source))


def test_path_protection_does_not_treat_and_or_or_input_output_as_paths() -> None:
    source = "Use and/or input/output here."
    applied = apply_letter_alternating_mix(source)
    assert _strip(applied) == source
    intervals = hard_machine_intervals(source)
    covered = "".join(source[start:end] for start, end in intervals)
    assert "and/or" not in covered
    assert "input/output" not in covered
    assert "\u034f" in applied or "\ufe00" in applied


def test_existing_posix_windows_url_and_email_protections_still_hold() -> None:
    source = (
        "See /var/tmp/report.json and C:\\Temp\\report.json plus "
        "https://example.com/do-not-touch and a.b+tag@example.com please."
    )
    applied = apply_letter_alternating_mix(source)
    for token in (
        "/var/tmp/report.json",
        "C:\\Temp\\report.json",
        "https://example.com/do-not-touch",
        "a.b+tag@example.com",
    ):
        assert token in applied
    assert _strip(applied) == source
    manifest = ProtectedSpanExtractor().extract(source)
    kinds = {kind for span in manifest.spans for kind in span.kinds}
    assert ProtectedSpanKind.POSIX_PATH in kinds
    assert ProtectedSpanKind.WINDOWS_PATH in kinds
    assert ProtectedSpanKind.URL in kinds
    assert ProtectedSpanKind.EMAIL in kinds


def test_markdown_reference_links_keep_href_after_mix() -> None:
    source = "[click][ref]\n\n[ref]: https://example.com\n"
    applied = apply_letter_alternating_mix(source)
    assert resolve_markdown_reference_hrefs(source) == ("https://example.com",)
    assert resolve_markdown_reference_hrefs(applied) == ("https://example.com",)
    assert "https://example.com" in applied
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
    click_span = applied[applied.index("[") + 1 : applied.index("]")]
    assert "\u034f" in click_span or "\ufe00" in click_span


def test_visible_projection_equality_is_not_markdown_link_behavior() -> None:
    source = "[click][ref]\n\n[ref]: https://example.com\n"
    broken = "[click][r\u034fef]\n\n[ref]: https://example.com\n"
    assert project_visible_v1(broken, LETTER_MIX_APPROVED_CARRIERS) == source
    assert resolve_markdown_reference_hrefs(source) == ("https://example.com",)
    assert resolve_markdown_reference_hrefs(broken) == ()
    applied = apply_letter_alternating_mix(source)
    assert resolve_markdown_reference_hrefs(applied) == ("https://example.com",)


def test_markdown_reference_definition_order_and_label_case() -> None:
    first = "[ref]: https://example.com\n\n[click][REF]\n"
    second = "[click][ref]\n\n[REF]: https://example.com\n"
    collapsed = "[ref][]\n\n[ref]: https://example.com\n"
    shortcut = "[ref]\n\n[ref]: https://example.com\n"
    for source in (first, second, collapsed, shortcut):
        applied = apply_letter_alternating_mix(source)
        assert resolve_markdown_reference_hrefs(applied) == ("https://example.com",)
        assert "https://example.com" in applied
        assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source


def test_inline_markdown_links_and_existing_destination_protection_do_not_regress() -> None:
    source = "Read [docs](https://example.com/a) and continue."
    applied = apply_letter_alternating_mix(source)
    assert "https://example.com/a" in applied
    assert _strip(applied) == source
    manifest = ProtectedSpanExtractor().extract(source)
    dest = next(span for span in manifest.spans if ProtectedSpanKind.MARKDOWN_DESTINATION in span.kinds)
    assert dest.exact_text == "https://example.com/a"
    assert resolve_markdown_reference_hrefs(applied) == ()
