from dataclasses import replace

import pytest

from confirmatory_helpers import confirmatory_condition_plan, preregistration_inputs
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e20_conditions import (
    E20Condition,
    E20ConditionPlanError,
    build_e20_condition_plan,
    verify_e20_condition_plan,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy


def test_condition_plan_replays_preregistered_budget_config_hash() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    plan = confirmatory_condition_plan()
    assert plan.plan_hash == preregistration.budget_config_hash
    assert {value.schedule_policy for value in plan.conditions} == set(preregistration.schedules)
    assert {value.target_fpr for value in plan.conditions} == set(preregistration.target_fprs)
    assert {value.calibration_bundle_hash for value in plan.conditions} == {
        value.bundle_hash for value in preregistration.calibration_bundles
    }
    assert len(plan.conditions) == (
        len(preregistration.schedules)
        * len(preregistration.target_fprs)
        * len(preregistration.calibration_bundles)
    )
    assert len(plan.transform_condition_ids) == len(preregistration.schedules)
    for schedule in preregistration.schedules:
        ids = {
            value.transform_condition_id
            for value in plan.conditions
            if value.schedule_policy is schedule
        }
        assert len(ids) == 1
    verify_e20_condition_plan(plan, preregistration)


def test_condition_plan_rejects_opaque_hash_mismatch() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash="f" * 64)
    )
    with pytest.raises(E20ConditionPlanError, match="budget_config_hash"):
        verify_e20_condition_plan(confirmatory_condition_plan(), preregistration)


def test_condition_plan_rejects_missing_preregistered_schedule_bundle_cell() -> None:
    inputs = preregistration_inputs()
    full = confirmatory_condition_plan()
    reduced = build_e20_condition_plan(
        tuple(value for value in full.conditions if value.schedule_policy is not SchedulePolicy.EVEN_SPACING)
    )
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash=reduced.plan_hash)
    )
    with pytest.raises(E20ConditionPlanError, match="exactly cover"):
        verify_e20_condition_plan(reduced, preregistration)


def test_condition_plan_rejects_unknown_hypothesis_class_even_when_hash_matches() -> None:
    inputs = preregistration_inputs()
    full = confirmatory_condition_plan()
    bad = build_e20_condition_plan(
        tuple(
            E20Condition.create(
                value.condition_id,
                value.transform_condition_id,
                value.schedule_policy,
                value.budget,
                value.budget_unit,
                value.target_fpr,
                value.calibration_bundle_hash,
                "not-preregistered",
            )
            for value in full.conditions
        )
    )
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash=bad.plan_hash)
    )
    with pytest.raises(E20ConditionPlanError, match="unknown preregistered hypothesis"):
        verify_e20_condition_plan(bad, preregistration)


def test_condition_plan_rejects_unknown_calibration_bundle_even_when_hash_matches() -> None:
    inputs = preregistration_inputs()
    full = confirmatory_condition_plan()
    first = full.conditions[0]
    bad_first = E20Condition.create(
        first.condition_id,
        first.transform_condition_id,
        first.schedule_policy,
        first.budget,
        first.budget_unit,
        first.target_fpr,
        sha256_text("not-a-preregistered-calibration-bundle"),
        first.hypothesis_class,
    )
    bad = build_e20_condition_plan((bad_first, *full.conditions[1:]))
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash=bad.plan_hash)
    )
    with pytest.raises(E20ConditionPlanError, match="calibration bundle outside"):
        verify_e20_condition_plan(bad, preregistration)


def test_condition_plan_rejects_semantically_duplicate_condition_without_silent_dedup() -> None:
    bundle_hash = preregistration_inputs().calibration_bundles[0].bundle_hash
    condition = E20Condition.create(
        "first",
        "random-valid-budget-1",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        bundle_hash,
        "H13-primary",
    )
    duplicate = E20Condition.create(
        "second",
        "random-valid-budget-1",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        bundle_hash,
        "H13-primary",
    )
    with pytest.raises(ValueError, match="unique by execution semantics"):
        build_e20_condition_plan((condition, duplicate))


def test_condition_plan_rejects_different_transform_ids_for_same_schedule_budget() -> None:
    bundle_hashes = tuple(value.bundle_hash for value in preregistration_inputs().calibration_bundles)
    first = E20Condition.create(
        "first",
        "transform-a",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        bundle_hashes[0],
        "H13-primary",
    )
    second = E20Condition.create(
        "second",
        "transform-b",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        bundle_hashes[1],
        "H13-primary",
    )
    with pytest.raises(ValueError, match="must reuse one transform_condition_id"):
        build_e20_condition_plan((first, second))
