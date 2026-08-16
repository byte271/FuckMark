from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms import SchedulePolicy
from .confirmatory import ConfirmatoryPreregistration


E20_CONDITION_PLAN_ALGORITHM_VERSION = "e20-condition-plan-v2"


class E20ConditionPlanError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E20Condition:
    condition_id: str
    schedule_policy: SchedulePolicy
    budget: int
    budget_unit: str
    target_fpr: float
    calibration_bundle_hash: str
    hypothesis_class: str
    condition_hash: str

    def __post_init__(self) -> None:
        require_clean_string("condition_id", self.condition_id)
        if not isinstance(self.schedule_policy, SchedulePolicy):
            raise TypeError("schedule_policy must be a SchedulePolicy")
        require_int("budget", self.budget)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        require_clean_string("budget_unit", self.budget_unit)
        if isinstance(self.target_fpr, bool) or not isinstance(self.target_fpr, (int, float)):
            raise TypeError("target_fpr must be a real number")
        target = float(self.target_fpr)
        if not math.isfinite(target) or target <= 0.0 or target >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        require_sha256("calibration_bundle_hash", self.calibration_bundle_hash)
        require_clean_string("hypothesis_class", self.hypothesis_class)
        require_sha256("condition_hash", self.condition_hash)
        if self.condition_hash != sha256_json(self._payload()):
            raise ValueError("condition_hash does not match E20 condition")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_CONDITION_PLAN_ALGORITHM_VERSION,
            "condition_id": self.condition_id,
            "schedule_policy": self.schedule_policy.value,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "target_fpr": self.target_fpr,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "hypothesis_class": self.hypothesis_class,
        }

    @classmethod
    def create(
        cls,
        condition_id: str,
        schedule_policy: SchedulePolicy,
        budget: int,
        budget_unit: str,
        target_fpr: float,
        calibration_bundle_hash: str,
        hypothesis_class: str,
    ) -> E20Condition:
        payload = {
            "algorithm_version": E20_CONDITION_PLAN_ALGORITHM_VERSION,
            "condition_id": condition_id,
            "schedule_policy": schedule_policy.value if isinstance(schedule_policy, SchedulePolicy) else schedule_policy,
            "budget": budget,
            "budget_unit": budget_unit,
            "target_fpr": float(target_fpr),
            "calibration_bundle_hash": calibration_bundle_hash,
            "hypothesis_class": hypothesis_class,
        }
        return cls(
            condition_id,
            schedule_policy,
            budget,
            budget_unit,
            float(target_fpr),
            calibration_bundle_hash,
            hypothesis_class,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E20ConditionPlan:
    algorithm_version: str
    conditions: tuple[E20Condition, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_CONDITION_PLAN_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 condition plan algorithm version")
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise TypeError("conditions must be a non-empty tuple")
        if any(not isinstance(value, E20Condition) for value in self.conditions):
            raise TypeError("conditions must contain E20Condition values")
        expected = tuple(sorted(self.conditions, key=lambda value: (value.condition_id, value.condition_hash)))
        if self.conditions != expected:
            raise ValueError("E20 conditions must be canonically ordered")
        if len({value.condition_id for value in self.conditions}) != len(self.conditions):
            raise ValueError("E20 condition IDs must be unique")
        semantic_keys = tuple(
            (
                value.schedule_policy,
                value.budget,
                value.budget_unit,
                value.target_fpr,
                value.calibration_bundle_hash,
                value.hypothesis_class,
            )
            for value in self.conditions
        )
        if len(set(semantic_keys)) != len(semantic_keys):
            raise ValueError("E20 conditions must be unique by execution semantics")
        require_sha256("plan_hash", self.plan_hash)
        if self.plan_hash != sha256_json(self._payload()):
            raise ValueError("plan_hash does not match E20 condition plan")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "conditions": self.conditions,
        }

    def condition(self, condition_id: str) -> E20Condition:
        require_clean_string("condition_id", condition_id)
        for value in self.conditions:
            if value.condition_id == condition_id:
                return value
        raise KeyError(condition_id)


def build_e20_condition_plan(conditions: Sequence[E20Condition]) -> E20ConditionPlan:
    if not isinstance(conditions, Sequence) or isinstance(conditions, (str, bytes, bytearray)):
        raise TypeError("conditions must be a sequence")
    values = tuple(conditions)
    if not values:
        raise ValueError("conditions must not be empty")
    if any(not isinstance(value, E20Condition) for value in values):
        raise TypeError("conditions must contain E20Condition values")
    ordered = tuple(sorted(values, key=lambda value: (value.condition_id, value.condition_hash)))
    payload = {
        "algorithm_version": E20_CONDITION_PLAN_ALGORITHM_VERSION,
        "conditions": ordered,
    }
    return E20ConditionPlan(
        E20_CONDITION_PLAN_ALGORITHM_VERSION,
        ordered,
        sha256_json(payload),
    )


def verify_e20_condition_plan(
    plan: E20ConditionPlan,
    preregistration: ConfirmatoryPreregistration,
) -> None:
    if not isinstance(plan, E20ConditionPlan):
        raise TypeError("plan must be an E20ConditionPlan")
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if plan.plan_hash != preregistration.budget_config_hash:
        raise E20ConditionPlanError("E20 condition plan hash does not match preregistered budget_config_hash")
    allowed_schedules = set(preregistration.schedules)
    allowed_fprs = set(preregistration.target_fprs)
    allowed_hypotheses = {value.hypothesis_id for value in preregistration.hypotheses}
    bundles = {value.bundle_hash: value for value in preregistration.calibration_bundles}
    expected_execution_cells = {
        (schedule, target_fpr, bundle_hash)
        for schedule in allowed_schedules
        for target_fpr in allowed_fprs
        for bundle_hash, bundle in bundles.items()
        if any(threshold.target_fpr == target_fpr for threshold in bundle.thresholds)
    }
    actual_execution_cells: set[tuple[SchedulePolicy, float, str]] = set()
    for condition in plan.conditions:
        if condition.schedule_policy not in allowed_schedules:
            raise E20ConditionPlanError("E20 condition uses a schedule outside the preregistered schedule set")
        if condition.target_fpr not in allowed_fprs:
            raise E20ConditionPlanError("E20 condition uses a target FPR outside the preregistered target set")
        if condition.hypothesis_class not in allowed_hypotheses:
            raise E20ConditionPlanError("E20 condition uses an unknown preregistered hypothesis class")
        bundle = bundles.get(condition.calibration_bundle_hash)
        if bundle is None:
            raise E20ConditionPlanError("E20 condition uses a calibration bundle outside the preregistration")
        if not any(threshold.target_fpr == condition.target_fpr for threshold in bundle.thresholds):
            raise E20ConditionPlanError("E20 condition target FPR is not calibrated in its frozen detector bundle")
        execution_cell = (
            condition.schedule_policy,
            condition.target_fpr,
            condition.calibration_bundle_hash,
        )
        if execution_cell in actual_execution_cells:
            raise E20ConditionPlanError(
                "E20 condition plan contains more than one condition for the same schedule, target FPR, and detector calibration bundle"
            )
        actual_execution_cells.add(execution_cell)
    if actual_execution_cells != expected_execution_cells:
        raise E20ConditionPlanError(
            "E20 condition plan must exactly cover every preregistered schedule, target FPR, and calibrated detector bundle execution cell"
        )
