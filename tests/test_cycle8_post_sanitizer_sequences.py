import json
from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import sanitize_benchmark_stress, strip_nonspacing_marks
from fuckmark.cycle8.closed_set import CYCLE8_CLOSED_SET_HASH
from fuckmark.cycle8.control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from fuckmark.cycle8.feasibility import CYCLE8_FEASIBILITY_HASH
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.cycle8.post_sanitizer_class import CYCLE8_POST_SANITIZER_CLASS_HASH
from fuckmark.cycle8.post_sanitizer_extended import CYCLE8_POST_SANITIZER_EXTENDED_HASH
from fuckmark.cycle8.post_sanitizer_sequences import (
    CYCLE8_POST_SANITIZER_SEQUENCES_HASH,
    CYCLE8_POST_SANITIZER_SEQUENCES_PATH,
    CYCLE8_POST_SANITIZER_SEQUENCES_VERSION,
    HANGUL_L_V_SEQUENCE,
    JOINING_CONNECTOR_PROBES,
    LRI_PDI_WRAP,
    MIX_PLUS_DEL_SEQUENCE,
    PREPEND_CHROMIUM_PROBES,
    SEQUENCE_SOURCE,
    TATWEEL,
    UAX29_PREPEND_CODEPOINTS,
    assert_post_sanitizer_sequences_committed,
    hangul_lv_composed_required_sanitizers_keep,
    hangul_lv_required_sanitizers_keep,
    mix_plus_del_mn_remainder,
    post_sanitizer_sequences_payload,
    scan_prepend_survivors,
)
from fuckmark.cycle8.publishability import CYCLE8_MIX_PUBLISHABILITY_HASH, mix_is_product_publishable
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.rendering import chrome_executable, compare_chrome_pre_screenshots
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_POST_SANITIZER_SEQUENCES_PATH).read_text(encoding="utf-8"))


