from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .calibration_distribution import NullQuantile
from .calibration_identity import CalibrationScope, ComparisonOperator, DetectorCalibrationIdentity
from .calibration_threshold import CalibrationThreshold


@dataclass(frozen=True, slots=True)
class CalibrationBundle:
    calibration_algorithm_version: str
    scope: CalibrationScope
    detector_identity: DetectorCalibrationIdentity
    negative_manifest_hash: str
    negative_count: int
    robust_center: float
    robust_scale: float
    robust_scale_method: str
    null_quantiles: tuple[NullQuantile, ...]
    quantile_method: str
    comparison_operator: ComparisonOperator
    binomial_interval_method: str
    confidence_level: float
    thresholds: tuple[CalibrationThreshold, ...]
    calibration_input_hash: str
    bundle_hash: str

    def __post_init__(self) -> None:
        require_clean_string("calibration_algorithm_version", self.calibration_algorithm_version)
        if not isinstance(self.scope, CalibrationScope):
            raise TypeError("scope must be a CalibrationScope")
        if not isinstance(self.detector_identity, DetectorCalibrationIdentity):
            raise TypeError("detector_identity must be a DetectorCalibrationIdentity")
        require_sha256("negative_manifest_hash", self.negative_manifest_hash)
        require_int("negative_count", self.negative_count)
        if self.negative_count <= 0:
            raise ValueError("negative_count must be positive")
        for name, value in (
            ("robust_center", self.robust_center),
            ("robust_scale", self.robust_scale),
            ("confidence_level", self.confidence_level),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.robust_center < 0.0 or self.robust_center > 1.0:
            raise ValueError("robust_center must be between 0 and 1")
        if self.robust_scale <= 0.0:
            raise ValueError("robust_scale must be positive")
        require_clean_string("robust_scale_method", self.robust_scale_method)
        require_clean_string("quantile_method", self.quantile_method)
        if self.confidence_level <= 0.0 or self.confidence_level >= 1.0:
            raise ValueError("confidence_level must be between 0 and 1")
        if not isinstance(self.comparison_operator, ComparisonOperator):
            raise TypeError("comparison_operator must be a ComparisonOperator")
        require_clean_string("binomial_interval_method", self.binomial_interval_method)
        if not isinstance(self.null_quantiles, tuple) or not self.null_quantiles:
            raise TypeError("null_quantiles must be a non-empty tuple")
        probabilities: list[float] = []
        for quantile in self.null_quantiles:
            if not isinstance(quantile, NullQuantile):
                raise TypeError("null_quantiles must contain NullQuantile values")
            probabilities.append(quantile.probability)
        if probabilities != sorted(probabilities) or len(set(probabilities)) != len(probabilities):
            raise ValueError("null_quantiles must be unique and sorted by probability")
        if not isinstance(self.thresholds, tuple) or not self.thresholds:
            raise TypeError("thresholds must be a non-empty tuple")
        targets: list[float] = []
        for threshold in self.thresholds:
            if not isinstance(threshold, CalibrationThreshold):
                raise TypeError("thresholds must contain CalibrationThreshold values")
            if threshold.calibration_count != self.negative_count:
                raise ValueError("threshold calibration_count does not match bundle")
            if threshold.comparison_operator is not self.comparison_operator:
                raise ValueError("threshold comparison operator does not match bundle")
            if threshold.fpr_interval.confidence_level != self.confidence_level:
                raise ValueError("threshold confidence level does not match bundle")
            if threshold.fpr_interval.method != self.binomial_interval_method:
                raise ValueError("threshold interval method does not match bundle")
            targets.append(threshold.target_fpr)
        if targets != sorted(targets, reverse=True) or len(set(targets)) != len(targets):
            raise ValueError("thresholds must be unique and sorted by descending target FPR")
        require_sha256("calibration_input_hash", self.calibration_input_hash)
        require_sha256("bundle_hash", self.bundle_hash)
        expected_input_hash = sha256_json(self._input_payload())
        if self.calibration_input_hash != expected_input_hash:
            raise ValueError("calibration_input_hash does not match bundle inputs")
        for threshold in self.thresholds:
            if threshold.calibration_input_hash != self.calibration_input_hash:
                raise ValueError("threshold calibration input hash does not match bundle")
        expected_bundle_hash = sha256_json(
            {
                "calibration_input_hash": self.calibration_input_hash,
                "thresholds": self.thresholds,
            }
        )
        if self.bundle_hash != expected_bundle_hash:
            raise ValueError("bundle_hash does not match calibration bundle")

    def _input_payload(self) -> dict[str, object]:
        return {
            "calibration_algorithm_version": self.calibration_algorithm_version,
            "scope": self.scope,
            "detector_identity": self.detector_identity,
            "negative_manifest_hash": self.negative_manifest_hash,
            "negative_count": self.negative_count,
            "robust_center": self.robust_center,
            "robust_scale": self.robust_scale,
            "robust_scale_method": self.robust_scale_method,
            "null_quantiles": self.null_quantiles,
            "quantile_method": self.quantile_method,
            "comparison_operator": self.comparison_operator.value,
            "binomial_interval_method": self.binomial_interval_method,
            "confidence_level": self.confidence_level,
        }
