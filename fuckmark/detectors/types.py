from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DetectorFamily(str, Enum):
    MEAN = "mean"
    WEIGHTED_MEAN = "weighted_mean"
    BAYESIAN = "bayesian"


class CompatibilityStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIED = "UNVERIFIED"


class ScoreDirection(str, Enum):
    HIGHER_IS_MORE_WATERMARKED = "higher_is_more_watermarked"


class ZeroValidObservationsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DetectorCompatibility:
    status: CompatibilityStatus
    detector_family: DetectorFamily
    adapter_id: str
    adapter_algorithm_version: str
    source: str
    reason: str
    validated_by: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, CompatibilityStatus):
            raise TypeError("status must be a CompatibilityStatus")
        if not isinstance(self.detector_family, DetectorFamily):
            raise TypeError("detector_family must be a DetectorFamily")
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_clean_string("source", self.source)
        require_clean_string("reason", self.reason)
        if not isinstance(self.validated_by, tuple):
            raise TypeError("validated_by must be a tuple")
        for value in self.validated_by:
            require_clean_string("validated_by value", value)
        if self.status is CompatibilityStatus.SUPPORTED and not self.validated_by:
            raise ValueError("supported compatibility must name validation fixtures")


class DetectorCompatibilityError(ValueError):
    def __init__(self, compatibility: DetectorCompatibility) -> None:
        if not isinstance(compatibility, DetectorCompatibility):
            raise TypeError("compatibility must be a DetectorCompatibility")
        self.compatibility = compatibility
        super().__init__(
            f"Detector compatibility is {compatibility.status.value}: {compatibility.reason}"
        )


@dataclass(frozen=True, slots=True)
class UncalibratedDetectorEvidence:
    sample_id: str
    detector_family: DetectorFamily
    detector_algorithm_version: str
    detector_config_hash: str
    detector_source_id: str
    detector_source_commit: str
    adapter_id: str
    adapter_algorithm_version: str
    adapter_config_hash: str
    source_id: str
    source_commit: str
    direction: ScoreDirection
    total_observation_count: int
    valid_observation_count: int
    depth: int
    raw_score: float
    normalized_weights: tuple[float, ...]
    compatibility: DetectorCompatibility

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.detector_family, DetectorFamily):
            raise TypeError("detector_family must be a DetectorFamily")
        require_clean_string("detector_algorithm_version", self.detector_algorithm_version)
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_clean_string("detector_source_id", self.detector_source_id)
        require_clean_string("detector_source_commit", self.detector_source_commit)
        if _GIT_SHA_RE.fullmatch(self.detector_source_commit) is None:
            raise ValueError("detector_source_commit must be a full lowercase 40-character Git revision")
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_clean_string("source_id", self.source_id)
        require_clean_string("source_commit", self.source_commit)
        if _GIT_SHA_RE.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be a full lowercase 40-character Git revision")
        if not isinstance(self.direction, ScoreDirection):
            raise TypeError("direction must be a ScoreDirection")
        for name, value in (
            ("total_observation_count", self.total_observation_count),
            ("valid_observation_count", self.valid_observation_count),
            ("depth", self.depth),
        ):
            require_int(name, value)
        if self.total_observation_count < 0:
            raise ValueError("total_observation_count must be non-negative")
        if self.valid_observation_count <= 0:
            raise ValueError("valid_observation_count must be positive")
        if self.valid_observation_count > self.total_observation_count:
            raise ValueError("valid_observation_count cannot exceed total_observation_count")
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if isinstance(self.raw_score, bool) or not isinstance(self.raw_score, (int, float)):
            raise TypeError("raw_score must be a real number")
        score = float(self.raw_score)
        if not math.isfinite(score):
            raise ValueError("raw_score must be finite")
        if score < 0.0 or score > 1.0:
            raise ValueError("raw_score must be between 0 and 1")
        object.__setattr__(self, "raw_score", score)
        if not isinstance(self.normalized_weights, tuple):
            raise TypeError("normalized_weights must be a tuple")
        if len(self.normalized_weights) != self.depth:
            raise ValueError("normalized_weights length must match depth")
        weights: list[float] = []
        for value in self.normalized_weights:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("normalized_weights must contain real numbers")
            number = float(value)
            if not math.isfinite(number) or number < 0.0:
                raise ValueError("normalized_weights must contain finite non-negative values")
            weights.append(number)
        if not math.isclose(math.fsum(weights), float(self.depth), rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("normalized_weights must sum to depth")
        object.__setattr__(self, "normalized_weights", tuple(weights))
        if not isinstance(self.compatibility, DetectorCompatibility):
            raise TypeError("compatibility must be a DetectorCompatibility")
        if self.compatibility.status is not CompatibilityStatus.SUPPORTED:
            raise ValueError("uncalibrated evidence requires supported compatibility")
        if self.compatibility.detector_family is not self.detector_family:
            raise ValueError("compatibility detector family does not match evidence")
        if self.compatibility.adapter_id != self.adapter_id:
            raise ValueError("compatibility adapter_id does not match evidence")
        if self.compatibility.adapter_algorithm_version != self.adapter_algorithm_version:
            raise ValueError("compatibility adapter version does not match evidence")
