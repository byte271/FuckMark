import json
from pathlib import Path
import unicodedata

import pytest

from fuckmark.cycle8.benchmark import sanitize_benchmark_stress
from fuckmark.cycle8.feasibility import (
    CYCLE8_FEASIBILITY_HASH,
    CYCLE8_FEASIBILITY_PATH,
    CYCLE8_FEASIBILITY_VERSION,
    ENCLOSING_MARK_PROBE,
    assert_invisible_carrier_feasibility_committed,
    scan_invisible_carrier_feasibility,
)
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.cycle8.unicode_meta import is_default_ignorable_v1
from fuckmark.hashing import sha256_json
from fuckmark.product.rendering import chrome_executable, compare_chrome_pre_screenshots


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_FEASIBILITY_PATH).read_text(encoding="utf-8"))


def test_invisible_carrier_feasibility_spec_finds_no_stronger_product_mechanism() -> None:
    disk = _load()
    payload = scan_invisible_carrier_feasibility()
    assert disk["feasibility_hash"] == sha256_json(
        {key: value for key, value in disk.items() if key != "feasibility_hash"}
    )
    assert disk["feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert disk["algorithm_version"] == CYCLE8_FEASIBILITY_VERSION
    assert disk["stronger_invisible_product_mechanism"] is None
    assert disk["other_non_mn_cf_count"] == 0
    assert disk["other_non_mn_cf"] == []
    assert disk["survives_mn_cf_and_default_ignorable_while_invisible"] is False
    assert disk["enclosing_marks_rejected_rendering"] is True
    assert disk["assigned_enclosing_me"] == 13
    assert f"U+{ENCLOSING_MARK_PROBE:04X}" in disk["enclosing_me_labels"]
    assert disk["mix_carriers_are_mn_and_default_ignorable"] is True
    assert payload["stronger_invisible_product_mechanism"] is None
    assert payload["other_non_mn_cf_count"] == 0
    assert payload["other_non_mn_cf"] == []
    assert payload["assigned_enclosing_me"] == 13
    assert payload["survives_mn_cf_and_default_ignorable_while_invisible"] is False
    if payload["assigned_visible_or_control"] == disk["assigned_visible_or_control"]:
        assert disk == payload
        assert payload["feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert_invisible_carrier_feasibility_committed()


def test_mix_carriers_are_nonspacing_and_default_ignorable() -> None:
    for character in ("\u034f", "\ufe00"):
        assert unicodedata.category(character) == "Mn"
        assert is_default_ignorable_v1(ord(character)) is True
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    assert sanitize_benchmark_stress("mn_strip", transformed) != source
    assert sanitize_benchmark_stress("default_ignorable_strip", transformed) != source
    enclosing = f"A{chr(ENCLOSING_MARK_PROBE)}B"
    assert sanitize_benchmark_stress("mn_strip", enclosing) == enclosing
    assert sanitize_benchmark_stress("default_ignorable_strip", enclosing) == enclosing


def test_enclosing_mark_probe_changes_chromium_pre_pixels() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    original = "AB"
    transformed = f"A{chr(ENCLOSING_MARK_PROBE)}B"
    comparison = compare_chrome_pre_screenshots(original, transformed)
    if comparison.status == "UNKNOWN":
        pytest.skip(comparison.detail)
    assert comparison.status == "REJECTED"
    assert comparison.equal is False
