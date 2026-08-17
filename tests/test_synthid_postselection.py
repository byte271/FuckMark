from dataclasses import replace

import pytest

from fuckmark.experiments.synthid_geometry import (
    GeometryLabel,
    GeometryPair,
    GeometryPairStatus,
    GeometrySummary,
    SELECTION_ACCESS_ID,
    SYNTHID_GEOMETRY_ALGORITHM_VERSION,
    SynthIDGeometryReport,
)
from fuckmark.experiments.synthid_postselection import build_synthid_postselection_audit
from fuckmark.hashing import sha256_json, sha256_text


def _pair(index: int, label: GeometryLabel, disruption: float, score: float) -> GeometryPair:
    payload = {
        "prompt_id": f"p-{index}",
        "generation_seed": index,
        "label": label.value,
        "budget": 1,
        "greedy_variant_hash": sha256_text(f"greedy-{index}"),
        "matched_random_variant_hashes": (sha256_text(f"random-{index}"),),
        "disruption_advantage": disruption,
        "score_drop_advantage": score,
        "status": GeometryPairStatus.MATCHED.value,
    }
    return GeometryPair(
        f"p-{index}",
        index,
        label,
        1,
        payload["greedy_variant_hash"],
        payload["matched_random_variant_hashes"],
        disruption,
        score,
        GeometryPairStatus.MATCHED,
        sha256_json(payload),
    )


def _report() -> SynthIDGeometryReport:
    pairs = (
        _pair(1, GeometryLabel.CONTROL, 1.0, 0.01),
        _pair(2, GeometryLabel.CONTROL, 0.0, -0.01),
        _pair(3, GeometryLabel.WATERMARKED, 1.0, -0.03),
        _pair(4, GeometryLabel.WATERMARKED, 2.0, -0.02),
        _pair(5, GeometryLabel.WATERMARKED, 3.0, 0.01),
    )
    summary = GeometrySummary(
        5,
        10,
        0,
        (1,),
        1,
        1.0,
        1.0,
        len(pairs),
        0.5,
        2.0,
        0.0,
        -0.02,
    )
    payload = {
        "algorithm_version": SYNTHID_GEOMETRY_ALGORITHM_VERSION,
        "selection_access_id": SELECTION_ACCESS_ID,
        "backend_id": "fake-backend",
        "backend_version": "fake-v1",
        "model_id": "fake-model",
        "detector_id": "fake-detector",
        "detector_config_hash": sha256_text("detector"),
        "transform_ruleset_hash": sha256_text("rules"),
        "ngram_len": 5,
        "greedy_seed": 1,
        "random_seeds": (2,),
        "variants": (),
        "pairs": pairs,
        "summary": summary,
    }
    return SynthIDGeometryReport(
        SYNTHID_GEOMETRY_ALGORITHM_VERSION,
        SELECTION_ACCESS_ID,
        "fake-backend",
        "fake-v1",
        "fake-model",
        "fake-detector",
        sha256_text("detector"),
        sha256_text("rules"),
        5,
        1,
        (2,),
        (),
        pairs,
        summary,
        sha256_json(payload),
    )


def test_postselection_audit_reports_geometry_score_misalignment_without_feedback() -> None:
    audit = build_synthid_postselection_audit(_report())
    assert audit.selection_feedback_used is False
    control, watermarked = audit.summaries
    assert control.matched_pair_count == 2
    assert control.geometry_positive_pair_count == 1
    assert control.geometry_positive_score_positive_count == 1
    assert control.geometry_positive_score_nonpositive_count == 0
    assert watermarked.matched_pair_count == 3
    assert watermarked.geometry_positive_pair_count == 3
    assert watermarked.geometry_positive_score_positive_count == 1
    assert watermarked.geometry_positive_score_nonpositive_count == 2
    assert watermarked.mean_score_advantage_when_geometry_positive == pytest.approx(-0.013333333333333334)
    assert watermarked.pearson_geometry_vs_score is not None


def test_postselection_audit_is_content_addressed() -> None:
    audit = build_synthid_postselection_audit(_report())
    with pytest.raises(ValueError, match="audit_hash"):
        replace(audit, source_report_hash=sha256_text("other-report"))
    with pytest.raises(ValueError, match="descriptive"):
        replace(audit, selection_feedback_used=True)


def test_postselection_audit_requires_geometry_report() -> None:
    with pytest.raises(TypeError, match="SynthIDGeometryReport"):
        build_synthid_postselection_audit(object())
