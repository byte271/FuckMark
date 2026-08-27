from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from fuckmark.cycle8.benchmark import strip_default_ignorable, strip_nonspacing_marks
from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.threat_model_audit import (
    CYCLE8_THREAT_MODEL_AUDIT_HASH,
    CYCLE8_THREAT_MODEL_AUDIT_PATH,
    DEPLOYABILITY_CORPUS,
    TOKENIZER_OBSERVATIONS,
    assert_threat_model_audit_committed,
    ascii_domain_is_normalization_fixed_point,
    contract_stress_only_sanitizers,
    control_required_sanitizer_fixed_points,
    gate_promotes_stress_only_sanitizers,
    iter_shaping_invisible_codepoints,
    lm_watermarking_unicode_sanitizer,
    load_threat_model_audit,
    proposed_gate_status_on_existing_evidence,
    real_sanitizer_detector_observations,
    real_world_sanitizer_observations,
    render_identical_ascii_substitutes,
    sanitizer_deployability_damage,
    shaping_invisible_all_stripped_by_required_bundle,
    shaping_invisible_categories,
    shaping_invisible_codepoint_count,
    substitution_class_survivors,
    threat_model_audit_payload,
)
from fuckmark.cycle8.publishability import measure_mix_fixtures
from fuckmark.product.visible_projection import product_approved_carriers_v1
from fuckmark.transforms.registry import release_transform_registry


def test_threat_model_audit_spec_is_committed_and_frozen():
    assert Path(CYCLE8_THREAT_MODEL_AUDIT_PATH).is_file()
    assert_threat_model_audit_committed()
    disk = load_threat_model_audit()
    assert disk["audit_hash"] == CYCLE8_THREAT_MODEL_AUDIT_HASH
    assert disk == threat_model_audit_payload()


def test_audit_does_not_authorize_a_product_mechanism():
    disk = load_threat_model_audit()
    assert disk["product_authorized"] is False
    assert disk["stronger_priority_zero_safe_mechanism"] is None
    assert disk["mix_gate_not_rewritten"] is True
    assert disk["mix_sanitizer_gate"] == "FAIL"
    assert disk["required_sanitizer_bundle_not_weakened"] is True
    assert disk["spent_confirmation_corpora_not_reused"] is True
    assert disk["proposed_gate_v2"]["status"] == "proposal_only_not_active"
    assert disk["proposed_gate_v2"]["formalized_as"] == "cycle8-publishability-gate-v2"
    assert disk["closure"]["original_h16_scan_overclaimed_twelve_contexts"] is True
    assert disk["closure"]["shaping_contexts_scanned"] == 1
    assert disk["closure"]["shaping_contexts_advertised"] == 12
    assert disk["closure"]["twelve_context_rescan_status"] == "recorded"
    assert disk["closure"]["twelve_context_invisible_count"] == 396
    assert disk["closure"]["twelve_context_intersection_count"] == 0
    assert disk["proposed_gate_v2"]["formalization_status"] == "confirmed_not_product_authorized"


def test_required_sanitizer_bundle_is_unchanged_by_this_cycle():
    assert required_sanitizers_keep("I\u034f do not agree.") is False
    assert required_sanitizers_keep("I\ufe00 do not agree.") is False
    assert required_sanitizers_keep("I\u200b do not agree.") is False
    assert required_sanitizers_keep("I do not agree.") is True


def test_mix_still_fails_only_on_the_stress_only_sanitizers():
    measured = measure_mix_fixtures()
    assert measured["frozen_sanitizer_total"] > 0
    assert measured["frozen_sanitizer_survive"] == measured["frozen_sanitizer_total"]
    assert measured["mn_strip_kills"] == measured["stress_total"]
    assert measured["default_ignorable_strip_kills"] == measured["stress_total"]
    assert measured["nfkd_kills"] == 0


def test_every_invisible_codepoint_is_mn_or_cf():
    categories = shaping_invisible_categories()
    assert set(categories) == {"Mn", "Cf"}
    assert shaping_invisible_codepoint_count() == 396
    assert sum(categories.values()) == 396


def test_invisible_set_and_required_bundle_are_complementary():
    assert shaping_invisible_all_stripped_by_required_bundle() is True
    for codepoint in iter_shaping_invisible_codepoints():
        assert required_sanitizers_keep(f"I{chr(codepoint)} do not agree.") is False


