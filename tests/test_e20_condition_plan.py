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
from fuckmark.transforms import SchedulePolicy


def test_condition_plan_replays_preregistered_budget_config_hash() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    plan = confirmatory_condition_plan()
    assert plan.plan_hash == preregistration.budget_config_hash
    assert {value.schedule_policy for value in plan.conditions} == set(preregistration.schedules)
    assert {value.target_fpr for value in plan.conditions} == set(preregistration.target_fprs)
    verify_e20_condition_plan(plan, preregistration)


def test_condition_plan_rejects_opaque_hash_mismatch() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash="f" * 64)
    )
    with pytest.raises(E20ConditionPlanError, match="budget_config_hash"):
        verify_e20_condition_plan(confirmatory_condition_plan(), preregistration)


def test_condition_plan_rejects_missing_preregistered_schedule() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    full = confirmatory_condition_plan()
    reduced = build_e20_condition_plan(
        tuple(value for value in full.conditions if value.schedule_policy is not SchedulePolicy.EVEN_SPACING)
    )
    preregistration = create_confirmatory_preregistration(
        replace(inputs, budget_config_hash=reduced.plan_hash)
    )
    with pytest.raises(E20ConditionPlanError, match="every preregistered schedule"):
        verify_e20_condition_plan(reduced, preregistration)


def test_condition_plan_rejects_unknown_hypothesis_class_even_when_hash_matches() -> None:
    inputs = preregistration_inputs()
    full = confirmatory_condition_plan()
    bad = build_e20_condition_plan(
        tuple(
            E20Condition.create(
                value.condition_id,
                value.schedule_policy,
                value.budget,
                value.budget_unit,
                value.target_fpr,
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


def test_condition_plan_rejects_semantically_duplicate_condition_without_silent_dedup() -> None:
    condition = E20Condition.create(
        "first",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        "H13-primary",
    )
    duplicate = E20Condition.create(
        "second",
        SchedulePolicy.RANDOM_VALID,
        1,
        "operation",
        0.01,
        "H13-primary",
    )
    with pytest.raises(ValueError, match="unique by execution semantics"):
        build_e20_condition_plan((condition, duplicate))
