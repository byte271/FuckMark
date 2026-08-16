from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .calibration_identity import ComparisonOperator
from .calibration_distribution import ExactBinomialInterval
from .types import ScoreDirection


@dataclass(frozen=True, slots=True)
class CalibratedDetectorResult:
    sample_id: str
    evidence_hash: str
    observation_batch_hash: str
    detector_identity_hash: str
    calibration_bundle_hash: str
    threshold_hash: str
    target_fpr: float
    achieved_calibration_fpr: float
    calibration_fpr_interval: ExactBinomialInterval
    comparison_operator: ComparisonOperator
    threshold_value: float
    raw_score: float
    direction: ScoreDirection
    robust_scale: float
    standardized_margin: float
    valid_observation_count: int
    decision: bool
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        for name, value in (
            ("evidence_hash", self.evidence_hash),
            ("observation_batch_hash", self.observation_batch_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("calibration_bundle_hash", self.calibration_bundle_hash),
            ("threshold_hash", self.threshold_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.comparison_operator, ComparisonOperator):
            raise TypeError("comparison_operator must be a ComparisonOperator")
        if not isinstance(self.direction, ScoreDirection):
            raise TypeError("direction must be a ScoreDirection")
        for name, value in (
            ("target_fpr", self.target_fpr),
            ("achieved_calibration_fpr", self.achieved_calibration_fpr),
            ("threshold_value", self.threshold_value),
            ("raw_score", self.raw_score),
            ("robust_scale", self.robust_scale),
            ("standardized_margin", self.standardized_margin),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.target_fpr <= 0.0 or self.target_fpr >= 1.0:
            raise ValueError("target_fpr must be between 0 and 1")
        if self.achieved_calibration_fpr < 0.0 or self.achieved_calibration_fpr > self.target_fpr:
            raise ValueError("achieved_calibration_fpr is outside target range")
        if self.threshold_value < 0.0 or self.threshold_value > 1.0:
            raise ValueError("threshold_value must be between 0 and 1")
        if self.raw_score < 0.0 or self.raw_score > 1.0:
            raise ValueError("raw_score must be between 0 and 1")
        if self.robust_scale <= 0.0:
            raise ValueError("robust_scale must be positive")
        if not isinstance(self.calibration_fpr_interval, ExactBinomialInterval):
            raise TypeError("calibration_fpr_interval must be an ExactBinomialInterval")
        if not self.calibration_fpr_interval.lower <= self.achieved_calibration_fpr <= self.calibration_fpr_interval.upper:
            raise ValueError("achieved calibration FPR must lie inside its exact interval")
        require_int("valid_observation_count", self.valid_observation_count)
        if self.valid_observation_count <= 0:
            raise ValueError("valid_observation_count must be positive")
        if not isinstance(self.decision, bool):
            raise TypeError("decision must be a boolean")
        if self.direction is not ScoreDirection.HIGHER_IS_MORE_WATERMARKED:
            raise ValueError("unsupported score direction")
        expected_decision = (
            self.raw_score > self.threshold_value
            if self.comparison_operator is ComparisonOperator.GREATER_THAN
            else self.raw_score >= self.threshold_value
        )
        if self.decision is not expected_decision:
            raise ValueError("decision does not match score and threshold")
        expected_margin = (self.raw_score - self.threshold_value) / self.robust_scale
        if not math.isclose(self.standardized_margin, expected_margin, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("standardized_margin does not match score, threshold, and robust scale")
        expected_hash = sha256_json(self._payload())
        if self.result_hash != expected_hash:
            raise ValueError("result_hash does not match calibrated detector result")

    def _payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "evidence_hash": self.evidence_hash,
            "observation_batch_hash": self.observation_batch_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "threshold_hash": self.threshold_hash,
            "target_fpr": self.target_fpr,
            "achieved_calibration_fpr": self.achieved_calibration_fpr,
            "calibration_fpr_interval": self.calibration_fpr_interval,
            "comparison_operator": self.comparison_operator.value,
            "threshold_value": self.threshold_value,
            "raw_score": self.raw_score,
            "direction": self.direction.value,
            "robust_scale": self.robust_scale,
            "standardized_margin": self.standardized_margin,
            "valid_observation_count": self.valid_observation_count,
            "decision": self.decision,
        }
