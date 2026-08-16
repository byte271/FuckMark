from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..native_observations import NativeObservationBatch
from .bayesian import (
    BAYESIAN_SCORER_ALGORITHM_VERSION,
    BayesianCheckpoint,
    bayesian_posterior,
)
from .types import CompatibilityStatus, DetectorFamily, ScoreDirection


BAYESIAN_EVIDENCE_ALGORITHM_VERSION = "deepmind-bayesian-evidence-v1"
BAYESIAN_UNVERIFIED_REASON = (
    "Bayesian evidence is source-replayed but confirmatory compatibility remains unverified until "
    "watermark mode, Bernoulli(0.5) distribution evidence, checkpoint provenance, and empirical validation are source-bound"
)


@dataclass(frozen=True, slots=True)
class BayesianDetectorEvidence:
    algorithm_version: str
    sample_id: str
    detector_family: DetectorFamily
    scorer_algorithm_version: str
    detector_config_hash: str
    checkpoint_hash: str
    checkpoint_source_id: str
    checkpoint_source_commit: str
    observation_batch_hash: str
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
    compatibility_status: CompatibilityStatus
    compatibility_reason: str
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != BAYESIAN_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported Bayesian evidence algorithm version")
        require_clean_string("sample_id", self.sample_id)
        if self.detector_family is not DetectorFamily.BAYESIAN:
            raise ValueError("Bayesian detector evidence must use the Bayesian detector family")
        if self.scorer_algorithm_version != BAYESIAN_SCORER_ALGORITHM_VERSION:
            raise ValueError("Bayesian evidence scorer version does not match the frozen scorer")
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_sha256("checkpoint_hash", self.checkpoint_hash)
        require_clean_string("checkpoint_source_id", self.checkpoint_source_id)
        require_clean_string("checkpoint_source_commit", self.checkpoint_source_commit)
        require_sha256("observation_batch_hash", self.observation_batch_hash)
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_clean_string("source_id", self.source_id)
        require_clean_string("source_commit", self.source_commit)
        if not isinstance(self.direction, ScoreDirection):
            raise TypeError("direction must be a ScoreDirection")
        if self.direction is not ScoreDirection.HIGHER_IS_MORE_WATERMARKED:
            raise ValueError("Bayesian evidence direction must be higher-is-more-watermarked")
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
        raw_score = float(self.raw_score)
        if not math.isfinite(raw_score) or raw_score < 0.0 or raw_score > 1.0:
            raise ValueError("raw_score must be finite and in [0, 1]")
        object.__setattr__(self, "raw_score", raw_score)
        if self.compatibility_status is not CompatibilityStatus.UNVERIFIED:
            raise ValueError("Bayesian evidence v1 cannot claim verified confirmatory compatibility")
        if self.compatibility_reason != BAYESIAN_UNVERIFIED_REASON:
            raise ValueError("Bayesian evidence v1 must preserve the frozen unverified reason")
        expected_config_hash = sha256_json(
            {
                "algorithm_version": self.algorithm_version,
                "scorer_algorithm_version": self.scorer_algorithm_version,
                "checkpoint_hash": self.checkpoint_hash,
                "checkpoint_source_id": self.checkpoint_source_id,
                "checkpoint_source_commit": self.checkpoint_source_commit,
            }
        )
        if self.detector_config_hash != expected_config_hash:
            raise ValueError("detector_config_hash does not match Bayesian checkpoint configuration")
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match Bayesian detector evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "sample_id": self.sample_id,
            "detector_family": self.detector_family.value,
            "scorer_algorithm_version": self.scorer_algorithm_version,
            "detector_config_hash": self.detector_config_hash,
            "checkpoint_hash": self.checkpoint_hash,
            "checkpoint_source_id": self.checkpoint_source_id,
            "checkpoint_source_commit": self.checkpoint_source_commit,
            "observation_batch_hash": self.observation_batch_hash,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "adapter_config_hash": self.adapter_config_hash,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "direction": self.direction.value,
            "total_observation_count": self.total_observation_count,
            "valid_observation_count": self.valid_observation_count,
            "depth": self.depth,
            "raw_score": self.raw_score,
            "compatibility_status": self.compatibility_status.value,
            "compatibility_reason": self.compatibility_reason,
        }


def build_bayesian_evidence(
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
) -> BayesianDetectorEvidence:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(checkpoint, BayesianCheckpoint):
        raise TypeError("checkpoint must be a BayesianCheckpoint")
    if batch.depth != checkpoint.depth:
        raise ValueError("observation batch depth must match Bayesian checkpoint depth")
    g_values = tuple(record.g_values for record in batch.records)
    mask = tuple(record.valid for record in batch.records)
    score = bayesian_posterior(g_values, mask, checkpoint)
    config_hash = sha256_json(
        {
            "algorithm_version": BAYESIAN_EVIDENCE_ALGORITHM_VERSION,
            "scorer_algorithm_version": BAYESIAN_SCORER_ALGORITHM_VERSION,
            "checkpoint_hash": checkpoint.checkpoint_hash,
            "checkpoint_source_id": checkpoint.source_id,
            "checkpoint_source_commit": checkpoint.source_commit,
        }
    )
    payload = {
        "algorithm_version": BAYESIAN_EVIDENCE_ALGORITHM_VERSION,
        "sample_id": batch.sample_id,
        "detector_family": DetectorFamily.BAYESIAN.value,
        "scorer_algorithm_version": BAYESIAN_SCORER_ALGORITHM_VERSION,
        "detector_config_hash": config_hash,
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "checkpoint_source_id": checkpoint.source_id,
        "checkpoint_source_commit": checkpoint.source_commit,
        "observation_batch_hash": sha256_json(batch),
        "adapter_id": batch.adapter_id,
        "adapter_algorithm_version": batch.adapter_algorithm_version,
        "adapter_config_hash": batch.adapter_config_hash,
        "source_id": batch.source_id,
        "source_commit": batch.source_commit,
        "direction": ScoreDirection.HIGHER_IS_MORE_WATERMARKED.value,
        "total_observation_count": len(batch.records),
        "valid_observation_count": sum(record.valid for record in batch.records),
        "depth": batch.depth,
        "raw_score": score,
        "compatibility_status": CompatibilityStatus.UNVERIFIED.value,
        "compatibility_reason": BAYESIAN_UNVERIFIED_REASON,
    }
    return BayesianDetectorEvidence(
        BAYESIAN_EVIDENCE_ALGORITHM_VERSION,
        batch.sample_id,
        DetectorFamily.BAYESIAN,
        BAYESIAN_SCORER_ALGORITHM_VERSION,
        config_hash,
        checkpoint.checkpoint_hash,
        checkpoint.source_id,
        checkpoint.source_commit,
        sha256_json(batch),
        batch.adapter_id,
        batch.adapter_algorithm_version,
        batch.adapter_config_hash,
        batch.source_id,
        batch.source_commit,
        ScoreDirection.HIGHER_IS_MORE_WATERMARKED,
        len(batch.records),
        sum(record.valid for record in batch.records),
        batch.depth,
        score,
        CompatibilityStatus.UNVERIFIED,
        BAYESIAN_UNVERIFIED_REASON,
        sha256_json(payload),
    )


def verify_bayesian_evidence(
    evidence: BayesianDetectorEvidence,
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
) -> None:
    if not isinstance(evidence, BayesianDetectorEvidence):
        raise TypeError("evidence must be BayesianDetectorEvidence")
    expected = build_bayesian_evidence(batch, checkpoint)
    if evidence != expected:
        raise ValueError("Bayesian detector evidence does not replay exactly from observation batch and checkpoint")
