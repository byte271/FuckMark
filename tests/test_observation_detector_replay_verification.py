from dataclasses import replace

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.corpus import CorpusSplit, WatermarkLabel
from fuckmark.detectors import (
    DetectorArtifactVerificationError,
    apply_calibration,
    evaluate_pristine_baseline,
    mean_evidence,
    verify_calibrated_detector_result,
    verify_calibration_bundle,
    verify_pristine_baseline_summary,
    verify_uncalibrated_detector_evidence,
    weighted_mean_evidence,
)
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.hashing import sha256_json
from fuckmark.native_observations import build_native_observations
from fuckmark.observation_verification import (
    NativeObservationVerificationError,
    verify_native_observation_batch,
)
from tiny_dev_experiment_helpers import attack_evidence, calibration_evidence, tiny_dev_artifact


def _adapter():
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )


def _batch():
    return build_native_observations(
        "replay-source",
        (1, 2, 3, 4, 5, 6),
        999,
        _adapter(),
    )


def test_native_observation_replay_rejects_structurally_valid_forged_g_values() -> None:
    batch = _batch()
    verify_native_observation_batch(batch, _adapter())
    first = batch.records[0]
    flipped = (1 - first.g_values[0], *first.g_values[1:])
    forged_record = replace(first, g_values=flipped)
    forged_batch = replace(batch, records=(forged_record, *batch.records[1:]))
    assert forged_batch.g_values != batch.g_values
    with pytest.raises(NativeObservationVerificationError, match="does not replay exactly"):
        verify_native_observation_batch(forged_batch, _adapter())


def test_mean_family_evidence_replay_rejects_self_valid_score_forgery() -> None:
    batch = _batch()
    evidence = mean_evidence(batch)
    weighted = weighted_mean_evidence(batch, (3.0, 2.0, 1.0))
    verify_uncalibrated_detector_evidence(batch, evidence)
    verify_uncalibrated_detector_evidence(batch, weighted)
    forged_score = 0.0 if evidence.raw_score != 0.0 else 1.0
    forged = replace(evidence, raw_score=forged_score)
    assert forged.raw_score != evidence.raw_score
    with pytest.raises(DetectorArtifactVerificationError, match="does not replay exactly"):
        verify_uncalibrated_detector_evidence(batch, forged)


def test_calibration_bundle_replay_rejects_other_valid_negative_evidence() -> None:
    artifact = tiny_dev_artifact()
    rows = calibration_evidence()
    binding = calibrate_tiny_dev_detector(artifact, rows)
    verify_calibration_bundle(rows, binding.calibration_bundle)
    changed = list(rows)
    first = changed[0]
    changed[0] = replace(
        first,
        raw_score=min(1.0, first.raw_score + 0.4),
    )
    with pytest.raises(DetectorArtifactVerificationError, match="calibration bundle does not replay exactly"):
        verify_calibration_bundle(tuple(changed), binding.calibration_bundle)


def test_calibrated_result_replay_rejects_rehashed_bundle_field_forgery() -> None:
    artifact = tiny_dev_artifact()
    binding = calibrate_tiny_dev_detector(artifact, calibration_evidence())
    evidence = attack_evidence()[0]
    result = apply_calibration(evidence, binding.calibration_bundle, 0.01)
    verify_calibrated_detector_result(evidence, binding.calibration_bundle, result)
    forged_scale = result.robust_scale * 2.0
    forged_margin = (result.raw_score - result.threshold_value) / forged_scale
    forged_payload = result._payload()
    forged_payload["robust_scale"] = forged_scale
    forged_payload["standardized_margin"] = forged_margin
    forged = replace(
        result,
        robust_scale=forged_scale,
        standardized_margin=forged_margin,
        result_hash=sha256_json(forged_payload),
    )
    assert forged.result_hash != result.result_hash
    with pytest.raises(DetectorArtifactVerificationError, match="does not replay exactly"):
        verify_calibrated_detector_result(evidence, binding.calibration_bundle, forged)


def test_pristine_baseline_replay_rejects_other_valid_calibrated_results() -> None:
    artifact = tiny_dev_artifact()
    binding = calibrate_tiny_dev_detector(artifact, calibration_evidence())
    positive_ids = {
        sample.sample_id
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
        and sample.label is WatermarkLabel.WATERMARKED
    }
    results = tuple(
        apply_calibration(evidence, binding.calibration_bundle, 0.01)
        for evidence in attack_evidence()
        if evidence.sample_id in positive_ids
    )
    changed_results = tuple(
        apply_calibration(evidence, binding.calibration_bundle, 0.01)
        for evidence in attack_evidence(underpowered=True)
        if evidence.sample_id in positive_ids
    )
    summary = evaluate_pristine_baseline(results)
    verify_pristine_baseline_summary(results, summary)
    with pytest.raises(DetectorArtifactVerificationError, match="pristine baseline summary does not replay exactly"):
        verify_pristine_baseline_summary(changed_results, summary)
