from dataclasses import replace

import pytest

from fuckmark.experiments.registry import (
    DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION,
    DevelopmentDataScope,
    DevelopmentExperimentId,
    TransformSelectionAccess,
    default_development_experiment_registry,
)
from fuckmark.transforms import SchedulePolicy


def test_registry_freezes_e02_through_e19_in_exact_order() -> None:
    registry = default_development_experiment_registry()
    assert registry.version == DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION
    assert tuple(definition.experiment_id for definition in registry.definitions) == tuple(DevelopmentExperimentId)
    assert len(registry.definitions) == 18


def test_mechanism_experiments_do_not_require_calibration_or_scheduler_access() -> None:
    registry = default_development_experiment_registry()
    for experiment_id in (
        DevelopmentExperimentId.E03,
        DevelopmentExperimentId.E04,
        DevelopmentExperimentId.E05,
        DevelopmentExperimentId.E06,
    ):
        definition = registry.get(experiment_id)
        assert definition.data_scope is DevelopmentDataScope.MECHANISM_FIXTURE
        assert definition.requires_calibration is False
        assert definition.selection_access is TransformSelectionAccess.NOT_APPLICABLE
        assert definition.scheduler_policies == ()


def test_e09_e10_e11_freeze_key_blind_scheduler_contracts() -> None:
    registry = default_development_experiment_registry()
    e09 = registry.get(DevelopmentExperimentId.E09)
    e10 = registry.get(DevelopmentExperimentId.E10)
    e11 = registry.get(DevelopmentExperimentId.E11)
    assert e09.selection_access is TransformSelectionAccess.KEY_BLIND
    assert e09.scheduler_policies == (SchedulePolicy.RANDOM_VALID,)
    assert e10.selection_access is TransformSelectionAccess.KEY_BLIND
    assert e10.scheduler_policies == (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING)
    assert e11.selection_access is TransformSelectionAccess.KEY_BLIND
    assert e11.scheduler_policies == (
        SchedulePolicy.RANDOM_VALID,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
    )
    assert DevelopmentExperimentId.E09 in e11.dependencies
    assert "g-value" in e11.failure_rule
    assert "detector-score" in e11.failure_rule


def test_detector_outcome_experiments_require_frozen_calibration() -> None:
    registry = default_development_experiment_registry()
    for experiment_id in (
        DevelopmentExperimentId.E02,
        DevelopmentExperimentId.E07,
        DevelopmentExperimentId.E08,
        DevelopmentExperimentId.E09,
        DevelopmentExperimentId.E10,
        DevelopmentExperimentId.E11,
        DevelopmentExperimentId.E14,
        DevelopmentExperimentId.E15,
        DevelopmentExperimentId.E16,
        DevelopmentExperimentId.E17,
        DevelopmentExperimentId.E18,
    ):
        assert registry.get(experiment_id).requires_calibration is True


def test_e12_through_e19_freeze_spec_objectives_and_failure_boundaries() -> None:
    registry = default_development_experiment_registry()
    e12 = registry.get(DevelopmentExperimentId.E12)
    e13 = registry.get(DevelopmentExperimentId.E13)
    e14 = registry.get(DevelopmentExperimentId.E14)
    e15 = registry.get(DevelopmentExperimentId.E15)
    e16 = registry.get(DevelopmentExperimentId.E16)
    e17 = registry.get(DevelopmentExperimentId.E17)
    e18 = registry.get(DevelopmentExperimentId.E18)
    e19 = registry.get(DevelopmentExperimentId.E19)
    assert "orthography" in e12.objective
    assert "semantic or code mutation" in e12.failure_rule
    assert "contraction and expansion" in e13.objective
    assert "Ambiguous morphology" in e13.failure_rule
    assert "64 through 1024" in e14.objective
    assert "Raw edit-count" in e14.failure_rule
    assert "four frozen domains" in e15.objective
    assert "domain-specific" in e15.failure_rule
    assert "key split not used for policy tuning" in e16.objective
    assert "TEST_KEYS" in e16.evidence_criterion
    assert "TEST_KEYS" in e16.failure_rule
    assert "tokenizer and model families" in e17.objective
    assert "universal" in e17.failure_rule
    assert "Mean, Weighted Mean, and Bayesian" in e18.objective
    assert "Mean-only" in e18.failure_rule
    assert "every g-value depth" in e19.objective
    assert "global mean alone" in e19.failure_rule


def test_e12_through_e17_preserve_key_blind_transform_boundary() -> None:
    registry = default_development_experiment_registry()
    for experiment_id in (
        DevelopmentExperimentId.E12,
        DevelopmentExperimentId.E13,
        DevelopmentExperimentId.E14,
        DevelopmentExperimentId.E15,
        DevelopmentExperimentId.E16,
        DevelopmentExperimentId.E17,
    ):
        assert registry.get(experiment_id).selection_access is TransformSelectionAccess.KEY_BLIND
    for experiment_id in (DevelopmentExperimentId.E18, DevelopmentExperimentId.E19):
        assert registry.get(experiment_id).selection_access is TransformSelectionAccess.NOT_APPLICABLE


def test_registry_hash_rejects_tampering() -> None:
    registry = default_development_experiment_registry()
    with pytest.raises(ValueError, match="registry_hash"):
        replace(registry, registry_hash="f" * 64)
