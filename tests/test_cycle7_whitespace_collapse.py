import unicodedata

from fuckmark.cycle7.whitespace_collapse import (
    CYCLE7_SANITIZER_VARIANT_IDS,
    WHITESPACE_COLLAPSE_VERSION,
    collapse_horizontal_ascii_whitespace,
    sanitize_cycle7_variant,
)
from fuckmark.sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters


def test_whitespace_collapse_version_and_variant_ids_are_frozen() -> None:
    assert WHITESPACE_COLLAPSE_VERSION == "whitespace-collapse-v1"
    assert CYCLE7_SANITIZER_VARIANT_IDS == (
        "raw",
        "nfkc",
        "cf_strip",
        "nfkc_cf_strip",
        "ws_collapse",
        "ws_collapse_nfkc_cf_strip",
    )


def test_collapse_repeated_ascii_spaces_and_tabs_but_preserve_newlines() -> None:
    assert collapse_horizontal_ascii_whitespace("a  b") == "a b"
    assert collapse_horizontal_ascii_whitespace("a\t\tb") == "a b"
    assert collapse_horizontal_ascii_whitespace("a \t b") == "a b"
    assert collapse_horizontal_ascii_whitespace("a\nb  c") == "a\nb c"
    assert collapse_horizontal_ascii_whitespace("a\r\nb") == "a\nb"
    assert collapse_horizontal_ascii_whitespace("  a  ") == " a "
    assert collapse_horizontal_ascii_whitespace("a\n\nb") == "a\n\nb"


def test_collapse_does_not_touch_nbsp_or_cycle6_nfkc_cf_arms() -> None:
    nbsp = "a\u00a0\u00a0b"
    assert collapse_horizontal_ascii_whitespace(nbsp) == nbsp
    cf = "a\u200bb"
    assert sanitize_cycle7_variant("cf_strip", cf) == strip_unicode_format_characters(cf)
    assert sanitize_cycle7_variant("nfkc", "ﬁ") == nfkc_normalize("ﬁ")
    assert sanitize_cycle7_variant("raw", "a  b") == "a  b"


def test_combined_collapse_runs_after_nfkc() -> None:
    text = "a  b\u200c  c"
    combined = sanitize_cycle7_variant("ws_collapse_nfkc_cf_strip", text)
    assert "  " not in combined
    assert "\u200c" not in combined
    assert unicodedata.normalize("NFKC", combined) == combined
