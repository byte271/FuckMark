import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.e02_pristine import run_e02_pristine_detectability
from fuckmark.experiments.e08_dose import run_e08_dose_response
from fuckmark.experiments.mechanisms import E03RepetitionFixture, run_e03_repetition_fixture, run_observation_mechanism
from fuckmark.experiments.registry import DevelopmentExperimentId
from fuckmark.experiments.schedule_analysis import run_e09_random_baseline, run_e10_spacing_comparison, run_e11_greedy_comparison
from fuckmark.experiments.transform_analysis import run_e07_predictor_comparison
from fuckmark.experiments.verification import (
    ExperimentArtifactVerificationError,
    verify_development_calibration_binding,
    verify_e02_result,
    verify_e03_result,
    verify_e07_result,
    verify_e08_result,
    verify_e09_result,
    verify_e10_result,
    verify_e11_result,
    verify_observation_mechanism_result,
)
from test_e07_predictor_comparison import _rows as e07_rows
from test_e08_dose_response import _dose_rows
from test_e09_random_baseline import _complete_rows
from test_e10_spacing_comparison import _paired_rows as e10_rows
from test_e11_greedy_comparison import _paired_rows as e11_rows
from tiny_dev_experiment_helpers import attack_evidence, calibration_evidence, tiny_dev_artifact


def test_calibration_and_e02_verifiers_recompute_from_supplied_evidence() -> None:
    artifact = tiny_dev_artifact()
    calibration_rows = calibration_evidence()
    binding = calibrate_tiny_dev_detector(artifact, calibration_rows)
    verify_development_calibration_binding(artifact, calibration_rows, binding)
    changed_calibration = list(calibration_rows)
    first = changed_calibration[0]
    changed_calibration[0] = type(first)(
        sample_id=first.sample_id,
        detector_family=first.detector_family,
        detector_algorithm_version=first.detector_algorithm_version,
        detector_config_hash=first.detector_config_hash,
        observation_batch_hash=first.observation_batch_hash,
        detector_source_id=first.detector_source_id,
        detector_source_commit=first.detector_source_commit,
        adapter_id=first.adapter_id,
        adapter_algorithm_version=first.adapter_algorithm_version,
        adapter_config_hash=first.adapter_config_hash,
        source_id=first.source_id,
        source_commit=first.source_commit,
        direction=first.direction,
        total_observation_count=first.total_observation_count,
        valid_observation_count=first.valid_observation_count,
        depth=first.depth,
        raw_score=min(1.0, first.raw_score + 0.4),
        normalized_weights=first.normalized_weights,
        compatibility=first.compatibility,
    )
    with pytest.raises(ExperimentArtifactVerificationError, match="calibration binding"):
        verify_development_calibration_binding(artifact, tuple(changed_calibration), binding)
    pristine_rows = attack_evidence()
    result = run_e02_pristine_detectability(artifact, binding, pristine_rows)
    verify_e02_result(artifact, binding, pristine_rows, result)
    with pytest.raises(ExperimentArtifactVerificationError, match="E02 result"):
        verify_e02_result(artifact, binding, attack_evidence(underpowered=True), result)


def test_e03_and_observation_mechanism_verifiers_replay_exact_mechanisms() -> None:
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=4)
    )
    tokens = (10, 20, 30, 40, 20, 30, 50)
    fixture = E03RepetitionFixture.create(
        "verification-golden",
        adapter,
        tokens,
        (True, True, True, True, False),
    )
    result = run_e03_repetition_fixture(fixture, adapter)
    verify_e03_result(fixture, adapter, result)
    alternate = E03RepetitionFixture.create(
        "verification-alternate",
        adapter,
        tokens,
        (True, True, True, True, True),
    )
    with pytest.raises(ExperimentArtifactVerificationError, match="E03 result"):
        verify_e03_result(alternate, adapter, result)
    mechanism = run_observation_mechanism(
        DevelopmentExperimentId.E04,
        (10, 20, 30, 40, 50, 60),
        (10, 20, 99, 40, 50, 60),
        3,
    )
    verify_observation_mechanism_result(mechanism)


def test_e07_and_e08_verifiers_reject_valid_results_from_other_row_sets() -> None:
    artifact = tiny_dev_artifact()
    predictor_rows = e07_rows()
    predictor_result = run_e07_predictor_comparison(artifact, predictor_rows)
    verify_e07_result(artifact, predictor_rows, predictor_result)
    with pytest.raises(ExperimentArtifactVerificationError, match="E07 result"):
        verify_e07_result(artifact, _dose_rows(), predictor_result)
    dose_rows = _dose_rows()
    dose_result = run_e08_dose_response(artifact, dose_rows)
    verify_e08_result(artifact, dose_rows, dose_result)
    with pytest.raises(ExperimentArtifactVerificationError, match="E08 result"):
        verify_e08_result(artifact, _dose_rows(nonmonotonic=True), dose_result)


def test_e09_e10_e11_verifiers_bind_results_to_exact_schedule_rows() -> None:
    artifact = tiny_dev_artifact()
    random_rows = _complete_rows()
    random_result = run_e09_random_baseline(artifact, random_rows)
    verify_e09_result(artifact, random_rows, random_result)
    incomplete_random = tuple(
        row for row in random_rows if row.source_sample_id != random_rows[-1].source_sample_id
    )
    with pytest.raises(ExperimentArtifactVerificationError, match="E09 result"):
        verify_e09_result(artifact, incomplete_random, random_result)
    spacing_rows = e10_rows()
    spacing_result = run_e10_spacing_comparison(artifact, spacing_rows)
    verify_e10_result(artifact, spacing_rows, spacing_result)
    with pytest.raises(ExperimentArtifactVerificationError, match="E10 result"):
        verify_e10_result(artifact, e10_rows(unmatched_source_index=1), spacing_result)
    greedy_rows = e11_rows()
    greedy_result = run_e11_greedy_comparison(artifact, greedy_rows)
    verify_e11_result(artifact, greedy_rows, greedy_result)
    with pytest.raises(ExperimentArtifactVerificationError, match="E11 result"):
        verify_e11_result(artifact, e11_rows(secret_source_index=0), greedy_result)
