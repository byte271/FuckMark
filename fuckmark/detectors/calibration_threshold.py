from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .calibration_distribution import ExactBinomialInterval
from .calibration_identity import ComparisonOperator


@dataclass(frozen=True, slots=True)
class CalibrationThreshold:
    target_fpr: float
    comparison_operator: ComparisonOperator
    value: float
    false_positive_count: int
    calibration_count: int
    achieved_fpr: float
    fpr_interval: ExactBinomialInterval
    calibration_input_hash: str
    threshold_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_operator, ComparisonOperator):
            raise TypeError("comparison_operator must be a ComparisonOperator")
        for name, value in (
            ("target_fpr", self.target_fpr),
            ("value", self.value),
            ("achieved_fpr", self.achieved_fpr),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.target_fpr <= 0.0 or self.target_fpr >= 1.0:
            raise ValueError("target_fpr must be between 0 and 1")
        if self.value < 0.0 or self.value > 1.0:
            raise ValueError("threshold value must be between 0 and 1")
        require_int("false_positive_count", self.false_positive_count)
        require_int("calibration_count", self.calibration_count)
        if self.calibration_count <= 0:
            raise ValueError("calibration_count must be positive")
        if self.false_positive_count < 0 or self.false_positive_count > self.calibration_count:
            raise ValueError("false_positive_count is outside calibration range")
        expected_fpr = self.false_positive_count / self.calibration_count
        if self.achieved_fpr != expected_fpr:
            raise ValueError("achieved_fpr does not match false-positive count")
        if self.achieved_fpr > self.target_fpr:
            raise ValueError("achieved_fpr exceeds target_fpr")
        if not isinstance(self.fpr_interval, ExactBinomialInterval):
            raise TypeError("fpr_interval must be an ExactBinomialInterval")
        if not self.fpr_interval.lower <= self.achieved_fpr <= self.fpr_interval.upper:
            raise ValueError("achieved_fpr must lie inside its exact binomial interval")
        from .calibration_statistics import exact_binomial_interval
        expected_interval = exact_binomial_interval(
            self.false_positive_count,
            self.calibration_count,
            self.fpr_interval.confidence_level,
        )
        if self.fpr_interval != expected_interval:
            raise ValueError("confidence interval does not match exact binomial interval")
        require_sha256("calibration_input_hash", self.calibration_input_hash)
        require_sha256("threshold_hash", self.threshold_hash)
        expected_hash = sha256_json(
            {
                "target_fpr": self.target_fpr,
                "comparison_operator": self.comparison_operator.value,
                "value": self.value,
                "false_positive_count": self.false_positive_count,
                "calibration_count": self.calibration_count,
                "achieved_fpr": self.achieved_fpr,
                "fpr_interval": self.fpr_interval,
                "calibration_input_hash": self.calibration_input_hash,
            }
        )
        if self.threshold_hash != expected_hash:
            raise ValueError("threshold_hash does not match threshold fields")
