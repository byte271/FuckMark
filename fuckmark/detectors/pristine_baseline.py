from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .calibration_distribution import ExactBinomialInterval
from .calibration_identity import BaselineStatus


@dataclass(frozen=True, slots=True)
class PristineBaselineSummary:
    calibration_bundle_hash: str
    threshold_hash: str
    detector_identity_hash: str
    evidence_manifest_hash: str
    sample_count: int
    detected_count: int
    tpr: float
    tpr_interval: ExactBinomialInterval
    interpretability_floor: float
    status: BaselineStatus
    summary_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("calibration_bundle_hash", self.calibration_bundle_hash),
            ("threshold_hash", self.threshold_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("evidence_manifest_hash", self.evidence_manifest_hash),
            ("summary_hash", self.summary_hash),
        ):
            require_sha256(name, value)
        require_int("sample_count", self.sample_count)
        require_int("detected_count", self.detected_count)
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.detected_count < 0 or self.detected_count > self.sample_count:
            raise ValueError("detected_count is outside sample range")
        for name, value in (("tpr", self.tpr), ("interpretability_floor", self.interpretability_floor)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.tpr != self.detected_count / self.sample_count:
            raise ValueError("tpr does not match detected count")
        if self.interpretability_floor <= 0.0 or self.interpretability_floor > 1.0:
            raise ValueError("interpretability_floor must be in (0, 1]")
        if not isinstance(self.tpr_interval, ExactBinomialInterval):
            raise TypeError("tpr_interval must be an ExactBinomialInterval")
        if not self.tpr_interval.lower <= self.tpr <= self.tpr_interval.upper:
            raise ValueError("tpr must lie inside its exact binomial interval")
        from .calibration_statistics import exact_binomial_interval
        expected_interval = exact_binomial_interval(
            self.detected_count,
            self.sample_count,
            self.tpr_interval.confidence_level,
        )
        if self.tpr_interval != expected_interval:
            raise ValueError("tpr_interval does not match exact binomial interval")
        if not isinstance(self.status, BaselineStatus):
            raise TypeError("status must be a BaselineStatus")
        expected_status = BaselineStatus.PASS if self.tpr >= self.interpretability_floor else BaselineStatus.BELOW_FLOOR
        if self.status is not expected_status:
            raise ValueError("baseline status does not match TPR and interpretability floor")
        expected_hash = sha256_json(self._payload())
        if self.summary_hash != expected_hash:
            raise ValueError("summary_hash does not match pristine baseline summary")

    def _payload(self) -> dict[str, object]:
        return {
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "threshold_hash": self.threshold_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "sample_count": self.sample_count,
            "detected_count": self.detected_count,
            "tpr": self.tpr,
            "tpr_interval": self.tpr_interval,
            "interpretability_floor": self.interpretability_floor,
            "status": self.status.value,
        }
