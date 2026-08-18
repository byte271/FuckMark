from __future__ import annotations

from collections import Counter

import pytest

from fuckmark.corpus.mid_dev import (
    MID_DEV_PROMPT_FAMILIES,
    MID_DEV_SOURCE_COUNT,
    MID_DEV_SOURCES_PER_FAMILY_LENGTH,
    MID_DEV_SOURCES_PER_LENGTH,
    MID_DEV_TARGET_LENGTHS,
    build_mid_dev_prompt_records,
    mid_dev_target_length_for_prompt,
)
from fuckmark.corpus.schema import WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    MID_DEV_CONDITIONS,
    MidDevCondition,
    MidDevFrozenPlan,
    MidDevPlanRow,
    MidDevScoredRow,
    source_grouped_comparison,
)
from fuckmark.hashing import sha256_text


def test_mid_dev_prompt_matrix_has_36_unique_independent_sources() -> None:
    prompts = build_mid_dev_prompt_records()
    assert len(prompts) == MID_DEV_SOURCE_COUNT == 36
    assert len({value.prompt_id for value in prompts}) == 36
    assert len({value.text_sha256 for value in prompts}) == 36
    length_counts = Counter(mid_dev_target_length_for_prompt(value.prompt_id) for value in prompts)
    assert length_counts == Counter({128: MID_DEV_SOURCES_PER_LENGTH, 256: MID_DEV_SOURCES_PER_LENGTH})
    cell_counts = Counter(
        (value.prompt_family_id, mid_dev_target_length_for_prompt(value.prompt_id))
        for value in prompts
    )
    for family in MID_DEV_PROMPT_FAMILIES:
        for target_length in MID_DEV_TARGET_LENGTHS:
            assert cell_counts[(family.family_id, target_length)] == MID_DEV_SOURCES_PER_FAMILY_LENGTH


def _plan_rows(source_count: int = 32) -> tuple[MidDevPlanRow, ...]:
    rows: list[MidDevPlanRow] = []
    for source_index in range(source_count):
        source_group_id = f"group-{source_index:03d}"
        for label in (WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED):
            sample_id = f"{source_group_id}-{label.value}"
            source_hash = sha256_text("source:" + sample_id)
            for condition in MID_DEV_CONDITIONS:
                output = f"output:{sample_id}:{condition.value}"
                rows.append(
                    MidDevPlanRow.create(
                        source_group_id=source_group_id,
                        sample_id=sample_id,
                        source_label=label,
                        source_text_hash=source_hash,
                        condition=condition,
                        transformed_text=output,
                        operation_count=0 if condition is MidDevCondition.NO_OP else 1,
                        selection_trace_hash=sha256_text("trace:" + output),
                    )
                )
    return tuple(rows)


def test_frozen_plan_requires_at_least_32_source_groups() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        MidDevFrozenPlan.create(
            corpus_artifact_hash=sha256_text("corpus"),
            source_profile_hash=sha256_text("profile"),
            selection_config_hash=sha256_text("selection"),
            rows=_plan_rows(31),
        )


def test_frozen_plan_requires_every_condition_for_every_sample() -> None:
    rows = list(_plan_rows(32))
    rows.pop()
    with pytest.raises(ValueError, match="every frozen condition"):
        MidDevFrozenPlan.create(
            corpus_artifact_hash=sha256_text("corpus"),
            source_profile_hash=sha256_text("profile"),
            selection_config_hash=sha256_text("selection"),
            rows=rows,
        )


def test_frozen_plan_is_detector_and_secret_blind() -> None:
    plan = MidDevFrozenPlan.create(
        corpus_artifact_hash=sha256_text("corpus"),
        source_profile_hash=sha256_text("profile"),
        selection_config_hash=sha256_text("selection"),
        rows=_plan_rows(32),
    )
    assert plan.detector_access_observed is False
    assert plan.secret_access_observed is False
    assert len(plan.rows) == 32 * 2 * len(MID_DEV_CONDITIONS)


def _scored_positive_rows(source_count: int = 32) -> tuple[MidDevScoredRow, ...]:
    rows: list[MidDevScoredRow] = []
    plan_rows = _plan_rows(source_count)
    for plan_row in plan_rows:
        if plan_row.source_label is not WatermarkLabel.WATERMARKED:
            continue
        baseline_drop = 0.10
        comparison_drop = 0.20
        if plan_row.condition is MidDevCondition.CONTEXT_GREEDY:
            drop = comparison_drop
        elif plan_row.condition is MidDevCondition.CURRENT_BASELINE:
            drop = baseline_drop
        else:
            drop = 0.05
        rows.append(
            MidDevScoredRow.create(
                plan_row=plan_row,
                detector_identity_hash=sha256_text("detector"),
                threshold_hash=sha256_text("threshold"),
                threshold_value=0.5,
                pristine_score=0.8,
                transformed_score=0.8 - drop,
            )
        )
    return tuple(rows)


def test_source_grouped_comparison_uses_independent_sources() -> None:
    result = source_grouped_comparison(
        _scored_positive_rows(32),
        comparison_condition=MidDevCondition.CONTEXT_GREEDY,
        bootstrap_replicates=500,
        bootstrap_seed=17,
    )
    assert result.source_group_count == 32
    assert result.mean_score_drop_difference == pytest.approx(0.1)
    assert result.bootstrap_lower == pytest.approx(0.1)
    assert result.bootstrap_upper == pytest.approx(0.1)
    assert result.positive_difference_count == 32
    assert result.negative_difference_count == 0
    assert result.zero_difference_count == 0
    assert result.two_sided_sign_p_value < 1e-8


def test_source_grouped_comparison_rejects_too_few_sources() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        source_grouped_comparison(
            _scored_positive_rows(31),
            comparison_condition=MidDevCondition.CONTEXT_GREEDY,
            bootstrap_replicates=100,
        )
