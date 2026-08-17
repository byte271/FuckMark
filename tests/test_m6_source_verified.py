from dataclasses import replace
from functools import lru_cache

import pytest

from test_e07_predictor_comparison import _rows as e07_rows
from test_e08_dose_response import _dose_rows
from test_e09_random_baseline import _complete_rows
from test_e10_spacing_comparison import _paired_rows as e10_rows
from test_e11_greedy_comparison import _paired_rows as e11_rows
from test_extended_analysis import _row
from test_power_analysis import _input as power_input
from tiny_dev_experiment_helpers import tiny_dev_artifact
from schedule_experiment_helpers import attack_sources, schedule_row

from fuckmark.corpus import CorpusDomain, KeySplit, TARGET_LENGTHS
from fuckmark.detectors import DetectorFamily
from fuckmark.experiments.e08_dose import run_e08_dose_response
from fuckmark.experiments.extended_analysis import (
    ExtendedAnalysisRow,
    run_e12_surface_battery,
    run_e13_contraction_battery,
    run_e14_length_scaling,
    run_e15_domain_transfer,
    run_e16_validation_key_transfer,
    run_e17_tokenizer_transfer,
    run_e18_detector_disagreement,
    run_e19_per_depth_drift,
)
from fuckmark.experiments.m6_readiness import M6EvidencePartition, M6ExperimentEvidence, M6ReadinessStatus
from fuckmark.experiments.m6_source_verified import (
    M6ExperimentReplayInput,
    build_source_verified_m6_readiness,
    verify_source_verified_m6_readiness,
)
from fuckmark.experiments.power_analysis import run_power_analysis
from fuckmark.experiments.registry import DevelopmentExperimentId, default_development_experiment_registry
from fuckmark.experiments.schedule_analysis import run_e09_random_baseline, run_e10_spacing_comparison, run_e11_greedy_comparison
from fuckmark.experiments.transform_analysis import run_e07_predictor_comparison
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy


def _extended_row_from_base(base, *, model, detector_family=DetectorFamily.MEAN):
    return ExtendedAnalysisRow.create(
        base,
        key_id="dev-key-0",
        model_tokenizer_hash=sha256_text(model),
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        target_length=64,
        rule_family="surface",
        rule_id="surface-space-v1",
        realized_density=0.1,
        detector_family=detector_family,
        standardized_margin_drop=0.5,
        token_edit_count=2,
        source_token_count=100,
        fidelity_passed=True,
        hard_invariant_passed=True,
        pristine_depth_means=(0.8, 0.7, 0.6),
        transformed_depth_means=(0.7, 0.6, 0.5),
    )


@lru_cache(maxsize=1)
def _complete_inputs():
    artifact = tiny_dev_artifact()

    rows07 = e07_rows()
    rows08 = _dose_rows()
    rows09 = _complete_rows()
    rows10 = e10_rows()
    rows11 = e11_rows()

    inputs = [
        M6ExperimentReplayInput(run_e07_predictor_comparison(artifact, rows07), rows07, artifact),
        M6ExperimentReplayInput(run_e08_dose_response(artifact, rows08), rows08, artifact),
        M6ExperimentReplayInput(run_e09_random_baseline(artifact, rows09), rows09, artifact),
        M6ExperimentReplayInput(run_e10_spacing_comparison(artifact, rows10), rows10, artifact),
        M6ExperimentReplayInput(run_e11_greedy_comparison(artifact, rows11), rows11, artifact),
    ]

    rows12 = (_row(variant=0), _row(variant=1, rule_id="surface-punctuation-v1"))
    rows13 = (
        _row(variant=2, rule_family="contraction", rule_id="do-not", fidelity_passed=True),
        _row(variant=3, rule_family="contraction", rule_id="do-not", fidelity_passed=False),
    )
    rows14 = tuple(_row(variant=10 + index, target_length=length) for index, length in enumerate(TARGET_LENGTHS))
    rows15 = tuple(_row(variant=20 + index, domain=domain) for index, domain in enumerate(CorpusDomain))
    rows16 = (
        _row(variant=30, key_split=KeySplit.VALIDATION, key_id="validation-key-0"),
        _row(variant=31, key_split=KeySplit.VALIDATION, key_id="validation-key-1"),
    )

    base17 = schedule_row(attack_sources()[0], SchedulePolicy.RANDOM_VALID, variant=40)
    rows17 = (
        _extended_row_from_base(base17, model="model-tokenizer-a"),
        _extended_row_from_base(base17, model="model-tokenizer-b"),
    )

    base18 = schedule_row(attack_sources()[0], SchedulePolicy.RANDOM_VALID, variant=50)
    rows18 = tuple(
        _extended_row_from_base(base18, model="model-tokenizer-a", detector_family=family)
        for family in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN, DetectorFamily.BAYESIAN)
    )

    rows19 = (
        _row(variant=60, pristine_depth_means=(0.9, 0.8, 0.7), transformed_depth_means=(0.7, 0.7, 0.6)),
        _row(variant=61, pristine_depth_means=(0.8, 0.7, 0.6), transformed_depth_means=(0.7, 0.5, 0.4)),
    )

    inputs.extend(
        (
            M6ExperimentReplayInput(run_e12_surface_battery(rows12), rows12),
            M6ExperimentReplayInput(run_e13_contraction_battery(rows13), rows13),
            M6ExperimentReplayInput(run_e14_length_scaling(rows14), rows14),
            M6ExperimentReplayInput(run_e15_domain_transfer(rows15), rows15),
            M6ExperimentReplayInput(run_e16_validation_key_transfer(rows16), rows16),
            M6ExperimentReplayInput(run_e17_tokenizer_transfer(rows17), rows17),
            M6ExperimentReplayInput(run_e18_detector_disagreement(rows18), rows18),
            M6ExperimentReplayInput(run_e19_per_depth_drift(rows19), rows19),
        )
    )

    power = power_input((1.0, 0.9, 1.1, 0.8, 1.2))
    power_result = run_power_analysis(power)
    return tuple(inputs), power, power_result


