import pytest

from fuckmark.experiments.power_analysis import (
    POWER_ANALYSIS_ALGORITHM_VERSION,
    PowerAnalysisDirection,
    PowerAnalysisInput,
    PowerAnalysisStatus,
    m6_power_evidence_from_result,
    run_power_analysis,
    verify_power_analysis,
)


def _input(effects, desired_power=0.8):
    return PowerAnalysisInput.create(
        metric_id="standardized_detector_margin_drop",
        stratum_id="validation-core-cell",
        validation_effects=tuple(effects),
        candidate_sample_counts=(8, 16, 32),
        desired_power=desired_power,
        confidence_level=0.95,
        direction=PowerAnalysisDirection.POSITIVE,
        simulation_replicates=20,
        bootstrap_replicates=40,
        seed=271828,
    )


def test_power_analysis_is_deterministic_and_selects_smallest_passing_n() -> None:
    value = _input((1.0, 0.9, 1.1, 0.8, 1.2))
    first = run_power_analysis(value)
    second = run_power_analysis(value)
    assert first == second
    assert first.status is PowerAnalysisStatus.RESOLVED
    assert first.selected_sample_count == 8
    assert first.estimates[0].estimated_power == 1.0
    verify_power_analysis(first, value)


def test_zero_effect_validation_data_remains_unresolved() -> None:
    value = _input((0.0, 0.0, 0.0, 0.0))
    result = run_power_analysis(value)
    assert result.status is PowerAnalysisStatus.UNRESOLVED
    assert result.selected_sample_count is None
    assert all(estimate.estimated_power == 0.0 for estimate in result.estimates)
    with pytest.raises(ValueError, match="resolved"):
        m6_power_evidence_from_result(result)


def test_resolved_power_analysis_becomes_m6_power_evidence_without_retyping_n() -> None:
    result = run_power_analysis(_input((0.7, 0.8, 0.9, 1.0)))
    evidence = m6_power_evidence_from_result(result)
    assert evidence.method_id == POWER_ANALYSIS_ALGORITHM_VERSION
    assert evidence.validation_input_hash == result.input_hash
    assert evidence.analysis_artifact_hash == result.result_hash
    assert evidence.final_n_per_core_cell == result.selected_sample_count


def test_power_analysis_rejects_unsorted_candidate_sample_counts() -> None:
    with pytest.raises(ValueError, match="unique and increasing"):
        PowerAnalysisInput.create(
            metric_id="metric",
            stratum_id="stratum",
            validation_effects=(0.1, 0.2),
            candidate_sample_counts=(32, 16),
            desired_power=0.8,
            confidence_level=0.95,
            direction=PowerAnalysisDirection.TWO_SIDED,
            simulation_replicates=5,
            bootstrap_replicates=5,
            seed=1,
        )
