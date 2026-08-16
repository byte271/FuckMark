from dataclasses import replace

import pytest

from fuckmark.corpus import CorpusSplit
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.e02_pristine import (
    E02_ALGORITHM_VERSION,
    E02InputError,
    E02Status,
    run_e02_pristine_detectability,
)
from fuckmark.hashing import sha256_json
from tiny_dev_experiment_helpers import attack_evidence, calibration_evidence, tiny_dev_artifact


def _calibration():
    return calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())


def test_e02_reports_distributions_auc_and_both_frozen_operating_points() -> None:
    artifact = tiny_dev_artifact()
    result = run_e02_pristine_detectability(artifact, _calibration(), attack_evidence())
    assert result.algorithm_version == E02_ALGORITHM_VERSION
    assert result.status is E02Status.PASS
    assert result.auc == 1.0
    assert result.watermarked_scores == tuple(sorted(result.watermarked_scores))
    assert result.unwatermarked_scores == tuple(sorted(result.unwatermarked_scores))
    assert tuple(point.target_fpr for point in result.operating_points) == (0.05, 0.01)
    assert all(point.tpr == 1.0 for point in result.operating_points)
    assert all(point.evaluation_fpr == 0.0 for point in result.operating_points)
    assert all(point.positive_count == 4 for point in result.operating_points)
    assert all(point.negative_count == 4 for point in result.operating_points)


def test_e02_weak_pristine_tpr_is_underpowered_not_success() -> None:
    result = run_e02_pristine_detectability(
        tiny_dev_artifact(),
        _calibration(),
        attack_evidence(underpowered=True),
    )
    assert result.status is E02Status.UNDERPOWERED
    primary = next(point for point in result.operating_points if point.target_fpr == 0.01)
    assert primary.tpr < 0.80


def test_e02_requires_exact_attack_split_evidence_ids() -> None:
    artifact = tiny_dev_artifact()
    evidence = attack_evidence()
    with pytest.raises(E02InputError, match="exactly match"):
        run_e02_pristine_detectability(artifact, _calibration(), evidence[:-1])
    calibration_sample_id = next(
        sample.sample_id
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
    )
    contaminated = list(evidence)
    contaminated[-1] = replace(contaminated[-1], sample_id=calibration_sample_id)
    with pytest.raises(E02InputError, match="unexpected"):
        run_e02_pristine_detectability(artifact, _calibration(), tuple(contaminated))


def test_e02_replays_identically_independent_of_evidence_input_order() -> None:
    artifact = tiny_dev_artifact()
    calibration = _calibration()
    evidence = attack_evidence()
    first = run_e02_pristine_detectability(artifact, calibration, evidence)
    second = run_e02_pristine_detectability(artifact, calibration, tuple(reversed(evidence)))
    assert second == first


def test_e02_rejects_calibration_binding_from_other_corpus_identity() -> None:
    artifact = tiny_dev_artifact()
    calibration = _calibration()
    other_artifact_hash = "f" * 64
    forged_hash = sha256_json(
        {
            "algorithm_version": calibration.algorithm_version,
            "corpus_id": calibration.corpus_id,
            "tiny_dev_artifact_hash": other_artifact_hash,
            "calibration_sample_id_hash": calibration.calibration_sample_id_hash,
            "calibration_bundle_hash": calibration.calibration_bundle.bundle_hash,
        }
    )
    forged = replace(
        calibration,
        tiny_dev_artifact_hash=other_artifact_hash,
        binding_hash=forged_hash,
    )
    with pytest.raises(E02InputError, match="does not belong"):
        run_e02_pristine_detectability(artifact, forged, attack_evidence())


def test_e02_result_hash_rejects_tampering() -> None:
    result = run_e02_pristine_detectability(tiny_dev_artifact(), _calibration(), attack_evidence())
    with pytest.raises(ValueError, match="result_hash"):
        replace(result, result_hash="f" * 64)
