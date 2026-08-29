import unicodedata

from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import (
    strip_default_ignorable,
    strip_enclosing_marks,
    strip_nonspacing_marks,
    strip_other_controls,
)
from fuckmark.cycle8.compare import (
    CYCLE8_LETTER_ALT_ARM_ID,
    CYCLE8_MIX_ARM_IDS,
    CYCLE8_U034F_LETTER_ARM_ID,
    measure_carrier_arm,
)
from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    LETTER_MIX_CF_CODEPOINTS,
    LETTER_MIX_CF_PAYLOADS,
    LETTER_MIX_CONTROL_PAYLOADS,
    LETTER_MIX_INSERTIONS_PER_SITE,
    LETTER_MIX_MAX_SELECTED,
    LETTER_MIX_ME_PAYLOADS,
    apply_historical_triple_layer_letter_mix,
    apply_letter_alternating_mix,
    hard_machine_intervals,
    select_letter_mix_sites,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.cycle8.registry import apply_all_candidates, cycle8_letter_carrier_registry
from fuckmark.cycle8.sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.transforms.registry import release_transform_registry


def test_letter_mix_uses_alternating_carriers_and_keeps_visible_text() -> None:
    source = "Abcd"
    applied = apply_letter_alternating_mix(source)
    assert applied == (
        "A\u034f"
        + LETTER_MIX_CONTROL_PAYLOADS[0]
        + LETTER_MIX_ME_PAYLOADS[0]
        + LETTER_MIX_CF_PAYLOADS[0]
        + "b\ufe00"
        + LETTER_MIX_CONTROL_PAYLOADS[1]
        + LETTER_MIX_ME_PAYLOADS[0]
        + LETTER_MIX_CF_PAYLOADS[1]
        + "c\u034f"
        + LETTER_MIX_CONTROL_PAYLOADS[2]
        + LETTER_MIX_ME_PAYLOADS[0]
        + LETTER_MIX_CF_PAYLOADS[2]
        + "d\ufe00"
        + LETTER_MIX_CONTROL_PAYLOADS[3]
        + LETTER_MIX_ME_PAYLOADS[0]
        + LETTER_MIX_CF_PAYLOADS[3]
    )
    assert LETTER_MIX_INSERTIONS_PER_SITE == 4
    assert is_carrier_insertion_v1(source, applied, LETTER_MIX_APPROVED_CARRIERS)
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
    assert LETTER_MIX_MAX_SELECTED == 4096
    assert process_text(source) == apply_letter_alternating_mix(source)
    assert release_transform_registry().rules == ()
    assert strip_nonspacing_marks(applied) != source
    assert strip_default_ignorable(applied) != source


def test_letter_mix_reaches_unclosed_math_prose_and_blocks_numbers_and_urls() -> None:
    source = r"Keep going \[item 7 and we never wait at https://example.com/ab."
    letter = apply_all_candidates(cycle8_letter_carrier_registry(0x034F), source)
    mix = apply_letter_alternating_mix(source)
    letter_sites = select_letter_mix_sites(source)
    assert len(letter_sites) > letter.count("\u034f")
    assert mix.count("\u034f") + mix.count("\ufe00") == len(letter_sites)
    assert "7" in mix
    assert "https://example.com/ab" in project_visible_v1(mix, LETTER_MIX_APPROVED_CARRIERS)
    assert "https://example.com/ab" in mix
    intervals = hard_machine_intervals(source)
    assert any(source[start:end] == "7" for start, end in intervals)
    url = "https://example.com/ab"
    url_start = source.index(url)
    url_end = url_start + len(url)
    for index in letter_sites:
        assert index < url_start or index >= url_end
        assert source[index] != "7"
    assert project_visible_v1(mix, LETTER_MIX_APPROVED_CARRIERS) == source
    measured = measure_carrier_arm(
        arm_id=CYCLE8_LETTER_ALT_ARM_ID,
        source_sample_id="letter-mix",
        source_text=source,
    )
    assert measured["visible_ok"] is True
    assert int(measured["inserted_count"]) == len(letter_sites) * LETTER_MIX_INSERTIONS_PER_SITE
    assert int(measured["selected_count"]) == len(letter_sites)
    assert int(measured["protected_blocked_count"]) >= 1
    assert CYCLE8_MIX_ARM_IDS == ("identity", CYCLE8_U034F_LETTER_ARM_ID, CYCLE8_LETTER_ALT_ARM_ID)
    for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS:
        sanitized = sanitize_cycle8_scale_variant(variant, mix)
        assert is_carrier_insertion_v1(source, sanitized, LETTER_MIX_APPROVED_CARRIERS)
        if "cf_strip" in variant:
            assert sanitized != mix
            assert sanitized != source
        else:
            assert sanitized == mix


def test_letter_mix_inserts_inside_quotes_and_respects_cap() -> None:
    quoted = 'He said "hello world" and left.'
    applied = apply_letter_alternating_mix(quoted)
    interior = applied[applied.index('"') + 1 : applied.rindex('"')]
    assert "\u034f" in interior or "\ufe00" in interior
    source = "abcdefghijklmnopqrstuvwxyz" * 12
    capped = apply_letter_alternating_mix(source, max_selected=16)
    assert capped.count("\u034f") + capped.count("\ufe00") == 16
    assert project_visible_v1(capped, LETTER_MIX_APPROVED_CARRIERS) == source
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert release_transform_registry().rules == ()


def test_live_four_layer_resists_mn_me_unicode_sanitizer() -> None:
    source = "I do not agree."
    live = apply_letter_alternating_mix(source)
    historical = apply_historical_triple_layer_letter_mix(source)
    mn_me_us = lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(live)))
    di_me_us = lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_default_ignorable(live)))
    mn_me_cc = strip_other_controls(strip_enclosing_marks(strip_nonspacing_marks(live)))
    assert project_visible_v1(live, LETTER_MIX_APPROVED_CARRIERS) == source
    assert mn_me_us != source
    assert di_me_us != source
    assert mn_me_cc != source
    assert any(ord(character) in LETTER_MIX_CF_CODEPOINTS for character in mn_me_us)
    assert lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_nonspacing_marks(historical))) == source
    assert strip_other_controls(strip_enclosing_marks(strip_nonspacing_marks(historical))) == source


def test_live_cf_payloads_are_assigned_format_controls() -> None:
    assert LETTER_MIX_CF_CODEPOINTS == tuple(range(0x13430, 0x13439))
    assert 0x13439 not in LETTER_MIX_CF_CODEPOINTS
    assert LETTER_MIX_CF_PAYLOADS == tuple(chr(codepoint) for codepoint in LETTER_MIX_CF_CODEPOINTS)
    for payload in LETTER_MIX_CF_PAYLOADS:
        assert unicodedata.category(payload) == "Cf"
        assert unicodedata.name(payload)
