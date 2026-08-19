from __future__ import annotations

import pytest

from fuckmark.corpus.schema import CorpusDomain, WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    INSUFFICIENT_CANDIDATES,
    MidDevCondition,
    MidDevPlanRow,
    SUCCESS,
)
from fuckmark.experiments.mid_dev_primary_inference_v2 import (
    primary_realized_cost_inference,
)
from fuckmark.experiments.mid_dev_scoring import MidDevScoredPlanRow
from fuckmark.hashing import sha256_text


def _plan_row(
    *,
    group_index: int,
    label: WatermarkLabel,
    condition: MidDevCondition,
    replicate: int,
    realized_cost: int,
) -> MidDevPlanRow:
    group_id = f"group-{group_index:03d}"
    sample_id = f"{group_id}-{label.value}"
    text = f"{sample_id}:{condition.value}:{replicate}:{realized_cost}"
    target_length = 128 if group_index < 18 else 256
    return MidDevPlanRow.create(
        source_group_id=group_id,
        prompt_id=f"prompt-{group_index:03d}",
        sample_id=sample_id,
        source_label=label,
        prompt_family_id="family",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        target_length=target_length,
        source_text_hash=sha256_text("source:" + sample_id),
        condition=condition,
        budget=4,
        replicate=replicate,
        transformed_text=text,
        operation_count=realized_cost,
        status=SUCCESS if realized_cost == 4 else INSUFFICIENT_CANDIDATES,
        selection_trace_hash=sha256_text("trace:" + text),
    )


def _scored(
    plan_row: MidDevPlanRow,
    *,
    drop: float,
) -> MidDevScoredPlanRow:
    threshold_name = f"threshold-{plan_row.target_length}"
    threshold_value = 0.5 if plan_row.target_length == 128 else 0.55
    return MidDevScoredPlanRow.create(
        plan_row=plan_row,
        detector_identity_hash=sha256_text("detector"),
        threshold_hash=sha256_text(threshold_name),
        threshold_value=threshold_value,
        pristine_score=0.8,
        transformed_score=0.8 - drop,
    )


def _rows(
    *,
    under_match_groups: int = 0,
) -> tuple[MidDevScoredPlanRow, ...]:
    output: list[MidDevScoredPlanRow] = []
    for group_index in range(36):
        for label in (WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED):
            deterministic_drop = 0.20 if label is WatermarkLabel.WATERMARKED else 0.03
            output.append(
                _scored(
                    _plan_row(
                        group_index=group_index,
                        label=label,
                        condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
                        replicate=0,
                        realized_cost=4,
                    ),
                    drop=deterministic_drop,
                )
            )
            for replicate in range(16):
                realized_cost = 4
                if group_index < under_match_groups and replicate >= 7:
                    realized_cost = 3
                if label is WatermarkLabel.WATERMARKED:
                    drop = 0.08 if replicate % 2 == 0 else 0.12
                else:
                    drop = 0.00 if replicate % 2 == 0 else 0.02
                output.append(
                    _scored(
                        _plan_row(
                            group_index=group_index,
                            label=label,
                            condition=MidDevCondition.RANDOM_SAFE,
                            replicate=replicate,
                            realized_cost=realized_cost,
                        ),
                        drop=drop,
                    )
                )
    return tuple(output)


def test_primary_v2_matches_random_by_realized_cost_before_source_inference() -> None:
    result = primary_realized_cost_inference(
        _rows(),
        deterministic_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=4,
        bootstrap_replicates=500,
        bootstrap_seed=37,
    )
    assert result.planned_source_group_count == 36
    assert result.eligible_source_group_count == 36
    assert result.excluded_source_group_ids == ()
    assert result.mean_watermarked_margin_advantage == pytest.approx(0.10)
    assert result.mean_control_margin_advantage == pytest.approx(0.02)
    assert result.mean_control_adjusted_margin_advantage == pytest.approx(0.08)
    assert result.bootstrap_lower == pytest.approx(0.08)
    assert result.bootstrap_upper == pytest.approx(0.08)
    assert all(value.realized_edit_cost == 4 for value in result.source_contrasts)
    assert all(value.watermarked_random_match_count == 16 for value in result.source_contrasts)
    assert all(value.control_random_match_count == 16 for value in result.source_contrasts)
    summaries = {value.target_length: value for value in result.length_summaries}
    assert set(summaries) == {128, 256}
    assert summaries[128].source_group_count == 18
    assert summaries[256].source_group_count == 18
    assert summaries[128].mean_control_adjusted_margin_advantage == pytest.approx(0.08)
    assert summaries[256].mean_control_adjusted_margin_advantage == pytest.approx(0.08)


def test_primary_v2_explicitly_excludes_source_with_fewer_than_eight_cost_matches() -> None:
    result = primary_realized_cost_inference(
        _rows(under_match_groups=1),
        deterministic_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=4,
        bootstrap_replicates=100,
        bootstrap_seed=41,
    )
    assert result.eligible_source_group_count == 35
    assert result.excluded_source_group_ids == ("group-000",)
    summaries = {value.target_length: value for value in result.length_summaries}
    assert summaries[128].source_group_count == 17
    assert summaries[256].source_group_count == 18


def test_primary_v2_rejects_when_cost_matching_leaves_fewer_than_32_sources() -> None:
    with pytest.raises(ValueError, match="fewer than 32"):
        primary_realized_cost_inference(
            _rows(under_match_groups=5),
            deterministic_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
            budget=4,
            bootstrap_replicates=100,
        )
