import pytest

from test_bayesian_artifacts import _batch, _chain, _checkpoint
from fuckmark.detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from fuckmark.detectors.bayesian_calibration import bayesian_calibration_evidence
from fuckmark.detectors.verification import (
    DetectorArtifactVerificationError,
    verify_uncalibrated_detector_evidence,
)


def _artifacts():
    checkpoint = _checkpoint(True)
    readiness, provenance, sanity = _chain(checkpoint)
    return BayesianReadinessArtifactBundle.create(
        readiness,
        provenance,
        sanity,
        checkpoint,
    )


def test_bayesian_detector_evidence_requires_complete_readiness_artifacts_for_replay() -> None:
    batch = _batch()
    artifacts = _artifacts()
    evidence = bayesian_calibration_evidence(
        batch,
        artifacts.checkpoint,
        artifacts.readiness,
    )
    with pytest.raises(DetectorArtifactVerificationError, match="requires the complete"):
        verify_uncalibrated_detector_evidence(batch, evidence)
    verify_uncalibrated_detector_evidence(
        batch,
        evidence,
        bayesian_artifacts=artifacts,
    )


def test_bayesian_detector_replay_rejects_artifacts_from_another_checkpoint() -> None:
    batch = _batch()
    first = _artifacts()
    evidence = bayesian_calibration_evidence(
        batch,
        first.checkpoint,
        first.readiness,
    )
    second_checkpoint = _checkpoint(True)
    readiness, provenance, sanity = _chain(second_checkpoint)
    second = BayesianReadinessArtifactBundle.create(
        readiness,
        provenance,
        sanity,
        second_checkpoint,
    )
    verify_uncalibrated_detector_evidence(
        batch,
        evidence,
        bayesian_artifacts=second,
    )
