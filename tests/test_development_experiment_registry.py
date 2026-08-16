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


def test_registry_freezes_e02_through_e11_in_exact_order() -> None:
    registry = default_development_experiment_registry()
    assert registry.version == DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION
    assert tuple(definition.experiment_id for definition in registry.definitions) == tuple(DevelopmentExperimentId)
    assert len(registry.definitions) == 10


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


def test_e02_and_transform_outcome_experiments_require_frozen_calibration() -> None:
    registry = default_development_experiment_registry()
    for experiment_id in (
        DevelopmentExperimentId.E02,
        DevelopmentExperimentId.E07,
        DevelopmentExperimentId.E08,
        DevelopmentExperimentId.E09,
        DevelopmentExperimentId.E10,
        DevelopmentExperimentId.E11,
    ):
        assert registry.get(experiment_id).requires_calibration is True


def test_registry_hash_rejects_tampering() -> None:
    registry = default_development_experiment_registry()
    with pytest.raises(ValueError, match="registry_hash"):
        replace(registry, registry_hash="f" * 64)
