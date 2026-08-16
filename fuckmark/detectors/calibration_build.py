from __future__ import annotations

from collections.abc import Sequence

from ..hashing import sha256_json
from .calibration_selection import _check_tail_resolution, _normalize_negative_evidence, _normalize_target_fprs, _select_threshold, _threshold_hash_payload
from .calibration_statistics import BINOMIAL_INTERVAL_METHOD, NULL_QUANTILE_METHOD, ROBUST_SCALE_METHOD, _empirical_quantile, _robust_location_scale, _validate_probability, exact_binomial_interval
from .calibration_types import CalibrationBundle, CalibrationScope, CalibrationThreshold, ComparisonOperator, NullQuantile
from .types import UncalibratedDetectorEvidence


CALIBRATION_ALGORITHM_VERSION = "empirical-fixed-fpr-v1"


def calibrate_detector(
    negative_evidence: Sequence[UncalibratedDetectorEvidence],
    scope: CalibrationScope,
    target_fprs: Sequence[float] = (0.05, 0.01),
    comparison_operator: ComparisonOperator = ComparisonOperator.GREATER_THAN_OR_EQUAL,
    confidence_level: float = 0.95,
) -> CalibrationBundle:
    if not isinstance(scope, CalibrationScope):
        raise TypeError("scope must be a CalibrationScope")
    if not isinstance(comparison_operator, ComparisonOperator):
        raise TypeError("comparison_operator must be a ComparisonOperator")
    level = _validate_probability("confidence_level", confidence_level)
    targets = _normalize_target_fprs(target_fprs)
    ordered, identity = _normalize_negative_evidence(negative_evidence)
    count = len(ordered)
    for target in targets:
        _check_tail_resolution(count, target)
    sorted_scores = tuple(sorted(value.raw_score for value in ordered))
    center, scale = _robust_location_scale(sorted_scores)
    quantile_probabilities = tuple(sorted({0.5, *(1.0 - target for target in targets)}))
    quantiles = tuple(
        NullQuantile(probability, _empirical_quantile(sorted_scores, probability))
        for probability in quantile_probabilities
    )
    negative_manifest_hash = sha256_json(ordered)
    input_payload = {
        "calibration_algorithm_version": CALIBRATION_ALGORITHM_VERSION,
        "scope": scope,
        "detector_identity": identity,
        "negative_manifest_hash": negative_manifest_hash,
        "negative_count": count,
        "robust_center": center,
        "robust_scale": scale,
        "robust_scale_method": ROBUST_SCALE_METHOD,
        "null_quantiles": quantiles,
        "quantile_method": NULL_QUANTILE_METHOD,
        "comparison_operator": comparison_operator.value,
        "binomial_interval_method": BINOMIAL_INTERVAL_METHOD,
        "confidence_level": level,
    }
    calibration_input_hash = sha256_json(input_payload)
    thresholds: list[CalibrationThreshold] = []
    for target in targets:
        threshold_value, false_positives = _select_threshold(sorted_scores, target, comparison_operator)
        achieved_fpr = false_positives / count
        interval = exact_binomial_interval(false_positives, count, level)
        threshold_payload = _threshold_hash_payload(
            target,
            comparison_operator,
            threshold_value,
            false_positives,
            count,
            achieved_fpr,
            interval,
            calibration_input_hash,
        )
        thresholds.append(
            CalibrationThreshold(
                target_fpr=target,
                comparison_operator=comparison_operator,
                value=threshold_value,
                false_positive_count=false_positives,
                calibration_count=count,
                achieved_fpr=achieved_fpr,
                fpr_interval=interval,
                calibration_input_hash=calibration_input_hash,
                threshold_hash=sha256_json(threshold_payload),
            )
        )
    threshold_tuple = tuple(thresholds)
    bundle_hash = sha256_json(
        {
            "calibration_input_hash": calibration_input_hash,
            "thresholds": threshold_tuple,
        }
    )
    return CalibrationBundle(
        calibration_algorithm_version=CALIBRATION_ALGORITHM_VERSION,
        scope=scope,
        detector_identity=identity,
        negative_manifest_hash=negative_manifest_hash,
        negative_count=count,
        robust_center=center,
        robust_scale=scale,
        robust_scale_method=ROBUST_SCALE_METHOD,
        null_quantiles=quantiles,
        quantile_method=NULL_QUANTILE_METHOD,
        comparison_operator=comparison_operator,
        binomial_interval_method=BINOMIAL_INTERVAL_METHOD,
        confidence_level=level,
        thresholds=threshold_tuple,
        calibration_input_hash=calibration_input_hash,
        bundle_hash=bundle_hash,
    )
