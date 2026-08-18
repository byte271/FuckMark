import json
from pathlib import Path

from fuckmark.hashing import sha256_json


_EVIDENCE_PATH = Path("evidence/tiny_dev/real-hf-gpt2-transform-evidence-2026-08-18.json")


def _evidence() -> dict[str, object]:
    return json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_real_transform_evidence_is_self_hashed_and_scoped() -> None:
    evidence = _evidence()
    evidence_hash = evidence.pop("evidence_hash")
    assert evidence_hash == sha256_json(evidence)
    assert evidence["algorithm_version"] == "real-tiny-dev-transform-evidence-manifest-v1"
    assert evidence["evidence_kind"] == "development-transform-detector-pilot"
    assert evidence["interpretation"]["status"] == "PROMISING_DEV_SIGNAL_NOT_M6"
    assert evidence["interpretation"]["m6_readiness_claim_permitted"] is False
    assert evidence["interpretation"]["confirmatory_claim_permitted"] is False


def test_real_transform_evidence_binds_successful_source_run() -> None:
    source = _evidence()["source"]
    assert source["source_head_commit"] == "c77e8bb2e720be106e4b525377f07849f4ad933e"
    assert source["workflow_run_id"] == 32096402704
    assert source["workflow_conclusion"] == "success"
    assert source["artifact_id"] == 9310202139
    assert source["artifact_zip_sha256"] == "e572ea9cb7148368c17bec73f4b1dd749ad3dbee7e96fd32f85b2390a7fbc4a4"
    assert source["corpus_json_sha256"] == "ee09527d06abc58e612f7157b69908d5abe06101865714ce13a1287d1f0d7664"
    assert source["plan_json_sha256"] == "9c74356f46e286bdb50c49236580d1168a9dacd690f0215e8254a91ec4c8936e"
    assert source["transform_evidence_json_sha256"] == "509a5c69ffd79e821d10bd54df29588164bc0d208cfcb68acf8862ce09fdbbbc"


def test_real_transform_evidence_records_detector_and_plan_firewall() -> None:
    evidence = _evidence()
    detector = evidence["detector"]
    plan = evidence["selection_plan"]
    assert detector["family"] == "weighted_mean"
    assert detector["calibration_negative_count"] == 100
    assert detector["primary_target_fpr"] == 0.01
    assert detector["achieved_calibration_fpr"] == 0.01
    assert plan["geometry_mode"] == "TOKENIZER_AWARE_PUBLIC"
    assert plan["budgets"] == [1, 2, 4]
    assert plan["random_seed_count"] == 8
    assert plan["watermarked_candidate_counts"] == [6, 6, 11, 9]
    assert plan["selection_frozen_before_detector_scoring"] is True


def test_real_transform_evidence_preserves_positive_and_negative_results() -> None:
    result = _evidence()["result"]
    interpretation = _evidence()["interpretation"]
    assert result["pristine_positive_detected_count"] == 4
    assert result["pristine_positive_count"] == 4
    assert result["pristine_negative_detected_count"] == 0
    assert result["pristine_negative_count"] == 4
    assert result["watermarked_transform_row_count"] == 216
    assert result["watermarked_unique_transformed_text_count"] == 92
    assert result["control_eligible_count"] == 216
    assert result["control_false_to_true_count"] == 0
    assert result["e07"]["lower_error_metric"] == "OBSERVATION_REPLACEMENT"
    assert result["e08"]["monotonic_non_decreasing"] is True
    assert result["e08"]["monotonic_violation_count"] == 0
    assert result["e11"]["mean_improvement_greedy_minus_random_replacement_per_edit"] > 0.0
    assert result["e11"]["overall_mean_score_drop_greedy_minus_random"] < 0.0
    assert interpretation["greedy_improves_replacement_per_edit_over_random"] is True
    assert interpretation["greedy_improves_overall_detector_score_drop_over_random"] is False
