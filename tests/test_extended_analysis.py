import pytest

from fuckmark.corpus import CorpusDomain, KeySplit, TARGET_LENGTHS
from fuckmark.detectors import DetectorFamily
from fuckmark.experiments.extended_analysis import (
    ExtendedAnalysisInputError,
    ExtendedAnalysisRow,
    run_e12_surface_battery,
    run_e13_contraction_battery,
    run_e14_length_scaling,
    run_e15_domain_transfer,
    run_e16_validation_key_transfer,
    run_e17_tokenizer_transfer,
    run_e18_detector_disagreement,
    run_e19_per_depth_drift,
    verify_extended_analysis_result,
)
from fuckmark.experiments.registry import DevelopmentExperimentId
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy
from schedule_experiment_helpers import attack_sources, schedule_row


def _row(
    *,
    variant: int = 0,
    key_split: KeySplit = KeySplit.DEV,
    key_id: str = "dev-key-0",
    model: str = "model-tokenizer-0",
    domain: CorpusDomain = CorpusDomain.GENERAL_EXPLANATORY,
    target_length: int = 64,
    rule_family: str = "surface",
    rule_id: str = "surface-space-v1",
    density: float = 0.1,
    detector_family: DetectorFamily = DetectorFamily.MEAN,
    fidelity_passed: bool = True,
    hard_invariant_passed: bool = True,
    pristine_depth_means: tuple[float, ...] = (0.8, 0.7, 0.6),
    transformed_depth_means: tuple[float, ...] = (0.7, 0.6, 0.5),
):
    base = schedule_row(
        attack_sources()[0],
        SchedulePolicy.RANDOM_VALID,
        variant=variant,
        key_split=key_split,
    )
    return ExtendedAnalysisRow.create(
        base,
        key_id=key_id,
        model_tokenizer_hash=sha256_text(model),
        domain=domain,
        target_length=target_length,
        rule_family=rule_family,
        rule_id=rule_id,
        realized_density=density,
        detector_family=detector_family,
        standardized_margin_drop=0.5 + variant * 0.01,
        token_edit_count=2,
        source_token_count=100,
        fidelity_passed=fidelity_passed,
        hard_invariant_passed=hard_invariant_passed,
        pristine_depth_means=pristine_depth_means,
        transformed_depth_means=transformed_depth_means,
    )


def test_e12_surface_battery_replays_and_rejects_invariant_failure() -> None:
    rows = (_row(variant=0), _row(variant=1, rule_id="surface-punctuation-v1"))
    result = run_e12_surface_battery(rows)
    assert result.experiment_id is DevelopmentExperimentId.E12
    assert len(result.strata) == 2
    verify_extended_analysis_result(result, rows)
    failed = (_row(variant=2, hard_invariant_passed=False),)
    with pytest.raises(ExtendedAnalysisInputError, match="hard-invariant"):
        run_e12_surface_battery(failed)


def test_e13_contraction_battery_preserves_fidelity_failures_in_rate() -> None:
    rows = (
        _row(variant=0, rule_family="contraction", rule_id="do-not", fidelity_passed=True),
        _row(variant=1, rule_family="contraction", rule_id="do-not", fidelity_passed=False),
    )
    result = run_e13_contraction_battery(rows)
    assert result.experiment_id is DevelopmentExperimentId.E13
    assert result.strata[0].fidelity_pass_rate == 0.5


def test_e14_requires_all_frozen_length_strata() -> None:
    rows = tuple(_row(variant=index, target_length=length) for index, length in enumerate(TARGET_LENGTHS))
    result = run_e14_length_scaling(rows)
    assert result.experiment_id is DevelopmentExperimentId.E14
    assert {stratum.stratum_key[0] for stratum in result.strata} == {str(value) for value in TARGET_LENGTHS}
    with pytest.raises(ExtendedAnalysisInputError, match="all frozen"):
        run_e14_length_scaling(rows[:-1])


