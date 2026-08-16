from dataclasses import replace

import pytest

from fuckmark.corpus import CorpusSplit, WatermarkLabel
from fuckmark.experiments.development_calibration import (
    DEVELOPMENT_CALIBRATION_BINDING_VERSION,
    DEVELOPMENT_TARGET_FPRS,
    DevelopmentCalibrationError,
    calibrate_tiny_dev_detector,
)
from fuckmark.hashing import sha256_text
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


def test_tiny_dev_calibration_binds_exact_100_negative_ids_and_freezes_fprs() -> None:
    artifact = tiny_dev_artifact()
    evidence = calibration_evidence()
    binding = calibrate_tiny_dev_detector(artifact, evidence)
    expected_ids = tuple(
        sorted(
            sample.sample_id
            for sample in artifact.manifest.samples
            if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
            and sample.label is WatermarkLabel.UNWATERMARKED
        )
    )
    assert binding.algorithm_version == DEVELOPMENT_CALIBRATION_BINDING_VERSION
    assert binding.calibration_sample_ids == expected_ids
    assert len(binding.calibration_sample_ids) == 100
    assert binding.calibration_bundle.negative_count == 100
    assert tuple(threshold.target_fpr for threshold in binding.calibration_bundle.thresholds) == DEVELOPMENT_TARGET_FPRS
    assert all(
        threshold.achieved_fpr <= threshold.target_fpr
        for threshold in binding.calibration_bundle.thresholds
    )
    assert binding.tiny_dev_artifact_hash == artifact.artifact_hash


def test_calibration_binding_replays_deterministically() -> None:
    artifact = tiny_dev_artifact()
    evidence = calibration_evidence()
    first = calibrate_tiny_dev_detector(artifact, evidence)
    second = calibrate_tiny_dev_detector(artifact, tuple(reversed(evidence)))
    assert second == first


def test_calibration_binding_rejects_missing_negative_even_when_other_99_are_valid() -> None:
    artifact = tiny_dev_artifact()
    evidence = calibration_evidence()
    with pytest.raises(DevelopmentCalibrationError, match="exactly match"):
        calibrate_tiny_dev_detector(artifact, evidence[:-1])


def test_calibration_binding_rejects_attack_sample_substitution_at_same_count() -> None:
    artifact = tiny_dev_artifact()
    evidence = list(calibration_evidence())
    attack_sample = next(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
        and sample.label is WatermarkLabel.UNWATERMARKED
    )
    evidence[-1] = replace(
        evidence[-1],
        sample_id=attack_sample.sample_id,
        observation_batch_hash=sha256_text("attack-sample-contamination"),
    )
    with pytest.raises(DevelopmentCalibrationError, match="unexpected"):
        calibrate_tiny_dev_detector(artifact, tuple(evidence))


def test_calibration_binding_rejects_duplicate_sample_id() -> None:
    artifact = tiny_dev_artifact()
    evidence = list(calibration_evidence())
    evidence[-1] = replace(
        evidence[-1],
        sample_id=evidence[0].sample_id,
        observation_batch_hash=sha256_text("duplicate-sample-id"),
    )
    with pytest.raises(DevelopmentCalibrationError, match="exactly match"):
        calibrate_tiny_dev_detector(artifact, tuple(evidence))


def test_calibration_binding_hash_rejects_tampering() -> None:
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    with pytest.raises(ValueError, match="binding_hash"):
        replace(binding, binding_hash="f" * 64)
