from __future__ import annotations

import pytest

from fuckmark.corpus.schema import CorpusDomain, WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
    MidDevPlanRow,
    MidDevScoredRow,
    SUCCESS,
)
from fuckmark.experiments.mid_dev_primary_inference import (
    primary_random_control_adjusted_comparison,
)
from fuckmark.hashing import sha256_text


def _plan_row(
    *,
    group_index: int,
    label: WatermarkLabel,
    condition: MidDevCondition,
    replicate: int,
) -> MidDevPlanRow:
    group_id = f"group-{group_index:03d}"
    sample_id = f"{group_id}-{label.value}"
    text = f"{sample_id}:{condition.value}:{replicate}"
    return MidDevPlanRow.create(
        source_group_id=group_id,
        prompt_id=f"prompt-{group_index:03d}",
        sample_id=sample_id,
        source_label=label,
        prompt_family_id="family",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        target_length=128,
        source_text_hash=sha256_text("source:" + sample_id),
        condition=condition,
        budget=4,
        replicate=replicate,
        transformed_text=text,
        operation_count=4,
        status=SUCCESS,
        selection_trace_hash=sha256_text("trace:" + text),
    )


def _scored(
    plan_row: MidDevPlanRow,
    *,
    drop: float,
    detector: str = "detector",
) -> MidDevScoredRow:
    return MidDevScoredRow.create(
        plan_row=plan_row,
        detector_identity_hash=sha256_text(detector),
        threshold_hash=sha256_text("threshold"),
        threshold_value=0.5,
        pristine_score=0.8,
        transformed_score=0.8 - drop,
    )


def _primary_rows(
    source_count: int = 32,
    *,
    drop_one_random_replicate: bool = False,
    mix_detector: bool = False,
) -> tuple[MidDevScoredRow, ...]:
    rows: list[MidDevScoredRow] = []
    for group_index in range(source_count):
        for label in (WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED):
            for replicate in range(MID_DEV_RANDOM_REPLICATES):
                if (
                    drop_one_random_replicate
                    and group_index == 0
                    and label is WatermarkLabel.WATERMARKED
                    and replicate == MID_DEV_RANDOM_REPLICATES - 1
                ):
                    continue
                if label is WatermarkLabel.WATERMARKED:
                    random_drop = 0.08 if replicate % 2 == 0 else 0.12
                else:
                    random_drop = 0.00 if replicate % 2 == 0 else 0.02
                rows.append(
                    _scored(
                        _plan_row(
                            group_index=group_index,
                            label=label,
                            condition=MidDevCondition.RANDOM_SAFE,
                            replicate=replicate,
                        ),
                        drop=random_drop,
                    )
                )
            deterministic_drop = (
                0.20 if label is WatermarkLabel.WATERMARKED else 0.03
            )
            detector = (
                "other-detector"
                if mix_detector
                and group_index == 0
                and label is WatermarkLabel.WATERMARKED
                else "detector"
            )
            rows.append(
                _scored(
                    _plan_row(
                        group_index=group_index,
                        label=label,
                        condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
                        replicate=0,
                    ),
                    drop=deterministic_drop,
                    detector=detector,
                )
            )
    return tuple(rows)


def test_primary_comparison_uses_16_random_replicates_then_bootstraps_sources() -> None:
    primary, core = primary_random_control_adjusted_comparison(
        _primary_rows(),
        comparison_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=4,
        bootstrap_replicates=500,
        bootstrap_seed=23,
    )
    assert primary.source_group_count == 32
    assert primary.random_replicates_per_source_label == 16
    assert core.mean_watermarked_difference == pytest.approx(0.10)
    assert core.mean_control_difference == pytest.approx(0.02)
    assert core.mean_control_adjusted_difference == pytest.approx(0.08)
    assert core.bootstrap_lower == pytest.approx(0.08)
    assert core.bootstrap_upper == pytest.approx(0.08)
    assert core.source_group_count == 32
    assert core.positive_adjusted_count == 32


def test_primary_comparison_rejects_incomplete_random_replicates() -> None:
    with pytest.raises(ValueError, match="sixteen random replicates"):
        primary_random_control_adjusted_comparison(
            _primary_rows(drop_one_random_replicate=True),
            comparison_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
            budget=4,
            bootstrap_replicates=50,
        )


def test_primary_comparison_rejects_detector_or_threshold_mixing() -> None:
    with pytest.raises(ValueError, match="cannot mix detector"):
        primary_random_control_adjusted_comparison(
            _primary_rows(mix_detector=True),
            comparison_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
            budget=4,
            bootstrap_replicates=50,
        )
