from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from ..search.visible_cost_budget import VisibleCostTier
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json, parse_mid_dev_plan_json
from .mid_dev_plan_v5 import (
    MidDevDevelopmentPlanV5,
    MidDevNormalizedCostRow,
    MidDevNormalizedPlanner,
)


def _normalized_row(value: object) -> MidDevNormalizedCostRow:
    data = _mapping(
        "normalized_row",
        value,
        (
            "source_group_id",
            "sample_id",
            "source_text_hash",
            "planner",
            "tier",
            "replicate",
            "visible_cost_policy_hash",
            "candidate_registry_hash",
            "selection_algorithm_version",
            "maximum_search_operations",
            "realized_operation_count",
            "transformed_text",
            "transformed_text_hash",
            "final_search_state_hash",
            "search_result_hash",
            "selection_trace_hash",
            "residual_geometry_hash",
            "word_edit_rate",
            "character_edit_rate",
            "token_edit_distance",
            "length_ratio",
            "protected_span_violation_count",
            "hard_invariant_passed",
            "normalized_cost_eligible",
            "row_hash",
        ),
    )
    return MidDevNormalizedCostRow(
        source_group_id=data["source_group_id"],
        sample_id=data["sample_id"],
        source_text_hash=data["source_text_hash"],
        planner=MidDevNormalizedPlanner(data["planner"]),
        tier=VisibleCostTier(data["tier"]),
        replicate=data["replicate"],
        visible_cost_policy_hash=data["visible_cost_policy_hash"],
        candidate_registry_hash=data["candidate_registry_hash"],
        selection_algorithm_version=data["selection_algorithm_version"],
        maximum_search_operations=data["maximum_search_operations"],
        realized_operation_count=data["realized_operation_count"],
        transformed_text=data["transformed_text"],
        transformed_text_hash=data["transformed_text_hash"],
        final_search_state_hash=data["final_search_state_hash"],
        search_result_hash=data["search_result_hash"],
        selection_trace_hash=data["selection_trace_hash"],
        residual_geometry_hash=data["residual_geometry_hash"],
        word_edit_rate=data["word_edit_rate"],
        character_edit_rate=data["character_edit_rate"],
        token_edit_distance=data["token_edit_distance"],
        length_ratio=data["length_ratio"],
        protected_span_violation_count=data["protected_span_violation_count"],
        hard_invariant_passed=data["hard_invariant_passed"],
        normalized_cost_eligible=data["normalized_cost_eligible"],
        row_hash=data["row_hash"],
    )


def parse_mid_dev_development_plan_v5_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevDevelopmentPlanV5:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_development_plan_v5",
            decoded,
            (
                "algorithm_version",
                "role",
                "source_code_commit",
                "legacy_plan",
                "legacy_plan_hash",
                "normalized_rows",
                "normalized_schema_hash",
                "plan_hash",
            ),
        )
        legacy = parse_mid_dev_plan_json(
            canonical_json_text(data["legacy_plan"]),
            require_canonical=True,
        )
        plan = MidDevDevelopmentPlanV5(
            algorithm_version=data["algorithm_version"],
            role=data["role"],
            source_code_commit=data["source_code_commit"],
            legacy_plan=legacy,
            legacy_plan_hash=data["legacy_plan_hash"],
            normalized_rows=tuple(
                _normalized_row(row)
                for row in _array("normalized_rows", data["normalized_rows"])
            ),
            normalized_schema_hash=data["normalized_schema_hash"],
            plan_hash=data["plan_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev v5 development plan failed validation") from error
    if require_canonical and text not in (
        canonical_json_text(plan),
        canonical_json_text(plan) + "\n",
    ):
        raise MidDevPlanJsonError("MidDev v5 development plan JSON is not canonical")
    return plan


def load_mid_dev_development_plan_v5_json(path: str | Path) -> MidDevDevelopmentPlanV5:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("MidDev v5 development plan JSON exceeds the size limit")
    return parse_mid_dev_development_plan_v5_json(file_path.read_text(encoding="utf-8"))
