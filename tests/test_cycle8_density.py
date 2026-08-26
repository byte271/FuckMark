import pytest

from fuckmark.cycle8.compare import (
    CYCLE8_DENSITY_ARM_IDS,
    CYCLE8_IDENTITY_ARM_ID,
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
    arm_registry,
    measure_carrier_arm,
)
from fuckmark.cycle8.decision import PROMISING_DEVELOPMENT, classify_scale_detector_compare
from fuckmark.cycle8.ledger import CYCLE8_SCALE_PAIR_COUNT
from fuckmark.cycle8_density_hf import CYCLE8_DENSITY_DETECTOR_VERSION
from fuckmark.cycle8_hf import _topic_for_seed
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from fuckmark.seeds.ledger import (
    CYCLE8_DENSITY_EXPLORATORY_SEED_BASE,
    CYCLE8_DENSITY_EXPLORATORY_TOPIC,
    CYCLE8_SCALE_VALIDATION_SEED_BASE,
    assert_new_cycle8_density_generation_seed,
)
from fuckmark.transforms.registry import release_transform_registry


def test_density_seed_and_arms_are_reserved_before_generation() -> None:
    assert CYCLE8_SCALE_PAIR_COUNT == 16
    assert CYCLE8_DENSITY_EXPLORATORY_SEED_BASE == 960000
    assert _topic_for_seed(CYCLE8_DENSITY_EXPLORATORY_SEED_BASE) == CYCLE8_DENSITY_EXPLORATORY_TOPIC
    assert CYCLE8_DENSITY_ARM_IDS == (
        CYCLE8_IDENTITY_ARM_ID,
        CYCLE8_U034F_SPACE_ARM_ID,
        CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
    )
    assert CYCLE8_DENSITY_DETECTOR_VERSION == "cycle8-density-detector-compare-v1"
    assert_new_cycle8_density_generation_seed(CYCLE8_DENSITY_EXPLORATORY_SEED_BASE)
    with pytest.raises(ValueError, match="frozen"):
        assert_new_cycle8_density_generation_seed(CYCLE8_SCALE_VALIDATION_SEED_BASE)
    with pytest.raises(ValueError, match="confirmation"):
        assert_new_cycle8_density_generation_seed(830000)
    assert release_transform_registry().rules == ()


def test_density_wordfinal_arm_inserts_after_spaces_and_word_final_letters() -> None:
    source = "Apply the check after the notes."
    space = measure_carrier_arm(
        arm_id=CYCLE8_U034F_SPACE_ARM_ID,
        source_sample_id="density-space-control",
        source_text=source,
    )
    combined = measure_carrier_arm(
        arm_id=CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
        source_sample_id="density-wordfinal",
        source_text=source,
    )
    assert space["visible_ok"] is True
    assert combined["visible_ok"] is True
    assert int(combined["inserted_count"]) > int(space["inserted_count"])
    transformed = str(combined["transformed_text"])
    assert is_carrier_insertion_v1(source, transformed, (0x034F,))
    assert project_visible_v1(transformed, (0x034F,)) == source
    assert combined["fail_closed_identity"] is False
    registry = arm_registry(CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID)
    assert len(registry.rules) == 2


def test_classify_density_detector_compare_uses_wordfinal_arm() -> None:
    artifact = {
        "summaries": {
            CYCLE8_IDENTITY_ARM_ID: {
                "raw_watermarked_detected": 16,
                "raw_unwatermarked_detected": 0,
                "visible_pass_count": 32,
                "visible_total_count": 32,
            },
            CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID: {
                "raw_watermarked_detected": 0,
                "raw_unwatermarked_detected": 0,
                "cf_strip_watermarked_detected": 0,
                "nfkc_watermarked_detected": 0,
                "ws_collapse_watermarked_detected": 0,
                "nfkc_cf_strip_watermarked_detected": 0,
                "ws_collapse_nfkc_cf_strip_watermarked_detected": 0,
                "visible_pass_count": 32,
                "visible_total_count": 32,
            },
        }
    }
    decision = classify_scale_detector_compare(
        artifact,
        transformed_arm_id=CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID,
    )
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["transformed_arm_id"] == CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID
    assert decision["u034f_raw_watermarked_detected"] == 0
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
    assert any("space-wordfinal" in reason for reason in decision["reasons"])


def test_cycle8_density_960000_n16_records_one_raw_residual_on_both_arms() -> None:
    import json
    from pathlib import Path

    from fuckmark.hashing import sha256_json

    artifact = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "evidence"
            / "cycle8-density-960000-2026-08-26"
            / "detector-compare.json"
        ).read_text(encoding="utf-8")
    )
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(body) == "194aee2782663b0741d21cc6777a5c2426e28ef4929aba645e3e0ce812b30372"
    assert artifact["seed_base"] == 960000
    assert artifact["pair_count"] == 16
    assert artifact["topic"] == CYCLE8_DENSITY_EXPLORATORY_TOPIC
    assert artifact["algorithm_version"] == CYCLE8_DENSITY_DETECTOR_VERSION
    assert artifact["detector_access_used_for_selection"] is False
    identity = artifact["summaries"][CYCLE8_IDENTITY_ARM_ID]
    space = artifact["summaries"][CYCLE8_U034F_SPACE_ARM_ID]
    wordfinal = artifact["summaries"][CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID]
    assert identity["raw_watermarked_detected"] == 16
    assert space["raw_watermarked_detected"] == 1
    assert wordfinal["raw_watermarked_detected"] == 1
    assert space["raw_unwatermarked_detected"] == 0
    assert wordfinal["raw_unwatermarked_detected"] == 0
    assert space["cf_strip_watermarked_detected"] == 1
    assert wordfinal["cf_strip_watermarked_detected"] == 1
    assert space["visible_pass_count"] == 32
    assert wordfinal["visible_pass_count"] == 32
    assert space["fail_closed_identity_count"] == 0
    assert wordfinal["fail_closed_identity_count"] == 0
    assert float(wordfinal["inserted_count_mean"]) > float(space["inserted_count_mean"])
    residual_ids = {
        row["sample_id"]
        for row in artifact["scored_rows"]
        if row["label"] == "watermarked"
        and row["arm_id"] in {CYCLE8_U034F_SPACE_ARM_ID, CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID}
        and row["sanitizers"]["raw"]["detected"]
    }
    assert residual_ids == {"cycle8-960000-12-general_explanatory-watermarked"}
    decision = json.loads(
        (
            Path(__file__).resolve().parents[1] / "evidence" / "cycle8-density-960000-2026-08-26" / "decision.json"
        ).read_text(encoding="utf-8")
    )
    assert decision["decision"] == PROMISING_DEVELOPMENT
    assert decision["transformed_arm_id"] == CYCLE8_U034F_SPACE_WORDFINAL_ARM_ID
    assert decision["u034f_raw_watermarked_detected"] == 1
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
    space_decision = classify_scale_detector_compare(artifact, transformed_arm_id=CYCLE8_U034F_SPACE_ARM_ID)
    assert space_decision["u034f_raw_watermarked_detected"] == 1
    assert space_decision["decision"] == PROMISING_DEVELOPMENT
