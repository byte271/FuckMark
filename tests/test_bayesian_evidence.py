from pathlib import Path

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors.bayesian import load_bayesian_checkpoint
from fuckmark.detectors.bayesian_evidence import (
    BAYESIAN_UNVERIFIED_REASON,
    BayesianDetectorEvidence,
    build_bayesian_evidence,
    verify_bayesian_evidence,
)
from fuckmark.detectors.types import CompatibilityStatus
from fuckmark.hashing import sha256_json
from fuckmark.native_observations import build_native_observations


FIXTURE = Path(__file__).parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


def _evidence():
    checkpoint = load_bayesian_checkpoint(FIXTURE)
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    batch = build_native_observations(
        "bayesian-evidence-sample",
        (1, 2, 3, 4, 5, 6, 7, 8),
        999,
        adapter,
    )
    return build_bayesian_evidence(batch, checkpoint), batch, checkpoint


def test_bayesian_evidence_replays_posterior_and_stays_explicitly_unverified() -> None:
    evidence, batch, checkpoint = _evidence()
    assert 0.0 <= evidence.raw_score <= 1.0
    assert evidence.compatibility_status is CompatibilityStatus.UNVERIFIED
    assert evidence.compatibility_reason == BAYESIAN_UNVERIFIED_REASON
    assert evidence.checkpoint_hash == checkpoint.checkpoint_hash
    assert evidence.observation_batch_hash == sha256_json(batch)
    verify_bayesian_evidence(evidence, batch, checkpoint)


def test_bayesian_evidence_replay_rejects_rehashed_wrong_posterior() -> None:
    evidence, batch, checkpoint = _evidence()
    wrong_score = min(1.0, evidence.raw_score + 0.1)
    if wrong_score == evidence.raw_score:
        wrong_score = max(0.0, evidence.raw_score - 0.1)
    payload = evidence._payload()
    payload["raw_score"] = wrong_score
    forged = BayesianDetectorEvidence(
        evidence.algorithm_version,
        evidence.sample_id,
        evidence.detector_family,
        evidence.scorer_algorithm_version,
        evidence.detector_config_hash,
        evidence.checkpoint_hash,
        evidence.checkpoint_source_id,
        evidence.checkpoint_source_commit,
        evidence.observation_batch_hash,
        evidence.adapter_id,
        evidence.adapter_algorithm_version,
        evidence.adapter_config_hash,
        evidence.source_id,
        evidence.source_commit,
        evidence.direction,
        evidence.total_observation_count,
        evidence.valid_observation_count,
        evidence.depth,
        wrong_score,
        evidence.compatibility_status,
        evidence.compatibility_reason,
        sha256_json(payload),
    )
    with pytest.raises(ValueError, match="does not replay exactly"):
        verify_bayesian_evidence(forged, batch, checkpoint)


def test_bayesian_evidence_v1_cannot_claim_supported_compatibility() -> None:
    evidence, _, _ = _evidence()
    payload = evidence._payload()
    payload["compatibility_status"] = CompatibilityStatus.SUPPORTED.value
    with pytest.raises(ValueError, match="cannot claim verified confirmatory compatibility"):
        BayesianDetectorEvidence(
            evidence.algorithm_version,
            evidence.sample_id,
            evidence.detector_family,
            evidence.scorer_algorithm_version,
            evidence.detector_config_hash,
            evidence.checkpoint_hash,
            evidence.checkpoint_source_id,
            evidence.checkpoint_source_commit,
            evidence.observation_batch_hash,
            evidence.adapter_id,
            evidence.adapter_algorithm_version,
            evidence.adapter_config_hash,
            evidence.source_id,
            evidence.source_commit,
            evidence.direction,
            evidence.total_observation_count,
            evidence.valid_observation_count,
            evidence.depth,
            evidence.raw_score,
            CompatibilityStatus.SUPPORTED,
            evidence.compatibility_reason,
            sha256_json(payload),
        )
