from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..scheduling.beam_v2 import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from ..search.visible_cost_budget import (
    RELAXED_VISIBLE_COST_POLICY,
    STRICT_VISIBLE_COST_POLICY,
    VisibleCostTier,
)
from .mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES
from .mid_dev_freeze import MidDevDeterministicFrozenPlan


MID_DEV_DEVELOPMENT_PLAN_VERSION = "mid-dev-development-plan-v5"
MID_DEV_NORMALIZED_COST_ROW_VERSION = "mid-dev-normalized-cost-row-v1"
MID_DEV_DEVELOPMENT_ROLE = "DEVELOPMENT_PILOT_ONLY"
MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION = "mid-dev-normalized-random-safe-v1"


class MidDevNormalizedPlanner(str, Enum):
    CONTEXT_SURVIVAL_BEAM_V2 = "CONTEXT_SURVIVAL_BEAM_V2"
    RANDOM_SAFE_MATCHED_COST = "RANDOM_SAFE_MATCHED_COST"


def _policy_for_tier(tier: VisibleCostTier):
    if tier is VisibleCostTier.STRICT:
        return STRICT_VISIBLE_COST_POLICY
    if tier is VisibleCostTier.RELAXED:
        return RELAXED_VISIBLE_COST_POLICY
    raise TypeError("unsupported visible-cost tier")


def _selection_algorithm(planner: MidDevNormalizedPlanner) -> str:
    if planner is MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2:
        return CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
    if planner is MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST:
        return MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION
    raise TypeError("unsupported normalized planner")