def test_post_sanitizer_sequences_has_no_conjunction_survivor() -> None:
    disk = _load()
    payload = post_sanitizer_sequences_payload()
    body = {key: value for key, value in disk.items() if key != "sequence_class_hash"}
    assert disk["sequence_class_hash"] == sha256_json(body) == CYCLE8_POST_SANITIZER_SEQUENCES_HASH
    assert disk["algorithm_version"] == CYCLE8_POST_SANITIZER_SEQUENCES_VERSION
    assert disk["does_not_repeat_assigned_width0_scan"] is True
    assert disk["does_not_repeat_h14_single_codepoint_sweep"] is True
    assert disk["assigned_width0_closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert disk["assigned_width0_feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert disk["control_carrier_hash"] == CYCLE8_CONTROL_CARRIER_HASH
    assert disk["post_sanitizer_class_hash"] == CYCLE8_POST_SANITIZER_CLASS_HASH
    assert disk["post_sanitizer_extended_hash"] == CYCLE8_POST_SANITIZER_EXTENDED_HASH
    assert disk["mix_publishability_hash"] == CYCLE8_MIX_PUBLISHABILITY_HASH
    assert disk["mix_sanitizer_gate"] == "FAIL"
    assert disk["hangul_lv_sequence_required_sanitizers_keep"] is False
    assert disk["hangul_lv_composed_required_sanitizers_keep"] is False
    assert disk["lri_wrap_required_sanitizers_keep"] is False
    assert disk["ascii_plus_mc_nfc_hit_count"] == 0
    assert disk["mix_plus_del_mn_remainder"] == ["U+007F"]
    assert disk["dejavu_sans_mono_zero_advance_keep_including_composites"] == []
    assert disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] == []
    assert disk["stronger_priority_zero_safe_mechanism"] is None
    assert disk["product_authorized"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["spent_confirmation_corpora_not_reused"] is True
    if payload["prepend_sanitizer_survivor_count"] == disk["prepend_sanitizer_survivor_count"]:
        assert payload == disk
    assert_post_sanitizer_sequences_committed()
    by_id = {row["id"]: row for row in disk["classes"]}
    assert by_id["grapheme_prepend_plus_base"]["required_sanitizers"] == "PASS"
    assert by_id["grapheme_prepend_plus_base"]["chromium_pre"] == "REJECTED"
    assert by_id["joining_connector_sequence"]["chromium_pre"] == "REJECTED"
    assert by_id["hangul_lv_composition_sequence"]["required_sanitizers"] == "FAIL"
    assert by_id["bidi_isolate_wrap_sequence"]["required_sanitizers"] == "FAIL"
    assert by_id["iso6429_escape_sequence"]["ordinary_plain_text"] == "FAIL"
    assert by_id["partial_sanitizer_remainder"]["product"] == "FAIL"
    assert by_id["font_gsub_ligature_sequence"]["required_sanitizers"] == "FAIL"
    assert mix_is_product_publishable() is False
    assert process_text("I do not agree.") == apply_letter_alternating_mix("I do not agree.")
    assert product_approved_carriers_v1() == frozenset({0x034F, 0xFE00})
    assert release_transform_registry().rules == ()
    for row in disk["classes"]:
        conjunction = (
            row["required_sanitizers"] == "PASS"
            and row["chromium_pre"] == "VERIFIED"
            and row["ordinary_plain_text"] == "PASS"
        )
        assert conjunction is False


def test_sequence_probes_match_required_sanitizer_contract() -> None:
    assert hangul_lv_required_sanitizers_keep() is False
    assert hangul_lv_composed_required_sanitizers_keep() is False
    assert required_sanitizers_keep(LRI_PDI_WRAP) is False
    assert required_sanitizers_keep("I" + TATWEEL + " do not agree.") is True
    assert mix_plus_del_mn_remainder() == "\u007f"
    transformed = "I" + MIX_PLUS_DEL_SEQUENCE + " do not agree."
    assert strip_nonspacing_marks(transformed) == "I\u007f do not agree."
    assert required_sanitizers_keep("I\u007f do not agree.") is True
    source = SEQUENCE_SOURCE
    mix = apply_letter_alternating_mix(source)
    assert sanitize_benchmark_stress("mn_strip", mix) == source
    assert sanitize_benchmark_stress("default_ignorable_strip", mix) == source
    live = scan_prepend_survivors()
    if "U+0D4E" in live:
        assert required_sanitizers_keep(chr(0x0D4E) + SEQUENCE_SOURCE) is True
    for codepoint in JOINING_CONNECTOR_PROBES:
        assert required_sanitizers_keep(f"I{chr(codepoint)} do not agree.") is True
    assert HANGUL_L_V_SEQUENCE == "\u1100\u1161"
    assert len(UAX29_PREPEND_CODEPOINTS) >= 13


def test_sequence_chromium_probes_match_recorded_classes() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    original = SEQUENCE_SOURCE
    prepend = chr(PREPEND_CHROMIUM_PROBES[0]) + original
    comparison = compare_chrome_pre_screenshots(original, prepend)
    if comparison.status == "UNKNOWN":
        pytest.skip(comparison.detail)
    assert comparison.status == "REJECTED"
    tatweel = compare_chrome_pre_screenshots(original, "I" + TATWEEL + " do not agree.")
    if tatweel.status == "UNKNOWN":
        pytest.skip(tatweel.detail)
    assert tatweel.status == "REJECTED"
    wrap = compare_chrome_pre_screenshots(original, LRI_PDI_WRAP)
    if wrap.status == "UNKNOWN":
        pytest.skip(wrap.detail)
    assert wrap.status == "VERIFIED"
    mix = compare_chrome_pre_screenshots(original, apply_letter_alternating_mix(original))
    if mix.status == "UNKNOWN":
        pytest.skip(mix.detail)
    assert mix.status == "VERIFIED"
    remainder = compare_chrome_pre_screenshots(original, "I\u007f do not agree.")
    if remainder.status == "UNKNOWN":
        pytest.skip(remainder.detail)
    assert remainder.status in {"VERIFIED", "REJECTED"}
    escape = compare_chrome_pre_screenshots(original, "I\x1b[0m do not agree.")
    if escape.status == "UNKNOWN":
        pytest.skip(escape.detail)
    assert escape.status == "REJECTED"
    affirm = "I do not affirm."
    broken = "I do not aff\u034firm."
    liga = compare_chrome_pre_screenshots(affirm, broken)
    if liga.status == "UNKNOWN":
        pytest.skip(liga.detail)
    assert liga.status == "VERIFIED"


def test_h15_local_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[1] / "evidence" / "h15-local"
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    files = {line.split()[-1]: line.split()[0] for line in sums if line}
    assert set(files) == {
        "README.md",
        "summary.json",
        "chromium-probes.json",
    }
    for name, digest in files.items():
        assert sha256_file(root / name) == digest
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["mix_sanitizer_gate"] == "FAIL"
    assert summary["product_authorized"] is False
    assert summary["stronger_priority_zero_safe_mechanism"] is None
    assert summary["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] == []
