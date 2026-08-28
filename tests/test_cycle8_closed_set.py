import json
from pathlib import Path

import pytest

from fuckmark.cycle8.benchmark import sanitize_benchmark_stress
from fuckmark.cycle8.closed_set import (
    CYCLE8_CLOSED_SET_HASH,
    CYCLE8_CLOSED_SET_PATH,
    CYCLE8_CLOSED_SET_VERSION,
    assert_invisible_carrier_closed_set_committed,
    scan_invisible_carrier_closed_set,
)
from fuckmark.product.rendering import chrome_executable, compare_chrome_pre_screenshots
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.hashing import sha256_json
from fuckmark.sanitizer_robustness import strip_unicode_format_characters


def test_invisible_carrier_closed_set_has_no_priority_zero_safe_survivor() -> None:
    disk = json.loads((Path(__file__).resolve().parents[1] / CYCLE8_CLOSED_SET_PATH).read_text(encoding="utf-8"))
    payload = scan_invisible_carrier_closed_set()
    assert disk["closed_set_hash"] == sha256_json(
        {key: value for key, value in disk.items() if key != "closed_set_hash"}
    )
    assert disk["closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert disk["algorithm_version"] == CYCLE8_CLOSED_SET_VERSION
    assert disk["stronger_priority_zero_safe_mechanism"] is None
    assert disk["width0_assigned_other"] == []
    assert disk["width0_assigned_mn"] == 1985
    assert disk["width0_assigned_me"] == 13
    assert disk["width0_assigned_cf_not_default_ignorable"] == 32
    assert disk["mix_carriers_are_width0_mn_default_ignorable"] is True
    assert disk["non_di_cf_die_to_frozen_cf_strip"] is True
    assert disk["me_survives_mn_strip"] is True
    assert disk["me_survives_default_ignorable_strip"] is True
    assert disk["me_survives_frozen_cf_strip"] is True
    assert disk["me_rejected_for_rendering"] is True
    assert payload["stronger_priority_zero_safe_mechanism"] is None
    assert payload["width0_assigned_other"] == []
    assert payload["width0_assigned_me"] == 13
    assert payload["mix_carriers_are_width0_mn_default_ignorable"] is True
    if payload["width0_assigned_mn"] == disk["width0_assigned_mn"]:
        assert disk == payload
        assert payload["closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert_invisible_carrier_closed_set_committed()
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    assert sanitize_benchmark_stress("mn_strip", transformed) != source
    assert sanitize_benchmark_stress("default_ignorable_strip", transformed) != source
    assert strip_unicode_format_characters(transformed) == transformed


def test_all_width0_enclosing_marks_change_chromium_pre_pixels() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    disk = json.loads((Path(__file__).resolve().parents[1] / CYCLE8_CLOSED_SET_PATH).read_text(encoding="utf-8"))
    labels = disk["width0_assigned_me_labels"]
    assert labels == [
        "U+0488",
        "U+0489",
        "U+1ABE",
        "U+20DD",
        "U+20DE",
        "U+20DF",
        "U+20E0",
        "U+20E2",
        "U+20E3",
        "U+20E4",
        "U+A670",
        "U+A671",
        "U+A672",
    ]
    original = "I do not agree."
    for label in labels:
        codepoint = int(label[2:], 16)
        comparison = compare_chrome_pre_screenshots(original, f"I{chr(codepoint)} do not agree.")
        if comparison.status == "UNKNOWN":
            pytest.skip(comparison.detail)
        assert comparison.status == "REJECTED"
        assert comparison.equal is False
