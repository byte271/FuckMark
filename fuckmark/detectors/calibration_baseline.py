from __future__ import annotations

import math
from collections.abc import Sequence

from ..hashing import sha256_json
from .calibration_statistics import _validate_probability, exact_binomial_interval
from .calibration_types import BaselineStatus, CalibratedDetectorResult, CalibrationIdentityError, PristineBaselineSummary


def evaluate_pristine_baseline(
    results: Sequence[CalibratedDetectorResult],
    interpretability_floor: float = 0.80,
    confidence_level: float = 0.95,
) -> PristineBaselineSummary:
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes, bytearray)):
        raise TypeError("results must be a sequence")
    values = tuple(results)
    if not values:
        raise ValueError("results must not be empty")
    for value in values:
        if not isinstance(value, CalibratedDetectorResult):
            raise TypeError("results must contain CalibratedDetectorResult values")
    if isinstance(interpretability_floor, bool) or not isinstance(interpretability_floor, (int, float)):
        raise TypeError("interpretability_floor must be a real number")
    floor = float(interpretability_floor)
    if not math.isfinite(floor) or floor <= 0.0 or floor > 1.0:
        raise ValueError("interpretability_floor must be in (0, 1]")
    level = _validate_probability("confidence_level", confidence_level)
    first = values[0]
    identity = (
        first.calibration_bundle_hash,
        first.threshold_hash,
        first.detector_identity_hash,
        first.target_fpr,
        first.comparison_operator,
        first.threshold_value,
    )
    evidence_hashes: list[str] = []
    for value in values:
        current = (
            value.calibration_bundle_hash,
            value.threshold_hash,
            value.detector_identity_hash,
            value.target_fpr,
            value.comparison_operator,
            value.threshold_value,
        )
        if current != identity:
            raise CalibrationIdentityError("pristine baseline results mix calibration thresholds or detector identities")
        evidence_hashes.append(value.evidence_hash)
    if len(set(evidence_hashes)) != len(evidence_hashes):
        raise ValueError("pristine baseline evidence must be unique")
    ordered = tuple(sorted(values, key=lambda value: (value.sample_id, value.evidence_hash)))
    sample_count = len(ordered)
    detected_count = sum(value.decision for value in ordered)
    tpr = detected_count / sample_count
    interval = exact_binomial_interval(detected_count, sample_count, level)
    status = BaselineStatus.PASS if tpr >= floor else BaselineStatus.BELOW_FLOOR
    manifest_hash = sha256_json(tuple(value.evidence_hash for value in ordered))
    payload = {
        "calibration_bundle_hash": first.calibration_bundle_hash,
        "threshold_hash": first.threshold_hash,
        "detector_identity_hash": first.detector_identity_hash,
        "evidence_manifest_hash": manifest_hash,
        "sample_count": sample_count,
        "detected_count": detected_count,
        "tpr": tpr,
        "tpr_interval": interval,
        "interpretability_floor": floor,
        "status": status.value,
    }
    return PristineBaselineSummary(
        calibration_bundle_hash=first.calibration_bundle_hash,
        threshold_hash=first.threshold_hash,
        detector_identity_hash=first.detector_identity_hash,
        evidence_manifest_hash=manifest_hash,
        sample_count=sample_count,
        detected_count=detected_count,
        tpr=tpr,
        tpr_interval=interval,
        interpretability_floor=floor,
        status=status,
        summary_hash=sha256_json(payload),
    )
