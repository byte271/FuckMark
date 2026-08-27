import json
from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import sanitize_benchmark_stress
from fuckmark.cycle8.closed_set import CYCLE8_CLOSED_SET_HASH
from fuckmark.cycle8.control_carrier import (
    CONTROL_MIX_ELIGIBLE_CODEPOINTS,
    CYCLE8_CONTROL_CARRIER_HASH,
    CYCLE8_CONTROL_CARRIER_PATH,
    CYCLE8_CONTROL_CARRIER_VERSION,
    HOSTILE_CONTROL_CODEPOINTS,
    ISO6429_DEVICE_CONTROL_CODEPOINTS,
    LAYOUT_CONTROL_CODEPOINTS,
    apply_required_sanitizer_bundle,
    assert_control_carrier_scan_committed,
    control_display_column_width,
    is_control_mix_eligible,
    is_iso6429_device_control,
    required_sanitizers_keep,
    scan_control_carrier_class,
)
from fuckmark.cycle8.control_mix import (
    CONTROL_MIX_APPROVED_CARRIERS,
    apply_control_alternating_mix,
)
from fuckmark.cycle8.feasibility import CYCLE8_FEASIBILITY_HASH
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.hashing import sha256_json
from fuckmark.cycle8.benchmark_render import compare_chrome_surface
from fuckmark.product.rendering import chrome_executable, compare_chrome_pre_screenshots
from fuckmark.product.roundtrip import display_column_width
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.sanitizer_robustness import strip_unicode_format_characters
from fuckmark.transforms.registry import release_transform_registry


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_CONTROL_CARRIER_PATH).read_text(encoding="utf-8"))


def test_control_carrier_scan_keeps_width0_closed_and_finds_cc_survivors() -> None:
    disk = _load()
    payload = scan_control_carrier_class()
    body = {key: value for key, value in disk.items() if key != "control_carrier_hash"}
    assert disk["control_carrier_hash"] == sha256_json(body) == CYCLE8_CONTROL_CARRIER_HASH
    assert disk["algorithm_version"] == CYCLE8_CONTROL_CARRIER_VERSION
    assert disk["assigned_width0_closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert disk["assigned_width0_feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert disk["assigned_width0_stronger_mechanism"] is None
    assert disk["product_authorized"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["eligible_count"] == 32
    assert disk["eligible_required_sanitizers_keep"] is True
    assert disk["eligible_are_cc"] is True
    assert disk["eligible_not_default_ignorable"] is True
    assert disk["eligible_product_width_delta_one"] is True
    assert disk["eligible_research_width_delta_zero"] is True
    assert disk["iso6429_device_controls_remain_in_eligible_set"] is True
    assert disk["product_display_width_proxy"] == "FAIL"
    assert disk["chromium_pre_pixels"] == "HOST_DEPENDENT"
    assert disk["terminal_pixels"] == "UNKNOWN"
    assert "U+009B" in disk["iso6429_device_control_codepoints"]
    assert "U+009B" in disk["eligible_codepoints"]
    assert "U+007F" in disk["eligible_codepoints"]
    assert "U+0080" in disk["eligible_codepoints"]
    assert "U+0085" not in disk["eligible_codepoints"]
    assert "U+0000" not in disk["eligible_codepoints"]
    assert "U+000A" not in disk["eligible_codepoints"]
    assert payload == disk
    assert_control_carrier_scan_committed()
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
    assert release_transform_registry().rules == ()


def test_eligible_controls_are_policy_filtered_and_survive_required_sanitizers() -> None:
    assert 0x007F in CONTROL_MIX_ELIGIBLE_CODEPOINTS
    assert 0x0080 in CONTROL_MIX_ELIGIBLE_CODEPOINTS
    assert 0x009F in CONTROL_MIX_ELIGIBLE_CODEPOINTS
    assert 0x0085 not in CONTROL_MIX_ELIGIBLE_CODEPOINTS
    assert 0x0085 in LAYOUT_CONTROL_CODEPOINTS
    assert 0x0000 in HOSTILE_CONTROL_CODEPOINTS
    assert is_control_mix_eligible(0x0085) is False
    assert is_control_mix_eligible(0x0000) is False
    assert is_control_mix_eligible(0x0001) is False
    assert is_iso6429_device_control(0x009B) is True
    assert 0x009B in ISO6429_DEVICE_CONTROL_CODEPOINTS
    assert 0x009B in CONTROL_MIX_ELIGIBLE_CODEPOINTS
    source = "I do not agree."
    control = apply_control_alternating_mix(source)
    mix = apply_letter_alternating_mix(source)
    assert control != source
    assert mix != source
    assert required_sanitizers_keep(control) is True
    assert apply_required_sanitizer_bundle(control) == control
    assert sanitize_benchmark_stress("mn_strip", control) == control
    assert sanitize_benchmark_stress("default_ignorable_strip", control) == control
    assert strip_unicode_format_characters(control) == control
    assert sanitize_benchmark_stress("mn_strip", mix) == source
    assert sanitize_benchmark_stress("default_ignorable_strip", mix) == source
    assert display_column_width(source) != display_column_width(control)
    assert control_display_column_width(source) == control_display_column_width(control)
    assert process_text(source) == apply_letter_alternating_mix(source)
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})


def test_control_mix_carriers_match_eligible_set() -> None:
    assert CONTROL_MIX_APPROVED_CARRIERS == CONTROL_MIX_ELIGIBLE_CODEPOINTS
    assert len(CONTROL_MIX_APPROVED_CARRIERS) == 32


def test_control_mix_chromium_pixels_are_host_dependent() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    source = "I do not agree."
    control = apply_control_alternating_mix(source)
    comparison = compare_chrome_pre_screenshots(source, control)
    if comparison.status == "UNKNOWN":
        pytest.skip(comparison.detail)
    assert comparison.status in {"VERIFIED", "REJECTED"}
    for surface in ("textarea", "contenteditable"):
        rendered = compare_chrome_surface(source, control, surface)
        if rendered["status"] == "UNKNOWN":
            pytest.skip(str(rendered["detail"]))
        assert rendered["status"] in {"VERIFIED", "REJECTED"}
    tofu = compare_chrome_pre_screenshots(source, "I\u0001 do not agree.")
    if tofu.status == "UNKNOWN":
        pytest.skip(tofu.detail)
    assert tofu.status == "REJECTED"
    assert tofu.equal is False
    blank = compare_chrome_pre_screenshots(source, "I\u2800 do not agree.")
    if blank.status == "UNKNOWN":
        pytest.skip(blank.detail)
    assert blank.status == "REJECTED"
    assert blank.equal is False
    for codepoint in (0x007F, 0x0080, 0x009F):
        row = compare_chrome_pre_screenshots(source, f"I{chr(codepoint)} do not agree.")
        if row.status == "UNKNOWN":
            pytest.skip(row.detail)
        assert row.status in {"VERIFIED", "REJECTED"}
