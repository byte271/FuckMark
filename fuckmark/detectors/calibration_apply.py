from __future__ import annotations

from ..hashing import sha256_json
from .calibration_statistics import _validate_probability
from .calibration_types import CalibratedDetectorResult, CalibrationBundle, CalibrationIdentityError, CalibrationThreshold, ComparisonOperator, DetectorCalibrationIdentity
from .types import ScoreDirection, UncalibratedDetectorEvidence


def _find_threshold(bundle: CalibrationBundle, target_fpr: float) -> CalibrationThreshold:
    target = _validate_probability("target_fpr", target_fpr)
    for threshold in bundle.thresholds:
        if threshold.target_fpr == target:
            return threshold
    raise KeyError(f"target FPR {target:g} is not present in calibration bundle")

def apply_calibration(
    evidence: UncalibratedDetectorEvidence,
    bundle: CalibrationBundle,
    target_fpr: float,
) -> CalibratedDetectorResult:
    if not isinstance(evidence, UncalibratedDetectorEvidence):
        raise TypeError("evidence must be UncalibratedDetectorEvidence")
    if not isinstance(bundle, CalibrationBundle):
        raise TypeError("bundle must be a CalibrationBundle")
    identity = DetectorCalibrationIdentity.from_evidence(evidence)
    if identity != bundle.detector_identity:
        raise CalibrationIdentityError("evidence detector identity does not match calibration bundle")
    threshold = _find_threshold(bundle, target_fpr)
    if evidence.direction is not ScoreDirection.HIGHER_IS_MORE_WATERMARKED:
        raise CalibrationIdentityError("unsupported detector score direction")
    decision = (
        evidence.raw_score > threshold.value
        if threshold.comparison_operator is ComparisonOperator.GREATER_THAN
        else evidence.raw_score >= threshold.value
    )
    margin = (evidence.raw_score - threshold.value) / bundle.robust_scale
    evidence_hash = sha256_json(evidence)
    payload = {
        "sample_id": evidence.sample_id,
        "evidence_hash": evidence_hash,
        "observation_batch_hash": evidence.observation_batch_hash,
        "detector_identity_hash": identity.identity_hash,
        "calibration_bundle_hash": bundle.bundle_hash,
        "threshold_hash": threshold.threshold_hash,
        "target_fpr": threshold.target_fpr,
        "achieved_calibration_fpr": threshold.achieved_fpr,
        "calibration_fpr_interval": threshold.fpr_interval,
        "comparison_operator": threshold.comparison_operator.value,
        "threshold_value": threshold.value,
        "raw_score": evidence.raw_score,
        "direction": evidence.direction.value,
        "robust_scale": bundle.robust_scale,
        "standardized_margin": margin,
        "valid_observation_count": evidence.valid_observation_count,
        "decision": decision,
    }
    return CalibratedDetectorResult(
        sample_id=evidence.sample_id,
        evidence_hash=evidence_hash,
        observation_batch_hash=evidence.observation_batch_hash,
        detector_identity_hash=identity.identity_hash,
        calibration_bundle_hash=bundle.bundle_hash,
        threshold_hash=threshold.threshold_hash,
        target_fpr=threshold.target_fpr,
        achieved_calibration_fpr=threshold.achieved_fpr,
        calibration_fpr_interval=threshold.fpr_interval,
        comparison_operator=threshold.comparison_operator,
        threshold_value=threshold.value,
        raw_score=evidence.raw_score,
        direction=evidence.direction,
        robust_scale=bundle.robust_scale,
        standardized_margin=margin,
        valid_observation_count=evidence.valid_observation_count,
        decision=decision,
        result_hash=sha256_json(payload),
    )
