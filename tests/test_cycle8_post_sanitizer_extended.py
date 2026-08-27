import json
from pathlib import Path

import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.benchmark import sanitize_benchmark_stress
from fuckmark.cycle8.closed_set import CYCLE8_CLOSED_SET_HASH
from fuckmark.cycle8.control_carrier import CYCLE8_CONTROL_CARRIER_HASH, required_sanitizers_keep
from fuckmark.cycle8.feasibility import CYCLE8_FEASIBILITY_HASH
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix
from fuckmark.cycle8.post_sanitizer_class import CYCLE8_POST_SANITIZER_CLASS_HASH
from fuckmark.cycle8.post_sanitizer_extended import (
    CYCLE8_POST_SANITIZER_EXTENDED_HASH,
    CYCLE8_POST_SANITIZER_EXTENDED_PATH,
    CYCLE8_POST_SANITIZER_EXTENDED_VERSION,
    DESIGNED_BLANK_PROBES,
    HANGUL_JAMO_FILLER_SEQUENCE,
    LM_CHROMIUM_PROBES,
    MC_CHROMIUM_PROBES,
    NFKC_COLLAPSE_PROBES,
    UCD15_DEFAULT_IGNORABLE_RANGES,
    assert_post_sanitizer_extended_class_committed,
    post_sanitizer_extended_class_payload,
)
from fuckmark.cycle8.publishability import CYCLE8_MIX_PUBLISHABILITY_HASH, mix_is_product_publishable
from fuckmark.cycle8.unicode_meta import DEFAULT_IGNORABLE_RANGES_V1
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.rendering import chrome_executable, compare_chrome_pre_screenshots
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


def _load() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / CYCLE8_POST_SANITIZER_EXTENDED_PATH).read_text(encoding="utf-8"))


def test_post_sanitizer_extended_class_has_no_conjunction_survivor() -> None:
    disk = _load()
    payload = post_sanitizer_extended_class_payload()
    body = {key: value for key, value in disk.items() if key != "extended_class_hash"}
    assert disk["extended_class_hash"] == sha256_json(body) == CYCLE8_POST_SANITIZER_EXTENDED_HASH
    assert disk["algorithm_version"] == CYCLE8_POST_SANITIZER_EXTENDED_VERSION
    assert disk["does_not_repeat_assigned_width0_scan"] is True
    assert disk["does_not_reopen_h13_classification"] is True
    assert disk["assigned_width0_closed_set_hash"] == CYCLE8_CLOSED_SET_HASH
    assert disk["assigned_width0_feasibility_hash"] == CYCLE8_FEASIBILITY_HASH
    assert disk["control_carrier_hash"] == CYCLE8_CONTROL_CARRIER_HASH
    assert disk["post_sanitizer_class_hash"] == CYCLE8_POST_SANITIZER_CLASS_HASH
    assert disk["mix_publishability_hash"] == CYCLE8_MIX_PUBLISHABILITY_HASH
    assert disk["mix_sanitizer_gate"] == "FAIL"
    assert disk["di_list_complete_vs_ucd15"] is True
    assert DEFAULT_IGNORABLE_RANGES_V1 == UCD15_DEFAULT_IGNORABLE_RANGES
    assert disk["mc_width0_survivor_labels"] == []
    assert disk["lm_width0_survivor_labels"] == []
    assert disk["mc_sanitizer_survivor_count"] >= 1
    assert disk["lm_sanitizer_survivor_count"] >= 1
    assert disk["hangul_jamo_filler_sequence_required_sanitizers_keep"] is False
    assert disk["dejavu_sans_mono_zero_advance_empty_assigned_survivors"] == []
    assert disk["conjunction_sanitizer_pass_chromium_verified_ordinary_text"] == []
    assert disk["stronger_priority_zero_safe_mechanism"] is None
    assert disk["product_authorized"] is False
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["spent_confirmation_corpora_not_reused"] is True
    if payload["mc_sanitizer_survivor_count"] == disk["mc_sanitizer_survivor_count"]:
        assert payload == disk
    assert_post_sanitizer_extended_class_committed()
    by_id = {row["id"]: row for row in disk["classes"]}
    assert by_id["mc_spacing_combining_insertion"]["required_sanitizers"] == "PASS"
    assert by_id["mc_spacing_combining_insertion"]["chromium_pre"] == "REJECTED"
    assert by_id["lm_modifier_letter_insertion"]["chromium_pre"] == "REJECTED"
    assert by_id["designed_blank_or_gap_filler"]["chromium_pre"] == "REJECTED"
    assert by_id["font_zero_advance_empty_glyph"]["required_sanitizers"] == "FAIL"
    assert by_id["hangul_filler_sequence"]["required_sanitizers"] == "FAIL"
    assert by_id["nfkc_compatibility_lookalike"]["required_sanitizers"] == "FAIL"
    assert by_id["cc_csi_filtered_subset"]["chromium_pre"] == "HOST_DEPENDENT"
    assert by_id["cc_csi_filtered_subset"]["ordinary_plain_text"] == "FAIL"
    assert mix_is_product_publishable() is False
    assert process_text("I do not agree.") == "I do not agree."
    assert product_approved_carriers_v1() == frozenset()
    assert release_transform_registry().rules == ()
    for row in disk["classes"]:
        conjunction = (
            row["required_sanitizers"] == "PASS"
            and row["chromium_pre"] == "VERIFIED"
            and row["ordinary_plain_text"] == "PASS"
        )
        assert conjunction is False