@dataclass(frozen=True, slots=True)
class MidDevNormalizedCostRow:
    source_group_id: str
    sample_id: str
    source_text_hash: str
    planner: MidDevNormalizedPlanner
    tier: VisibleCostTier
    replicate: int
    visible_cost_policy_hash: str
    candidate_registry_hash: str
    selection_algorithm_version: str
    maximum_search_operations: int
    realized_operation_count: int
    transformed_text: str
    transformed_text_hash: str
    final_search_state_hash: str
    search_result_hash: str
    selection_trace_hash: str
    residual_geometry_hash: str
    word_edit_rate: float
    character_edit_rate: float
    token_edit_distance: int
    length_ratio: float
    protected_span_violation_count: int
    hard_invariant_passed: bool
    normalized_cost_eligible: bool
    row_hash: str

    def __post_init__(self) -> None:
        for name in ("source_group_id", "sample_id", "selection_algorithm_version"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "source_text_hash",
            "visible_cost_policy_hash",
            "candidate_registry_hash",
            "transformed_text_hash",
            "final_search_state_hash",
            "search_result_hash",
            "selection_trace_hash",
            "residual_geometry_hash",
            "row_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.planner, MidDevNormalizedPlanner):
            raise TypeError("planner must be MidDevNormalizedPlanner")
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        for name in (
            "replicate",
            "maximum_search_operations",
            "realized_operation_count",
            "token_edit_distance",
            "protected_span_violation_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.realized_operation_count > self.maximum_search_operations:
            raise ValueError("realized_operation_count exceeds resource ceiling")
        if self.planner is MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2:
            if self.replicate != 0:
                raise ValueError("normalized Beam v2 rows require replicate=0")
        elif not 0 <= self.replicate < MID_DEV_RANDOM_REPLICATES:
            raise ValueError("normalized random-safe replicate is outside frozen range")
        if self.selection_algorithm_version != _selection_algorithm(self.planner):
            raise ValueError("selection_algorithm_version does not match normalized planner")
        policy = _policy_for_tier(self.tier)
        if self.visible_cost_policy_hash != policy.policy_hash:
            raise ValueError("visible_cost_policy_hash does not match tier")
        if not isinstance(self.transformed_text, str):
            raise TypeError("transformed_text must be a string")
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        for name in ("word_edit_rate", "character_edit_rate", "length_ratio"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if self.word_edit_rate > 1.0 or self.character_edit_rate > 1.0:
            raise ValueError("edit rates must be in [0, 1]")
        if self.length_ratio <= 0.0:
            raise ValueError("length_ratio must be positive")
        if type(self.hard_invariant_passed) is not bool or type(self.normalized_cost_eligible) is not bool:
            raise TypeError("invariant/eligibility flags must be bool")
        expected_eligible = (
            self.word_edit_rate <= policy.word_edit_rate_max
            and self.character_edit_rate <= policy.character_edit_rate_max
            and self.protected_span_violation_count == 0
            and self.hard_invariant_passed
            and (
                policy.length_ratio_min is None
                or policy.length_ratio_min <= self.length_ratio <= policy.length_ratio_max
            )
        )
        if self.normalized_cost_eligible != expected_eligible:
            raise ValueError("normalized_cost_eligible does not reproduce frozen tier policy")
        if not self.normalized_cost_eligible:
            raise ValueError("frozen normalized-cost plan rows must be eligible")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match normalized-cost row")

    @classmethod
    def create(
        cls,
        *,
        source_group_id: str,
        sample_id: str,
        source_text_hash: str,
        planner: MidDevNormalizedPlanner,
        tier: VisibleCostTier,
        replicate: int,
        candidate_registry_hash: str,
        maximum_search_operations: int,
        realized_operation_count: int,
        transformed_text: str,
        final_search_state_hash: str,
        search_result_hash: str,
        selection_trace_hash: str,
        residual_geometry_hash: str,
        word_edit_rate: float,
        character_edit_rate: float,
        token_edit_distance: int,
        length_ratio: float,
        protected_span_violation_count: int,
        hard_invariant_passed: bool,
    ) -> "MidDevNormalizedCostRow":
        policy = _policy_for_tier(tier)
        eligible = (
            word_edit_rate <= policy.word_edit_rate_max
            and character_edit_rate <= policy.character_edit_rate_max
            and protected_span_violation_count == 0
            and hard_invariant_passed
            and (
                policy.length_ratio_min is None
                or policy.length_ratio_min <= length_ratio <= policy.length_ratio_max
            )
        )
        values = {
            "source_group_id": source_group_id,
            "sample_id": sample_id,
            "source_text_hash": source_text_hash,
            "planner": planner,
            "tier": tier,
            "replicate": replicate,
            "visible_cost_policy_hash": policy.policy_hash,
            "candidate_registry_hash": candidate_registry_hash,
            "selection_algorithm_version": _selection_algorithm(planner),
            "maximum_search_operations": maximum_search_operations,
            "realized_operation_count": realized_operation_count,
            "transformed_text": transformed_text,
            "transformed_text_hash": sha256_text(transformed_text),
            "final_search_state_hash": final_search_state_hash,
            "search_result_hash": search_result_hash,
            "selection_trace_hash": selection_trace_hash,
            "residual_geometry_hash": residual_geometry_hash,
            "word_edit_rate": float(word_edit_rate),
            "character_edit_rate": float(character_edit_rate),
            "token_edit_distance": token_edit_distance,
            "length_ratio": float(length_ratio),
            "protected_span_violation_count": protected_span_violation_count,
            "hard_invariant_passed": hard_invariant_passed,
            "normalized_cost_eligible": eligible,
        }
        payload = {
            "algorithm_version": MID_DEV_NORMALIZED_COST_ROW_VERSION,
            **{
                key: (value.value if isinstance(value, Enum) else value)
                for key, value in values.items()
            },
        }
        return cls(**values, row_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_NORMALIZED_COST_ROW_VERSION,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_text_hash": self.source_text_hash,
            "planner": self.planner.value,
            "tier": self.tier.value,
            "replicate": self.replicate,
            "visible_cost_policy_hash": self.visible_cost_policy_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "selection_algorithm_version": self.selection_algorithm_version,
            "maximum_search_operations": self.maximum_search_operations,
            "realized_operation_count": self.realized_operation_count,
            "transformed_text": self.transformed_text,
            "transformed_text_hash": self.transformed_text_hash,
            "final_search_state_hash": self.final_search_state_hash,
            "search_result_hash": self.search_result_hash,
            "selection_trace_hash": self.selection_trace_hash,
            "residual_geometry_hash": self.residual_geometry_hash,
            "word_edit_rate": self.word_edit_rate,
            "character_edit_rate": self.character_edit_rate,
            "token_edit_distance": self.token_edit_distance,
            "length_ratio": self.length_ratio,
            "protected_span_violation_count": self.protected_span_violation_count,
            "hard_invariant_passed": self.hard_invariant_passed,
            "normalized_cost_eligible": self.normalized_cost_eligible,
        }


@dataclass(frozen=True, slots=True)
class MidDevDevelopmentPlanV5:
    algorithm_version: str
    role: str
    source_code_commit: str
    legacy_plan: MidDevDeterministicFrozenPlan
    legacy_plan_hash: str
    normalized_rows: tuple[MidDevNormalizedCostRow, ...]
    normalized_schema_hash: str
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_DEVELOPMENT_PLAN_VERSION:
            raise ValueError("unsupported MidDev v5 development plan version")
        if self.role != MID_DEV_DEVELOPMENT_ROLE:
            raise ValueError("MidDev v5 role must be DEVELOPMENT_PILOT_ONLY")
        if (
            not isinstance(self.source_code_commit, str)
            or len(self.source_code_commit) not in (40, 64)
            or any(ch not in "0123456789abcdef" for ch in self.source_code_commit)
        ):
            raise ValueError("source_code_commit must be a lowercase Git object ID")
        if not isinstance(self.legacy_plan, MidDevDeterministicFrozenPlan):
            raise TypeError("legacy_plan must be MidDevDeterministicFrozenPlan")
        require_sha256("legacy_plan_hash", self.legacy_plan_hash)
        if self.legacy_plan_hash != self.legacy_plan.plan_hash:
            raise ValueError("legacy_plan_hash does not bind legacy plan")
        if self.legacy_plan.source_code_commit != self.source_code_commit:
            raise ValueError("legacy plan and v5 container must bind the same source commit")
        if not isinstance(self.normalized_rows, tuple) or not self.normalized_rows:
            raise ValueError("v5 plan requires normalized-cost rows")
        if any(not isinstance(row, MidDevNormalizedCostRow) for row in self.normalized_rows):
            raise TypeError("normalized_rows must contain MidDevNormalizedCostRow values")
        keys = tuple((row.sample_id, row.planner.value, row.tier.value, row.replicate) for row in self.normalized_rows)
        if len(set(keys)) != len(keys):
            raise ValueError("normalized-cost row keys must be unique")
        legacy_bindings: dict[str, tuple[str, str]] = {}
        for row in self.legacy_plan.rows:
            binding = (row.source_group_id, row.source_text_hash)
            previous = legacy_bindings.setdefault(row.sample_id, binding)
            if previous != binding:
                raise ValueError("legacy plan contains inconsistent sample bindings")
        for row in self.normalized_rows:
            binding = legacy_bindings.get(row.sample_id)
            if binding is None:
                raise ValueError("normalized row sample is absent from legacy plan")
            if binding != (row.source_group_id, row.source_text_hash):
                raise ValueError("normalized row does not bind legacy sample identity")
        require_sha256("normalized_schema_hash", self.normalized_schema_hash)
        if self.normalized_schema_hash != self.schema_hash():
            raise ValueError("normalized_schema_hash does not reproduce")
        require_sha256("plan_hash", self.plan_hash)
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match MidDev v5 payload")

    @staticmethod
    def schema_hash() -> str:
        return sha256_json(
            {
                "algorithm_version": MID_DEV_DEVELOPMENT_PLAN_VERSION,
                "normalized_row_version": MID_DEV_NORMALIZED_COST_ROW_VERSION,
                "beam_algorithm_version": CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
                "strict_policy_hash": STRICT_VISIBLE_COST_POLICY.policy_hash,
                "relaxed_policy_hash": RELAXED_VISIBLE_COST_POLICY.policy_hash,
                "random_safe_algorithm_version": MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION,
            }
        )

    @classmethod
    def create(
        cls,
        *,
        source_code_commit: str,
        legacy_plan: MidDevDeterministicFrozenPlan,
        normalized_rows: tuple[MidDevNormalizedCostRow, ...],
    ) -> "MidDevDevelopmentPlanV5":
        normalized = tuple(
            sorted(
                normalized_rows,
                key=lambda row: (row.sample_id, row.planner.value, row.tier.value, row.replicate),
            )
        )
        schema_hash = cls.schema_hash()
        payload = {
            "algorithm_version": MID_DEV_DEVELOPMENT_PLAN_VERSION,
            "role": MID_DEV_DEVELOPMENT_ROLE,
            "source_code_commit": source_code_commit,
            "legacy_plan_hash": legacy_plan.plan_hash,
            "normalized_schema_hash": schema_hash,
            "normalized_row_hashes": tuple(row.row_hash for row in normalized),
        }
        return cls(
            algorithm_version=MID_DEV_DEVELOPMENT_PLAN_VERSION,
            role=MID_DEV_DEVELOPMENT_ROLE,
            source_code_commit=source_code_commit,
            legacy_plan=legacy_plan,
            legacy_plan_hash=legacy_plan.plan_hash,
            normalized_rows=normalized,
            normalized_schema_hash=schema_hash,
            plan_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "role": self.role,
            "source_code_commit": self.source_code_commit,
            "legacy_plan_hash": self.legacy_plan_hash,
            "normalized_schema_hash": self.normalized_schema_hash,
            "normalized_row_hashes": tuple(row.row_hash for row in self.normalized_rows),
        }