def test_e15_requires_all_four_domains() -> None:
    rows = tuple(_row(variant=index, domain=domain) for index, domain in enumerate(CorpusDomain))
    result = run_e15_domain_transfer(rows)
    assert result.experiment_id is DevelopmentExperimentId.E15
    assert len(result.strata) == len(tuple(CorpusDomain))
    with pytest.raises(ExtendedAnalysisInputError, match="all four"):
        run_e15_domain_transfer(rows[:-1])


def test_e16_uses_validation_keys_and_never_test_keys_during_m6() -> None:
    rows = (
        _row(variant=0, key_split=KeySplit.VALIDATION, key_id="validation-key-0"),
        _row(variant=1, key_split=KeySplit.VALIDATION, key_id="validation-key-1"),
    )
    result = run_e16_validation_key_transfer(rows)
    assert result.experiment_id is DevelopmentExperimentId.E16
    with pytest.raises(ExtendedAnalysisInputError, match="TEST_KEYS remain sealed"):
        run_e16_validation_key_transfer((_row(variant=2, key_split=KeySplit.TEST, key_id="test-key-0"),))


def test_e17_requires_same_text_perturbation_across_two_model_tokenizer_families() -> None:
    base = schedule_row(attack_sources()[0], SchedulePolicy.RANDOM_VALID, variant=20)
    rows = tuple(
        ExtendedAnalysisRow.create(
            base,
            key_id="dev-key-0",
            model_tokenizer_hash=sha256_text(model),
            domain=CorpusDomain.GENERAL_EXPLANATORY,
            target_length=64,
            rule_family="surface",
            rule_id="surface-space-v1",
            realized_density=0.1,
            detector_family=DetectorFamily.MEAN,
            standardized_margin_drop=0.5,
            token_edit_count=2,
            source_token_count=100,
            fidelity_passed=True,
            hard_invariant_passed=True,
            pristine_depth_means=(0.8, 0.7, 0.6),
            transformed_depth_means=(0.7, 0.6, 0.5),
        )
        for model in ("model-tokenizer-a", "model-tokenizer-b")
    )
    result = run_e17_tokenizer_transfer(rows)
    assert result.experiment_id is DevelopmentExperimentId.E17
    with pytest.raises(ExtendedAnalysisInputError, match="at least two"):
        run_e17_tokenizer_transfer((rows[0],))


def test_e18_requires_all_three_detector_families_for_each_text_pair() -> None:
    base = schedule_row(attack_sources()[0], SchedulePolicy.RANDOM_VALID, variant=30)
    rows = tuple(
        ExtendedAnalysisRow.create(
            base,
            key_id="dev-key-0",
            model_tokenizer_hash=sha256_text("model-tokenizer-a"),
            domain=CorpusDomain.GENERAL_EXPLANATORY,
            target_length=64,
            rule_family="surface",
            rule_id="surface-space-v1",
            realized_density=0.1,
            detector_family=family,
            standardized_margin_drop=0.4,
            token_edit_count=2,
            source_token_count=100,
            fidelity_passed=True,
            hard_invariant_passed=True,
            pristine_depth_means=(0.8, 0.7, 0.6),
            transformed_depth_means=(0.7, 0.6, 0.5),
        )
        for family in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN, DetectorFamily.BAYESIAN)
    )
    result = run_e18_detector_disagreement(rows)
    assert result.experiment_id is DevelopmentExperimentId.E18
    with pytest.raises(ExtendedAnalysisInputError, match="Bayesian"):
        run_e18_detector_disagreement(rows[:-1])


def test_e19_reports_per_depth_means_and_covariance() -> None:
    rows = (
        _row(
            variant=40,
            pristine_depth_means=(0.9, 0.8, 0.7),
            transformed_depth_means=(0.7, 0.7, 0.6),
        ),
        _row(
            variant=41,
            pristine_depth_means=(0.8, 0.7, 0.6),
            transformed_depth_means=(0.7, 0.5, 0.4),
        ),
    )
    result = run_e19_per_depth_drift(rows)
    assert result.experiment_id is DevelopmentExperimentId.E19
    summary = result.strata[0]
    assert len(summary.mean_depth_drift) == 3
    assert len(summary.depth_covariance) == 3
    assert all(len(value) == 3 for value in summary.depth_covariance)
    verify_extended_analysis_result(result, rows)