def test_source_verified_m6_replays_all_e07_through_e19_before_ready() -> None:
    registry = default_development_experiment_registry()
    experiments, power, power_result = _complete_inputs()
    bundle = build_source_verified_m6_readiness(registry, experiments, power, power_result)

    assert bundle.readiness.status is M6ReadinessStatus.READY
    assert bundle.readiness.ready_for_m7
    assert tuple(value.experiment_id for value in bundle.experiments) == tuple(DevelopmentExperimentId)[5:18]
    assert bundle.experiments[9].experiment_id is DevelopmentExperimentId.E16
    assert bundle.experiments[9].partition is M6EvidencePartition.VALIDATION
    assert all(
        value.partition is M6EvidencePartition.DEV
        for value in bundle.experiments
        if value.experiment_id is not DevelopmentExperimentId.E16
    )
    assert all(value.readiness_evidence.artifact_hash == value.result_hash for value in bundle.experiments)
    verify_source_verified_m6_readiness(bundle, registry, experiments, power, power_result)


def test_source_verified_m6_rejects_missing_experiment_instead_of_structural_ready_hashes() -> None:
    registry = default_development_experiment_registry()
    experiments, power, power_result = _complete_inputs()
    with pytest.raises(ValueError, match="complete E07-E19"):
        build_source_verified_m6_readiness(registry, experiments[:-1], power, power_result)

    arbitrary = M6ExperimentEvidence.create(
        DevelopmentExperimentId.E07,
        registry.get(DevelopmentExperimentId.E07).definition_hash,
        M6EvidencePartition.DEV,
        sha256_text("arbitrary-unverified-artifact"),
    )
    with pytest.raises(TypeError, match="E07 through E19 development result"):
        M6ExperimentReplayInput(arbitrary, e07_rows(), tiny_dev_artifact())


def test_source_verified_m6_rejects_result_replayed_against_different_rows() -> None:
    registry = default_development_experiment_registry()
    experiments, power, power_result = _complete_inputs()
    first = experiments[0]
    mismatched = replace(first, rows=_dose_rows())
    with pytest.raises(ValueError):
        build_source_verified_m6_readiness(registry, (mismatched, *experiments[1:]), power, power_result)


def test_source_verified_m6_rejects_test_key_rows_even_when_analysis_result_is_self_consistent() -> None:
    registry = default_development_experiment_registry()
    experiments, power, power_result = _complete_inputs()
    test_rows = (
        _row(variant=70, key_split=KeySplit.TEST, key_id="test-key-0"),
        _row(variant=71, key_split=KeySplit.TEST, key_id="test-key-1", rule_id="surface-punctuation-v1"),
    )
    self_consistent_result = run_e12_surface_battery(test_rows)
    replacement = M6ExperimentReplayInput(self_consistent_result, test_rows)
    replaced = tuple(replacement if value.result is experiments[5].result else value for value in experiments)
    with pytest.raises(ValueError, match="TEST_KEYS"):
        build_source_verified_m6_readiness(registry, replaced, power, power_result)


def test_source_verified_m6_rejects_power_result_from_different_validation_input() -> None:
    registry = default_development_experiment_registry()
    experiments, power, _ = _complete_inputs()
    other_power = power_input((0.0, 0.0, 0.0, 0.0))
    other_result = run_power_analysis(other_power)
    with pytest.raises(ValueError):
        build_source_verified_m6_readiness(registry, experiments, power, other_result)