def test_extended_class_probes_match_required_sanitizer_contract() -> None:
    for codepoint in (*MC_CHROMIUM_PROBES, *LM_CHROMIUM_PROBES, *DESIGNED_BLANK_PROBES):
        assert required_sanitizers_keep(f"A{chr(codepoint)}B") is True
    for codepoint in NFKC_COLLAPSE_PROBES:
        assert required_sanitizers_keep(f"A{chr(codepoint)}B") is False
    assert required_sanitizers_keep(f"A{HANGUL_JAMO_FILLER_SEQUENCE}B") is False
    source = "I do not agree."
    mix = apply_letter_alternating_mix(source)
    assert sanitize_benchmark_stress("mn_strip", mix) == source
    assert sanitize_benchmark_stress("default_ignorable_strip", mix) == source


def test_extended_class_chromium_probes_change_pre_pixels() -> None:
    if chrome_executable() is None:
        pytest.skip("chromium is not available")
    original = "I do not agree."
    for codepoint in (*MC_CHROMIUM_PROBES, *LM_CHROMIUM_PROBES, DESIGNED_BLANK_PROBES[0], DESIGNED_BLANK_PROBES[4], 0x13441):
        comparison = compare_chrome_pre_screenshots(original, f"I{chr(codepoint)} do not agree.")
        if comparison.status == "UNKNOWN":
            pytest.skip(comparison.detail)
        assert comparison.status == "REJECTED"
        assert comparison.equal is False
    cgj = compare_chrome_pre_screenshots(original, "I\u034f do not agree.")
    if cgj.status == "UNKNOWN":
        pytest.skip(cgj.detail)
    assert cgj.status == "VERIFIED"
    assert cgj.equal is True
    control = compare_chrome_pre_screenshots(original, "I\u007f do not agree.")
    if control.status == "UNKNOWN":
        pytest.skip(control.detail)
    assert control.status in {"VERIFIED", "REJECTED"}


def test_h14_local_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[1] / "evidence" / "h14-local"
    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    files = {line.split()[-1]: line.split()[0] for line in sums if line}
    assert set(files) == {
        "README.md",
        "summary.json",
        "chromium-probes.json",
        "lm-chromium-probes.json",
    }
    for name, digest in files.items():
        assert sha256_file(root / name) == digest
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["mix_sanitizer_gate"] == "FAIL"
    assert summary["product_authorized"] is False
    assert summary["stronger_priority_zero_safe_mechanism"] is None
    assert summary["pixel_equal_and_sanitizer_keep"] == [
        "cc_del",
        "cc_nul",
        "cc_c1_no_device_csi_filtered",
    ]