def test_substitution_class_has_no_sanitizer_survivor():
    substitutes = render_identical_ascii_substitutes()
    assert len(substitutes) == 14
    for codepoint in substitutes:
        assert unicodedata.normalize("NFKC", chr(codepoint)) == " "
    assert substitution_class_survivors() == ()


def test_ascii_input_domain_has_no_reencoding_freedom():
    assert ascii_domain_is_normalization_fixed_point() is True


def test_only_control_characters_remain_in_the_whole_space():
    survivors = control_required_sanitizer_fixed_points()
    assert len(survivors) == 63
    assert all(unicodedata.category(chr(cp)) == "Cc" for cp in survivors)
    assert 0x007F in survivors
    assert 0x0080 in survivors


def test_gate_promotes_contract_stress_only_sanitizers():
    assert contract_stress_only_sanitizers() == (
        "default_ignorable_removal",
        "nonspacing_mark_removal",
    )
    assert gate_promotes_stress_only_sanitizers() is True


def test_stress_only_sanitizers_corrupt_ordinary_text():
    damage = sanitizer_deployability_damage()
    assert damage["mn_strip"]["contract_category"] == "stress_only_not_frozen"
    assert damage["default_ignorable_strip"]["contract_category"] == "stress_only_not_frozen"
    assert damage["mn_strip"]["corrupted"] > damage["nfkc"]["corrupted"]
    assert "thai" in damage["mn_strip"]["corrupted_sample_ids"]
    assert "hebrew_niqqud" in damage["mn_strip"]["corrupted_sample_ids"]
    assert "emoji_zwj_family" in damage["default_ignorable_strip"]["corrupted_sample_ids"]


@pytest.mark.parametrize("sample_id,text", DEPLOYABILITY_CORPUS)
def test_deployability_corpus_is_ordinary_not_adversarial(sample_id, text):
    assert text == unicodedata.normalize("NFC", text) or sample_id == "hebrew_niqqud"
    assert text.strip() == text


def test_mn_strip_destroys_thai_and_hebrew():
    thai = "\u0e09\u0e31\u0e19\u0e44\u0e21\u0e48\u0e40\u0e2b\u0e47\u0e19"
    hebrew = "\u05d0\u05b2\u05e0\u05b4\u05d9"
    assert strip_nonspacing_marks(thai) != thai
    assert strip_nonspacing_marks(hebrew) != hebrew


def test_default_ignorable_strip_destroys_emoji_zwj_sequences():
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    assert strip_default_ignorable(family) != family


def test_production_tokenizers_do_not_strip_carriers():
    by_model = {row["model"]: row for row in TOKENIZER_OBSERVATIONS}
    for model in ("gemma-2-2b-it", "gemma-3-1b-it"):
        row = by_model[model]
        assert row["carriers_reaching_token_stream"] == row["carriers_probed"]
    assert all(row["carriers_reaching_token_stream"] >= 8 for row in TOKENIZER_OBSERVATIONS)


def test_audit_records_all_four_questions():
    disk = load_threat_model_audit()
    ids = [row["id"] for row in disk["findings"]]
    assert ids == [
        "q1_real_pipeline_normalization",
        "q2_are_stress_sanitizers_realistic",
        "q3_is_the_gate_correctly_defined",
        "q4_were_h9_h15_trapped",
    ]
    for row in disk["findings"]:
        assert row["answer"]
        assert row["evidence"]


def test_frozen_gate_conditions_are_met_by_existing_evidence():
    status = proposed_gate_status_on_existing_evidence()
    assert status["source"] == "already-run frozen confirmation evidence, no new corpus"
    assert status["identity_watermarked_detected"] == 185
    assert status["transformed_watermarked_rate"] == "0/192"
    assert status["visible_pass_rate"] == "192/192"
    assert all(value == 0 for value in status["detected_after_each_deployable_sanitizer"].values())
    assert status["frozen_sanitizer_conditions_satisfied"] is True


def test_proposed_gate_is_not_claimed_fully_satisfied():
    status = proposed_gate_status_on_existing_evidence()
    assert status["proposed_gate_v2_fully_satisfied"] is False
    assert status["all_conditions_measured"] is True
    assert status["confirmation_grade"] is False
    assert "why_not_fully_satisfied" in status


