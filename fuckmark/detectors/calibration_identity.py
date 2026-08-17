from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .types import DetectorFamily, ScoreDirection, UncalibratedDetectorEvidence


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ComparisonOperator(str, Enum):
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="


class BaselineStatus(str, Enum):
    PASS = "PASS"
    BELOW_FLOOR = "BELOW_FLOOR"


class CalibrationResolutionError(ValueError):
    pass


class CalibrationIdentityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CalibrationScope:
    corpus_id: str
    population_id: str
    length_policy_id: str
    token_track: str
    prompt_boundary_mode: str
    scope_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("corpus_id", self.corpus_id),
            ("population_id", self.population_id),
            ("length_policy_id", self.length_policy_id),
            ("token_track", self.token_track),
            ("prompt_boundary_mode", self.prompt_boundary_mode),
        ):
            require_clean_string(name, value)
        require_sha256("scope_hash", self.scope_hash)
        expected = sha256_json(
            {
                "corpus_id": self.corpus_id,
                "population_id": self.population_id,
                "length_policy_id": self.length_policy_id,
                "token_track": self.token_track,
                "prompt_boundary_mode": self.prompt_boundary_mode,
            }
        )
        if self.scope_hash != expected:
            raise ValueError("scope_hash does not match calibration scope")

    @classmethod
    def create(
        cls,
        corpus_id: str,
        population_id: str,
        length_policy_id: str,
        token_track: str,
        prompt_boundary_mode: str,
    ) -> CalibrationScope:
        payload = {
            "corpus_id": corpus_id,
            "population_id": population_id,
            "length_policy_id": length_policy_id,
            "token_track": token_track,
            "prompt_boundary_mode": prompt_boundary_mode,
        }
        return cls(
            corpus_id=corpus_id,
            population_id=population_id,
            length_policy_id=length_policy_id,
            token_track=token_track,
            prompt_boundary_mode=prompt_boundary_mode,
            scope_hash=sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class DetectorCalibrationIdentity:
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
    depth: int
    normalized_weights: tuple[float, ...]
    identity_hash: str
    detector_artifact_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.detector_family, DetectorFamily):
            raise TypeError("detector_family must be a DetectorFamily")
        if not isinstance(self.direction, ScoreDirection):
            raise TypeError("direction must be a ScoreDirection")
        for name, value in (
            ("detector_algorithm_version", self.detector_algorithm_version),
            ("detector_source_id", self.detector_source_id),
            ("detector_source_commit", self.detector_source_commit),
            ("adapter_id", self.adapter_id),
            ("adapter_algorithm_version", self.adapter_algorithm_version),
            ("source_id", self.source_id),
            ("source_commit", self.source_commit),
        ):
            require_clean_string(name, value)
        if _GIT_SHA_RE.fullmatch(self.detector_source_commit) is None:
            raise ValueError("detector_source_commit must be a full lowercase 40-character Git revision")
        if _GIT_SHA_RE.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be a full lowercase 40-character Git revision")
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_sha256("identity_hash", self.identity_hash)
        require_int("depth", self.depth)
        if self.depth <= 0:
            raise ValueError("depth must be positive")
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
        normalized_weights = tuple(weights)
        if not math.isclose(math.fsum(normalized_weights), float(self.depth), rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("normalized_weights must sum to depth")
        object.__setattr__(self, "normalized_weights", normalized_weights)
        if not isinstance(self.detector_artifact_hashes, tuple):
            raise TypeError("detector_artifact_hashes must be a tuple")
        if self.detector_artifact_hashes != tuple(sorted(set(self.detector_artifact_hashes))):
            raise ValueError("detector_artifact_hashes must be unique and canonically ordered")
        for value in self.detector_artifact_hashes:
            require_sha256("detector artifact hash", value)
        config_payload = {
            "detector_family": self.detector_family.value,
            "algorithm_version": self.detector_algorithm_version,
            "detector_source_commit": self.detector_source_commit,
            "normalized_weights": normalized_weights,
        }
        if self.detector_artifact_hashes:
            config_payload["detector_artifact_hashes"] = self.detector_artifact_hashes
        expected_config_hash = sha256_json(config_payload)
        if self.detector_config_hash != expected_config_hash:
            raise ValueError("detector_config_hash does not match detector calibration identity fields")
        expected = sha256_json(self._payload(normalized_weights))
        if self.identity_hash != expected:
            raise ValueError("identity_hash does not match detector calibration identity")

    def _payload(self, weights: tuple[float, ...]) -> dict[str, object]:
        payload = {
            "detector_family": self.detector_family.value,
            "detector_algorithm_version": self.detector_algorithm_version,
            "detector_config_hash": self.detector_config_hash,
            "detector_source_id": self.detector_source_id,
            "detector_source_commit": self.detector_source_commit,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "adapter_config_hash": self.adapter_config_hash,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "direction": self.direction.value,
            "depth": self.depth,
            "normalized_weights": weights,
        }
        if self.detector_artifact_hashes:
            payload["detector_artifact_hashes"] = self.detector_artifact_hashes
        return payload

    @classmethod
    def from_evidence(cls, evidence: UncalibratedDetectorEvidence) -> DetectorCalibrationIdentity:
        if not isinstance(evidence, UncalibratedDetectorEvidence):
            raise TypeError("evidence must be UncalibratedDetectorEvidence")
        payload = {
            "detector_family": evidence.detector_family.value,
            "detector_algorithm_version": evidence.detector_algorithm_version,
            "detector_config_hash": evidence.detector_config_hash,
            "detector_source_id": evidence.detector_source_id,
            "detector_source_commit": evidence.detector_source_commit,
            "adapter_id": evidence.adapter_id,
            "adapter_algorithm_version": evidence.adapter_algorithm_version,
            "adapter_config_hash": evidence.adapter_config_hash,
            "source_id": evidence.source_id,
            "source_commit": evidence.source_commit,
            "direction": evidence.direction.value,
            "depth": evidence.depth,
            "normalized_weights": evidence.normalized_weights,
        }
        if evidence.detector_artifact_hashes:
            payload["detector_artifact_hashes"] = evidence.detector_artifact_hashes
        return cls(
            detector_family=evidence.detector_family,
            detector_algorithm_version=evidence.detector_algorithm_version,
            detector_config_hash=evidence.detector_config_hash,
            detector_source_id=evidence.detector_source_id,
            detector_source_commit=evidence.detector_source_commit,
            adapter_id=evidence.adapter_id,
            adapter_algorithm_version=evidence.adapter_algorithm_version,
            adapter_config_hash=evidence.adapter_config_hash,
            source_id=evidence.source_id,
            source_commit=evidence.source_commit,
            direction=evidence.direction,
            depth=evidence.depth,
            normalized_weights=evidence.normalized_weights,
            identity_hash=sha256_json(payload),
            detector_artifact_hashes=evidence.detector_artifact_hashes,
        )
