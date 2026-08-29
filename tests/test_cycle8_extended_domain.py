from fuckmark.cli import (
    REASON_NO_ELIGIBLE_SITES,
    REASON_TRANSFORMED,
    REASON_UNSUPPORTED_DOMAIN,
    process_text,
    transform_text,
)
from fuckmark.cycle8.benchmark import (
    strip_enclosing_marks,
    strip_nonspacing_marks,
)
from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    apply_historical_quad_layer_letter_mix,
    apply_historical_mark_letter_mix,
    apply_letter_alternating_mix,
    select_letter_mix_sites,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.sanitizer_robustness import strip_unicode_format_characters


def test_live_mix_processes_latin_han_and_emoji_clusters() -> None:
    latin = chr(0x00E9) * 3
    han = chr(0x4E2D) + chr(0x6587)
    emoji = chr(0x1F600)
    family = chr(0x1F468) + "\u200d" + chr(0x1F469) + "\u200d" + chr(0x1F467)
    for source, sites in (
        (latin, (0, 1, 2)),
        (han, (0, 1)),
        (emoji, (0,)),
        (family, (4,)),
    ):
        assert select_letter_mix_sites(source) == sites
        result = transform_text(source)
        assert result.reason == REASON_TRANSFORMED
        assert result.site_count == len(sites)
        assert result.processed is True
        applied = apply_letter_alternating_mix(source)
        assert result.output_text == applied
        assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
        assert is_carrier_insertion_v1(source, applied, LETTER_MIX_APPROVED_CARRIERS)


def test_nfd_latin_inserts_after_the_combining_cluster() -> None:
    source = "e" + chr(0x0301)
    assert select_letter_mix_sites(source) == (1,)
    applied = apply_letter_alternating_mix(source)
    assert applied.startswith("e" + chr(0x0301))
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
    assert applied[1] == chr(0x0301)


def test_cafe_marks_precomposed_latin_letter() -> None:
    source = "caf" + chr(0x00E9)
    assert select_letter_mix_sites(source) == (0, 1, 2, 3)
    applied = process_text(source)
    assert applied != source
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source


def test_arabic_letters_stay_unsupported_to_avoid_joining_breaks() -> None:
    source = chr(0x0645) + chr(0x0646)
    assert select_letter_mix_sites(source) == ()
    result = transform_text(source)
    assert result.reason == REASON_UNSUPPORTED_DOMAIN
    assert result.output_text == source
    assert process_text("123.") == "123."
    assert transform_text("123.").reason == REASON_NO_ELIGIBLE_SITES
    assert transform_text(chr(0x00E9) * 3).first_unsupported == ""
    assert transform_text("I don" + chr(0x2019) + "t agree.").first_unsupported == "U+2019@5"


def test_ascii_english_sites_match_historical_ascii_selection() -> None:
    source = "I do not agree."
    live = select_letter_mix_sites(source)
    historical = select_letter_mix_sites(source, ascii_only=True)
    assert live == historical
    assert apply_letter_alternating_mix(source) != apply_historical_mark_letter_mix(source)
    mixed = "I do not agree " + chr(0x00E9) + "."
    assert len(select_letter_mix_sites(mixed)) == len(select_letter_mix_sites(mixed, ascii_only=True)) + 1


def test_hello_emoji_keeps_ascii_sites_and_adds_the_pictograph() -> None:
    source = "Hello " + chr(0x1F600)
    sites = select_letter_mix_sites(source)
    assert sites[-1] == 6
    assert source[sites[-1]] == chr(0x1F600)
    applied = apply_letter_alternating_mix(source)
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source


def test_mn_me_us_cf_leaves_unicode_sanitizer_spaces() -> None:
    source = "I do not agree."
    live = apply_letter_alternating_mix(source)
    mn_me_us = lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(live)))
    assert mn_me_us != source
    restored = strip_unicode_format_characters(mn_me_us)
    assert restored != source
    assert " " in restored
    historical = apply_historical_quad_layer_letter_mix(source)
    historical_restored = strip_unicode_format_characters(
        lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(historical)))
    )
    assert historical_restored == source
    cf_then_us = lm_watermarking_unicode_sanitizer(
        strip_unicode_format_characters(strip_enclosing_marks(strip_nonspacing_marks(live)))
    )
    assert cf_then_us == source
