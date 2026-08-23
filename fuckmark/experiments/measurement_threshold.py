from __future__ import annotations

import math

from ..detectors import CalibrationScope, ComparisonOperator, calibrate_detector
from ..detectors.calibration_statistics import exact_binomial_interval
from ..hashing import sha256_json
from ..tiny_dev_transform_hf import (
    TEXT_ONLY_CALIBRATION_POPULATION_ID,
    TEXT_ONLY_LENGTH_POLICY_ID,
    TEXT_ONLY_PROMPT_BOUNDARY_MODE,
    TEXT_ONLY_TOKEN_TRACK,
    _text_only_weighted_evidence,
)


MEASUREMENT_STABILITY_VERSION = "open-detector-measurement-stability-v1"
MEASUREMENT_STABILITY_TARGET_FPR = 0.01
MEASUREMENT_STABILITY_COMPARISON = ">="


def build_fixed_threshold_artifact(
    calibration_corpus,
    adapter,
    *,
    frozen_at_utc: str,
) -> dict[str, object]:
    negatives = calibration_corpus.calibration_samples()
    audit = calibration_corpus.audit_samples()
    evidence = tuple(_text_only_weighted_evidence(sample, adapter) for sample in negatives)
    audit_evidence = tuple(_text_only_weighted_evidence(sample, adapter) for sample in audit)
    scope = CalibrationScope.create(
        corpus_id=calibration_corpus.manifest.corpus_id,
        population_id=TEXT_ONLY_CALIBRATION_POPULATION_ID,
        length_policy_id=TEXT_ONLY_LENGTH_POLICY_ID,
        token_track=TEXT_ONLY_TOKEN_TRACK,
        prompt_boundary_mode=TEXT_ONLY_PROMPT_BOUNDARY_MODE,
    )
    bundle = calibrate_detector(
        evidence,
        scope,
        target_fprs=(0.05, 0.01),
        comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        confidence_level=0.95,
    )
    scores = sorted(value.raw_score for value in evidence)
    count = len(scores)
    order_statistic = count - math.floor(MEASUREMENT_STABILITY_TARGET_FPR * count) + 1
    threshold = scores[order_statistic - 1]
    calibration_exceedances = sum(1 for value in scores if value >= threshold)
    audit_scores = tuple(value.raw_score for value in audit_evidence)
    audit_exceedances = sum(1 for value in audit_scores if value >= threshold)
    interval = exact_binomial_interval(audit_exceedances, len(audit_scores))
    payload = {
        "algorithm_version": MEASUREMENT_STABILITY_VERSION,
        "frozen_at_utc": frozen_at_utc,
        "detector_identity_hash": bundle.detector_identity.identity_hash,
        "calibration_bundle_hash": bundle.bundle_hash,
        "calibration_corpus_artifact_hash": calibration_corpus.artifact_hash,
        "calibration_negative_count": count,
        "audit_negative_count": len(audit_scores),
        "target_fpr": MEASUREMENT_STABILITY_TARGET_FPR,
        "comparison_operator": MEASUREMENT_STABILITY_COMPARISON,
        "threshold_definition": (
            "ascending order statistic n - floor(target_fpr * n) + 1 of the calibration "
            "negative weighted-mean scores (the 1015th of 1024 for target FPR 0.01, bounding "
            "calibration exceedances at floor(target_fpr * n)); detection when score >= "
            "threshold; float64 scores as computed; no tie rounding"
        ),
        "threshold_order_statistic": order_statistic,
        "threshold": threshold,
        "calibration_exceedances": calibration_exceedances,
        "audit_exceedances": audit_exceedances,
        "audit_realized_fpr": audit_exceedances / len(audit_scores),
        "audit_fpr_confidence_interval_95": [interval.lower, interval.upper],
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def validate_fixed_threshold_artifact(artifact, detector_identity_hash: str) -> float:
    if not isinstance(artifact, dict):
        raise TypeError("fixed threshold artifact must be a mapping")
    if artifact.get("algorithm_version") != MEASUREMENT_STABILITY_VERSION:
        raise ValueError("unsupported fixed threshold artifact version")
    if artifact.get("detector_identity_hash") != detector_identity_hash:
        raise ValueError("fixed threshold detector identity does not match the scoring detector")
    if artifact.get("comparison_operator") != MEASUREMENT_STABILITY_COMPARISON:
        raise ValueError("fixed threshold comparison operator does not match the scoring rule")
    if artifact.get("target_fpr") != MEASUREMENT_STABILITY_TARGET_FPR:
        raise ValueError("fixed threshold target FPR does not match the scoring target")
    expected = sha256_json({key: value for key, value in artifact.items() if key != "artifact_hash"})
    if artifact.get("artifact_hash") != expected:
        raise ValueError("fixed threshold artifact hash does not replay")
    threshold = artifact.get("threshold")
    if not isinstance(threshold, float) or not 0.0 <= threshold <= 1.0:
        raise ValueError("fixed threshold must be a probability float")
    return threshold
