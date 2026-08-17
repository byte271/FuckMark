from __future__ import annotations

from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from ..hashing import sha256_json
from ..native_observations import NativeObservationBatch
from .bayesian import BAYESIAN_SCORER_ALGORITHM_VERSION, BayesianCheckpoint, bayesian_posterior
from .bayesian_training import BayesianConfirmatoryReadiness
from .compatibility import require_supported_detector
from .types import DetectorFamily, ScoreDirection, UncalibratedDetectorEvidence


BAYESIAN_CALIBRATION_EVIDENCE_VERSION = "deepmind-bayesian-calibration-evidence-v1"


def _artifact_hashes(
    checkpoint: BayesianCheckpoint,
    readiness: BayesianConfirmatoryReadiness,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                checkpoint.checkpoint_hash,
                readiness.readiness_hash,
                readiness.training_provenance_hash,
                readiness.sanity_evidence_hash,
            }
        )
    )


def bayesian_calibration_evidence(
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
    readiness: BayesianConfirmatoryReadiness,
) -> UncalibratedDetectorEvidence:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(checkpoint, BayesianCheckpoint):
        raise TypeError("checkpoint must be a BayesianCheckpoint")
    if not isinstance(readiness, BayesianConfirmatoryReadiness):
        raise TypeError("readiness must be a BayesianConfirmatoryReadiness")
    if readiness.checkpoint_hash != checkpoint.checkpoint_hash:
        raise ValueError("Bayesian readiness checkpoint hash does not match checkpoint")
    if batch.depth != checkpoint.watermarking_depth:
        raise ValueError("observation batch depth must match Bayesian checkpoint depth")
    compatibility = require_supported_detector(
        batch,
        DetectorFamily.BAYESIAN,
        bayesian_readiness=readiness,
    )
    score = bayesian_posterior(batch.g_values, batch.valid_mask, checkpoint)
    artifacts = _artifact_hashes(checkpoint, readiness)
    normalized_weights = (1.0,) * batch.depth
    config_hash = sha256_json(
        {
            "detector_family": DetectorFamily.BAYESIAN.value,
            "algorithm_version": BAYESIAN_SCORER_ALGORITHM_VERSION,
            "detector_source_commit": DEEPMIND_REFERENCE_SOURCE_PIN.commit,
            "normalized_weights": normalized_weights,
            "detector_artifact_hashes": artifacts,
        }
    )
    return UncalibratedDetectorEvidence(
        sample_id=batch.sample_id,
        detector_family=DetectorFamily.BAYESIAN,
        detector_algorithm_version=BAYESIAN_SCORER_ALGORITHM_VERSION,
        detector_config_hash=config_hash,
        observation_batch_hash=sha256_json(batch),
        detector_source_id=DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
        detector_source_commit=DEEPMIND_REFERENCE_SOURCE_PIN.commit,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        adapter_config_hash=batch.adapter_config_hash,
        source_id=batch.source_id,
        source_commit=batch.source_commit,
        direction=ScoreDirection.HIGHER_IS_MORE_WATERMARKED,
        total_observation_count=len(batch.records),
        valid_observation_count=sum(batch.valid_mask),
        depth=batch.depth,
        raw_score=score,
        normalized_weights=normalized_weights,
        compatibility=compatibility,
        detector_artifact_hashes=artifacts,
    )


def verify_bayesian_calibration_evidence(
    evidence: UncalibratedDetectorEvidence,
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
    readiness: BayesianConfirmatoryReadiness,
) -> None:
    if not isinstance(evidence, UncalibratedDetectorEvidence):
        raise TypeError("evidence must be an UncalibratedDetectorEvidence")
    expected = bayesian_calibration_evidence(batch, checkpoint, readiness)
    if evidence != expected:
        raise ValueError("Bayesian calibration evidence does not replay exactly from frozen inputs")