def test_mix_still_evades_the_real_sanitizer():
    detector = real_sanitizer_detector_observations()
    assert detector["watermarked_rows"] == 48
    assert detector["pristine_watermarked_detected"] == 47
    assert detector["real_sanitizer_watermarked_detected"] == 0


def test_the_real_sanitizer_does_not_suppress_detection_by_itself():
    detector = real_sanitizer_detector_observations()
    assert detector["real_sanitizer_carrier_free_detected"] == 46
    assert detector["real_sanitizer_watermarked_detected"] == 0
    assert "confound_ruled_out" in detector
    for row in detector["per_variant"]:
        assert row["carrier_free_detected"] >= 46


def test_required_bundle_defeats_mix_only_by_restoring_the_source():
    detector = real_sanitizer_detector_observations()
    assert detector["required_bundle_watermarked_detected"] == 47
    assert detector["required_bundle_restores_source_rows"] == 96
    by_variant = {row["variant"]: row for row in detector["per_variant"]}
    for variant in ("raw", "nfkc", "cf_strip", "lm_watermarking_unicode_sanitizer"):
        assert by_variant[variant]["watermarked_detected"] == 0
        assert by_variant[variant]["restores_source"] == 0


def test_detector_measurement_is_exploratory_and_uses_no_spent_seed():
    detector = real_sanitizer_detector_observations()
    assert detector["role"] == "exploratory_only_not_confirmation"
    assert detector["confirmation_grade"] is False
    assert detector["seed_base"] == 890000
    assert detector["seed_base"] not in (830000, 840000, 850000, 950000)


def test_real_sanitizer_does_not_restore_the_unwatermarked_source():
    observations = real_world_sanitizer_observations()
    assert observations["shipped_on_by_default"] is True
    assert observations["restores_the_unwatermarked_source"] is False
    assert observations["output_differs_from_source"] is True
    assert observations["injects_spurious_visible_spaces"] is True
    assert observations["detection_after_this_sanitizer"]["real_sanitizer_watermarked_detected"] == 0


def test_real_sanitizer_keeps_cgj_and_most_invisible_codepoints():
    observations = real_world_sanitizer_observations()
    assert observations["mix_carriers"] == ["U+034F", "U+FE00"]
    assert observations["mix_carriers_surviving"] == ["U+034F"]
    assert observations["invisible_codepoints_surviving"] == 366
    assert observations["invisible_codepoints_total"] == 396


def test_real_sanitizer_also_corrupts_ordinary_text():
    observations = real_world_sanitizer_observations()
    assert observations["ordinary_text_corrupted"] == 5
    assert "persian_zwnj" in observations["ordinary_text_corrupted_sample_ids"]
    assert "emoji_zwj_family" in observations["ordinary_text_corrupted_sample_ids"]
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    assert lm_watermarking_unicode_sanitizer(family) != family


def test_real_sanitizer_is_required_by_the_proposal():
    proposal = load_threat_model_audit()["proposed_gate_v2"]
    assert "lm_watermarking_unicode_sanitizer" in proposal["required_sanitizers"]
    assert proposal["added_since_first_draft"] == ["lm_watermarking_unicode_sanitizer"]


def test_gate_findings_do_not_authorize_the_product():
    disk = load_threat_model_audit()
    assert disk["proposed_gate_status_on_existing_evidence"]["frozen_sanitizer_conditions_satisfied"] is True
    assert disk["product_authorized"] is False
    assert disk["mix_sanitizer_gate"] == "FAIL"
    assert disk["proposed_gate_v2"]["status"] == "proposal_only_not_active"
    assert product_approved_carriers_v1() == frozenset()
    assert release_transform_registry().rules == ()


def test_proposed_gate_excludes_only_the_stress_only_sanitizers():
    proposal = load_threat_model_audit()["proposed_gate_v2"]
    assert proposal["excluded_sanitizers"] == [
        "default_ignorable_removal",
        "nonspacing_mark_removal",
    ]
    assert "nfkc_cf_strip" in proposal["required_sanitizers"]
    assert "cf_strip" in proposal["required_sanitizers"]
    assert "exact_user_visible_text_preservation" in proposal["still_requires"]
    assert "fresh_unspent_confirmation_corpus" in proposal["still_requires"]
