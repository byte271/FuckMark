import json
import math
from pathlib import Path

from fuckmark.hashing import sha256_json
from fuckmark.transforms import KEY_BLIND_HIGH_COVERAGE_PROFILE


def _record() -> dict[str, object]:
    path = (
        Path(__file__).parents[1]
        / "specs"
        / "fuckmark-key-blind-high-coverage-v1.tinydev-evidence.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_key_blind_high_coverage_evidence_record_replays() -> None:
    record = _record()
    payload = {key: value for key, value in record.items() if key != "record_hash"}
    assert record["record_hash"] == sha256_json(payload)
    assert record["decision"] == "ACCEPTED_DEVELOPMENT_EVIDENCE_ONLY"
    assert record["implementation_retained"] is True
    assert record["release_authorized"] is False
    assert record["profile"]["profile_hash"] == KEY_BLIND_HIGH_COVERAGE_PROFILE.profile_hash
    assert record["profile"]["ruleset_hash"] == KEY_BLIND_HIGH_COVERAGE_PROFILE.ruleset_hash


def test_key_blind_high_coverage_evidence_preserves_denominators_and_controls() -> None:
    record = _record()
    corpus = record["corpus"]
    measurement = record["measurement"]
    assert corpus["independent_watermarked_source_count"] == 4
    assert corpus["independent_control_source_count"] == 4
    assert measurement["pristine_watermarked_detected_count"] == 4
    assert measurement["transformed_watermarked_detected_count"] == 0
    assert measurement["pristine_control_detected_count"] == 0
    assert measurement["transformed_control_detected_count"] == 0
    assert len(record["watermarked_rows"]) == 4
    assert all(row["transformed_detected"] is False for row in record["watermarked_rows"])


def test_key_blind_high_coverage_evidence_summary_matches_rows() -> None:
    record = _record()
    measurement = record["measurement"]
    rows = record["watermarked_rows"]
    count = len(rows)
    pristine_mean = math.fsum(row["pristine_score"] for row in rows) / count
    transformed_mean = math.fsum(row["transformed_score"] for row in rows) / count
    mean_drop = math.fsum(row["score_drop"] for row in rows) / count
    assert math.isclose(measurement["mean_pristine_watermarked_score"], pristine_mean)
    assert math.isclose(measurement["mean_transformed_watermarked_score"], transformed_mean)
    assert math.isclose(measurement["mean_watermarked_score_drop"], mean_drop)
    assert math.isclose(pristine_mean - transformed_mean, mean_drop)
    assert math.isclose(
        measurement["threshold"] - measurement["maximum_transformed_control_score"],
        measurement["minimum_transformed_control_threshold_margin"],
    )


def test_key_blind_high_coverage_evidence_keeps_narrow_claim_boundary() -> None:
    boundary = _record()["claim_boundary"]
    for name in (
        "watermark_removal_claim",
        "undetectability_claim",
        "unknown_key_claim",
        "proprietary_detector_claim",
        "normalization_durability_claim",
        "confirmatory_replication_claim",
    ):
        assert boundary[name] is False
    assert boundary["blind_human_semantic_audit"] == "NOT_PERFORMED"
    assert boundary["blind_human_style_audit"] == "NOT_PERFORMED"
