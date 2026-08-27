from fuckmark.cli import process_text
from fuckmark.cycle8.compare import (
    CYCLE8_LETTER_ALT_ARM_ID,
    CYCLE8_MIX_ARM_IDS,
    CYCLE8_U034F_LETTER_ARM_ID,
    measure_carrier_arm,
)
from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_APPROVED_CARRIERS,
    LETTER_MIX_MAX_SELECTED,
    apply_letter_alternating_mix,
    hard_machine_intervals,
    select_letter_mix_sites,
)
from fuckmark.cycle8.registry import LETTER_CARRIER_MAX_SELECTED, apply_all_candidates, cycle8_letter_carrier_registry
from fuckmark.cycle8.sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.transforms.registry import release_transform_registry


def test_letter_mix_uses_alternating_carriers_and_keeps_visible_text() -> None:
    source = "Abcd"
    applied = apply_letter_alternating_mix(source)
    assert applied == "A\u034fb\ufe00c\u034fd\ufe00"
    assert is_carrier_insertion_v1(source, applied, LETTER_MIX_APPROVED_CARRIERS)
    assert project_visible_v1(applied, LETTER_MIX_APPROVED_CARRIERS) == source
    assert LETTER_MIX_MAX_SELECTED == LETTER_CARRIER_MAX_SELECTED == 192
    assert process_text(source) == apply_letter_alternating_mix(source)
    assert release_transform_registry().rules == ()


def test_letter_mix_reaches_unclosed_math_prose_and_blocks_numbers_and_urls() -> None:
    source = r"Keep going \[item 7 and we never wait at https://example.com/ab."
    letter = apply_all_candidates(cycle8_letter_carrier_registry(0x034F), source)
    mix = apply_letter_alternating_mix(source)
    letter_sites = select_letter_mix_sites(source)
    assert len(letter_sites) > letter.count("\u034f")
    assert mix.count("\u034f") + mix.count("\ufe00") == len(letter_sites)
    assert "7" in mix
    assert "https://example.com/ab" in project_visible_v1(mix, LETTER_MIX_APPROVED_CARRIERS)
    assert "https://example.com/ab" in mix.replace("\u034f", "").replace("\ufe00", "")
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
    assert int(measured["inserted_count"]) == mix.count("\u034f") + mix.count("\ufe00")
    assert int(measured["selected_count"]) == len(letter_sites)
    assert int(measured["protected_blocked_count"]) >= 1
    assert CYCLE8_MIX_ARM_IDS == ("identity", CYCLE8_U034F_LETTER_ARM_ID, CYCLE8_LETTER_ALT_ARM_ID)
    for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS:
        sanitized = sanitize_cycle8_scale_variant(variant, mix)
        assert sanitized == mix
        assert is_carrier_insertion_v1(source, sanitized, LETTER_MIX_APPROVED_CARRIERS)


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
