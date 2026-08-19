from __future__ import annotations

from .mid_dev_scored_schema import (
    MidDevScoredPlanRow as _SafeMidDevScoredPlanRow,
    MidDevScoringArtifact,
)
from .mid_dev_scoring_contracts import MidDevCondition, MidDevPlanRowView
from .mid_dev_scoring_safe import score_mid_dev_frozen_plan


class MidDevScoredPlanRow:
    @classmethod
    def create(
        cls,
        *,
        plan_row,
        detector_identity_hash: str,
        threshold_hash: str,
        threshold_value: float,
        pristine_score: float,
        transformed_score: float,
    ) -> _SafeMidDevScoredPlanRow:
        view = MidDevPlanRowView(
            plan_row.source_group_id,
            plan_row.prompt_id,
            plan_row.sample_id,
            plan_row.source_label,
            plan_row.prompt_family_id,
            plan_row.domain,
            plan_row.target_length,
            plan_row.source_text_hash,
            MidDevCondition(plan_row.condition.value),
            plan_row.budget,
            plan_row.replicate,
            plan_row.transformed_text,
            plan_row.transformed_text_hash,
            plan_row.operation_count,
            plan_row.status,
            plan_row.selection_trace_hash,
            plan_row.plan_row_hash,
        )
        return _SafeMidDevScoredPlanRow.create(
            plan_row=view,
            detector_identity_hash=detector_identity_hash,
            threshold_hash=threshold_hash,
            threshold_value=threshold_value,
            pristine_score=pristine_score,
            transformed_score=transformed_score,
        )


__all__ = (
    "MidDevScoredPlanRow",
    "MidDevScoringArtifact",
    "score_mid_dev_frozen_plan",
)
