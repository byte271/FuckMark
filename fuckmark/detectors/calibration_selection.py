from __future__ import annotations

import bisect
import math
from collections.abc import Sequence

from .calibration_statistics import _validate_probability
from .calibration_types import (
    CalibrationIdentityError,
    CalibrationResolutionError,
    CalibrationThreshold,
    ComparisonOperator,
    DetectorCalibrationIdentity,
    ExactBinomialInterval,
)
from .types import ScoreDirection, UncalibratedDetectorEvidence


def _normalize_target_fprs(target_fprs: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(target_fprs, Sequence) or isinstance(target_fprs, (str, bytes, bytearray)):
        raise TypeError("target_fprs must be a sequence of probabilities")
    values = tuple(_validate_probability("target_fpr", value) for value in tuple(target_fprs))
    if not values:
        raise ValueError("target_fprs must not be empty")
    if len(set(values)) != len(values):
        raise ValueError("target_fprs must be unique")
    return tuple(sorted(values, reverse=True))


def _normalize_negative_evidence(
    negative_evidence: Sequence[UncalibratedDetectorEvidence],
) -> tuple[tuple[UncalibratedDetectorEvidence, ...], DetectorCalibrationIdentity]:
    if not isinstance(negative_evidence, Sequence) or isinstance(negative_evidence, (str, bytes, bytearray)):
        raise TypeError("negative_evidence must be a sequence")
    evidence = tuple(negative_evidence)
    if not evidence:
        raise ValueError("negative_evidence must not be empty")
    for value in evidence:
        if not isinstance(value, UncalibratedDetectorEvidence):
            raise TypeError("negative_evidence must contain UncalibratedDetectorEvidence values")
    ordered = tuple(sorted(evidence, key=lambda value: (value.sample_id, value.observation_batch_hash)))
    sample_ids = tuple(value.sample_id for value in ordered)
    observation_hashes = tuple(value.observation_batch_hash for value in ordered)
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("negative calibration sample IDs must be unique")
    if len(set(observation_hashes)) != len(observation_hashes):
        raise ValueError("negative calibration observation batches must be unique")
    identity = DetectorCalibrationIdentity.from_evidence(ordered[0])
    for value in ordered[1:]:
        if DetectorCalibrationIdentity.from_evidence(value) != identity:
            raise CalibrationIdentityError("negative calibration evidence mixes detector identities")
    if identity.direction is not ScoreDirection.HIGHER_IS_MORE_WATERMARKED:
        raise CalibrationIdentityError("unsupported detector score direction")
    return ordered, identity



def _false_positive_count(
    sorted_scores: tuple[float, ...],
    threshold: float,
    operator: ComparisonOperator,
) -> int:
    if operator is ComparisonOperator.GREATER_THAN:
        return len(sorted_scores) - bisect.bisect_right(sorted_scores, threshold)
    return len(sorted_scores) - bisect.bisect_left(sorted_scores, threshold)


def _select_threshold(
    sorted_scores: tuple[float, ...],
    target_fpr: float,
    operator: ComparisonOperator,
) -> tuple[float, int]:
    for candidate in sorted(set(sorted_scores)):
        false_positives = _false_positive_count(sorted_scores, candidate, operator)
        if false_positives / len(sorted_scores) <= target_fpr:
            return candidate, false_positives
    raise CalibrationResolutionError(
        "no observed score threshold satisfies the target FPR under the selected comparison operator"
    )


def _check_tail_resolution(sample_count: int, target_fpr: float) -> None:
    minimum = math.ceil(1.0 / target_fpr)
    if sample_count < minimum:
        raise CalibrationResolutionError(
            f"target FPR {target_fpr:g} requires at least {minimum} negative samples for one empirical tail count"
        )
    if target_fpr <= 0.001 and sample_count < 10_000:
        raise CalibrationResolutionError("0.1% FPR calibration requires at least 10000 negative samples")


def _threshold_hash_payload(
    target_fpr: float,
    operator: ComparisonOperator,
    value: float,
    false_positive_count: int,
    calibration_count: int,
    achieved_fpr: float,
    interval: ExactBinomialInterval,
    calibration_input_hash: str,
) -> dict[str, object]:
    return {
        "target_fpr": target_fpr,
        "comparison_operator": operator.value,
        "value": value,
        "false_positive_count": false_positive_count,
        "calibration_count": calibration_count,
        "achieved_fpr": achieved_fpr,
        "fpr_interval": interval,
        "calibration_input_hash": calibration_input_hash,
    }


