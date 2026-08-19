from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from fuckmark.corpus.mid_dev import (
    MID_DEV_PROMPT_FAMILIES,
    MID_DEV_SEED_BASE,
    MID_DEV_SOURCE_COUNT,
    MID_DEV_SOURCES_PER_FAMILY_LENGTH,
    MID_DEV_TARGET_LENGTHS,
    MidDevAnalysisSplit,
    build_mid_dev_analysis_split,
    build_mid_dev_prompt_records,
    mid_dev_seed_for_prompt,
    mid_dev_target_length_for_prompt,
)
from fuckmark.corpus.schema import CorpusDomain, WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    MID_DEV_BUDGETS,
    MID_DEV_ECS1_PREDICTOR_VERSION,
    MID_DEV_RANDOM_REPLICATES,
    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    MidDevComputeRow,
    MidDevCondition,
    MidDevFrozenPlan,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevScoredRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
    SUCCESS,
    build_ecs1_predictor_rows,
    source_grouped_control_adjusted_comparison,
)
from fuckmark.hashing import sha256_text


def test_mid_dev_prompt_matrix_has_36_balanced_sources_and_unique_frozen_seeds() -> None:
    prompts = build_mid_dev_prompt_records()
    assert len(prompts) == MID_DEV_SOURCE_COUNT == 36
    assert len({value.prompt_id for value in prompts}) == 36
    assert len({value.text_sha256 for value in prompts}) == 36

    seeds = tuple(mid_dev_seed_for_prompt(value.prompt_id) for value in prompts)
    assert len(set(seeds)) == 36
    assert min(seeds) == MID_DEV_SEED_BASE
    assert max(seeds) == MID_DEV_SEED_BASE + 35

    length_counts = Counter(mid_dev_target_length_for_prompt(value.prompt_id) for value in prompts)
    assert length_counts == Counter({128: 18, 256: 18})
    cell_counts = Counter(
        (value.prompt_family_id, mid_dev_target_length_for_prompt(value.prompt_id))
        for value in prompts
    )
    for family in MID_DEV_PROMPT_FAMILIES:
        for target_length in MID_DEV_TARGET_LENGTHS:
            assert cell_counts[(family.family_id, target_length)] == MID_DEV_SOURCES_PER_FAMILY_LENGTH


def test_mid_dev_grouped_holdout_is_24_12_and_stratified_by_family_length() -> None:
    prompts = build_mid_dev_prompt_records()
    split = build_mid_dev_analysis_split(prompts)
    assert Counter(split.values()) == Counter(
        {
            MidDevAnalysisSplit.FIT: 24,
            MidDevAnalysisSplit.EVALUATION: 12,
        }
    )

    by_cell: dict[tuple[str, int], Counter[MidDevAnalysisSplit]] = {}
    for prompt in prompts:
        cell = (prompt.prompt_family_id, mid_dev_target_length_for_prompt(prompt.prompt_id))
        by_cell.setdefault(cell, Counter())[split[prompt.prompt_id]] += 1
    for counts in by_cell.values():
        assert counts == Counter(
            {
                MidDevAnalysisSplit.FIT: 2,
                MidDevAnalysisSplit.EVALUATION: 1,
            }
        )

    assert split == build_mid_dev_analysis_split(tuple(reversed(prompts)))


def test_frozen_selection_config_binds_beam_v2_and_16_random_replicates() -> None:
    config = MidDevSelectionConfig.frozen()
    assert config.budgets == MID_DEV_BUDGETS
    assert config.random_replicates == MID_DEV_RANDOM_REPLICATES == 16
    assert config.beam_algorithm_version == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


def test_selection_attestation_fails_closed_on_detector_or_secret_observation() -> None:
    clean = MidDevSelectionAttestation.from_observed(
        attested_expander_count=72,
        detector_access_observed=False,
        secret_access_observed=False,
        detector_query_count=0,
        secret_query_count=0,
    )
    assert clean.attested_expander_count == 72

    with pytest.raises(ValueError, match="contaminated"):
        MidDevSelectionAttestation.from_observed(
            attested_expander_count=72,
            detector_access_observed=True,
            secret_access_observed=False,
            detector_query_count=0,
            secret_query_count=0,
        )
    with pytest.raises(ValueError, match="contaminated"):
        MidDevSelectionAttestation.from_observed(
            attested_expander_count=72,
            detector_access_observed=False,
            secret_access_observed=False,
            detector_query_count=1,
            secret_query_count=0,
        )


def _row(
    *,
    group_index: int,
    label: WatermarkLabel,
    condition: MidDevCondition,
    budget: int,
    replicate: int = 0,
) -> MidDevPlanRow:
    group_id = f"group-{group_index:03d}"
    sample_id = f"{group_id}-{label.value}"
    if condition is MidDevCondition.NO_OP:
        operation_count = 0
    else:
        operation_count = budget
    output = f"text:{sample_id}:{condition.value}:{budget}:{replicate}"
    return MidDevPlanRow.create(
        source_group_id=group_id,
        prompt_id=f"prompt-{group_index:03d}",
        sample_id=sample_id,
        source_label=label,
        prompt_family_id="family",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        target_length=128 if group_index % 2 == 0 else 256,
        source_text_hash=sha256_text("source:" + sample_id),
        condition=condition,
        budget=budget,
        replicate=replicate,
        transformed_text=output,
        operation_count=operation_count,
        status=SUCCESS,
        selection_trace_hash=sha256_text("trace:" + output),
    )


def _complete_plan_rows(source_count: int = 32) -> tuple[MidDevPlanRow, ...]:
    rows: list[MidDevPlanRow] = []
    for group_index in range(source_count):
        for label in (WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED):
            rows.append(
                _row(
                    group_index=group_index,
                    label=label,
                    condition=MidDevCondition.NO_OP,
                    budget=0,
                )
            )
            for budget in MID_DEV_BUDGETS:
                for condition in (
                    MidDevCondition.CURRENT_STRONGEST_BASELINE,
                    MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
                    MidDevCondition.EVEN_SPACING,
                ):
                    rows.append(
                        _row(
                            group_index=group_index,
                            label=label,
                            condition=condition,
                            budget=budget,
                        )
                    )
                for replicate in range(MID_DEV_RANDOM_REPLICATES):
                    rows.append(
                        _row(
                            group_index=group_index,
                            label=label,
                            condition=MidDevCondition.RANDOM_SAFE,
                            budget=budget,
                            replicate=replicate,
                        )
                    )
            for budget in (4, 6):
                rows.append(
                    _row(
                        group_index=group_index,
                        label=label,
                        condition=MidDevCondition.CONTEXT_SURVIVAL_BEAM,
                        budget=budget,
                    )
                )
    return tuple(rows)


def _quality(row: MidDevPlanRow) -> MidDevQualityRow:
    destruction = 0.0 if row.condition is MidDevCondition.NO_OP else 0.2
    return MidDevQualityRow.create(
        plan_row_hash=row.plan_row_hash,
        word_edit_rate=0.0 if row.condition is MidDevCondition.NO_OP else 0.02,
        old_observation_replacement_ratio=destruction,
        exact_destruction_ratio=destruction,
        exact_survival_ratio=1.0 - destruction,
        token_edit_distance=row.operation_count,
        length_ratio=1.0,
        numbers_preserved_fraction=1.0,
        urls_preserved_fraction=1.0,
        protected_span_violation_count=0,
        hard_invariant_status="pass",
    )


def _compute(row: MidDevPlanRow) -> MidDevComputeRow:
    return MidDevComputeRow.create(
        plan_row_hash=row.plan_row_hash,
        expanded_state_count=row.operation_count,
        pruned_state_count=0,
        candidate_evaluation_count=row.operation_count,
        expansion_cache_hit_count=0,
        expansion_cache_miss_count=row.operation_count,
        geometry_cache_hit_count=0,
        planning_wall_time_ms=1.0,
        selection_detector_query_count=0,
        selection_secret_query_count=0,
    )


def _frozen_plan(source_count: int = 32) -> MidDevFrozenPlan:
    rows = _complete_plan_rows(source_count)
    return MidDevFrozenPlan.create(
        corpus_artifact_hash=sha256_text("corpus"),
        source_profile_hash=sha256_text("profile"),
        analysis_split_hash=sha256_text("split"),
        selection_config=MidDevSelectionConfig.frozen(),
        selection_attestation=MidDevSelectionAttestation.from_observed(
            attested_expander_count=source_count * 2,
            detector_access_observed=False,
            secret_access_observed=False,
            detector_query_count=0,
            secret_query_count=0,
        ),
        rows=rows,
        quality_rows=tuple(_quality(value) for value in rows),
        compute_rows=tuple(_compute(value) for value in rows),
    )


def test_frozen_plan_requires_complete_random_replicate_matrix() -> None:
    plan = _frozen_plan()
    expected_per_sample = 1 + len(MID_DEV_BUDGETS) * (3 + MID_DEV_RANDOM_REPLICATES) + 2
    assert len(plan.rows) == 32 * 2 * expected_per_sample

    rows = list(_complete_plan_rows())
    missing = next(
        index
        for index, row in enumerate(rows)
        if row.condition is MidDevCondition.RANDOM_SAFE
        and row.budget == 4
        and row.replicate == 15
    )
    rows.pop(missing)
    with pytest.raises(ValueError, match="complete frozen condition"):
        MidDevFrozenPlan.create(
            corpus_artifact_hash=sha256_text("corpus"),
            source_profile_hash=sha256_text("profile"),
            analysis_split_hash=sha256_text("split"),
            selection_config=MidDevSelectionConfig.frozen(),
            selection_attestation=MidDevSelectionAttestation.from_observed(
                attested_expander_count=64,
                detector_access_observed=False,
                secret_access_observed=False,
                detector_query_count=0,
                secret_query_count=0,
            ),
            rows=rows,
            quality_rows=tuple(_quality(value) for value in rows),
            compute_rows=tuple(_compute(value) for value in rows),
        )


def test_quality_sidecar_rejects_protected_span_violation() -> None:
    row = _row(
        group_index=0,
        label=WatermarkLabel.WATERMARKED,
        condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=1,
    )
    with pytest.raises(ValueError, match="protected-span"):
        MidDevQualityRow.create(
            plan_row_hash=row.plan_row_hash,
            word_edit_rate=0.1,
            old_observation_replacement_ratio=0.2,
            exact_destruction_ratio=0.2,
            exact_survival_ratio=0.8,
            token_edit_distance=1,
            length_ratio=1.0,
            numbers_preserved_fraction=1.0,
            urls_preserved_fraction=1.0,
            protected_span_violation_count=1,
            hard_invariant_status="pass",
        )


def test_ecs1_name_is_reserved_for_predictor_comparison_not_policy_labels() -> None:
    assert MID_DEV_ECS1_PREDICTOR_VERSION.startswith("E-CS1-")
    assert all(not value.value.startswith("E-CS") for value in MidDevCondition)


def test_ecs1_predictor_rows_bind_grouped_holdout_and_exact_vs_old_predictors() -> None:
    plan = _frozen_plan()
    target = next(
        value
        for value in plan.rows
        if value.source_group_id == "group-000"
        and value.source_label is WatermarkLabel.WATERMARKED
        and value.condition is MidDevCondition.CONTEXT_SURVIVAL_GREEDY
        and value.budget == 4
    )
    scored = MidDevScoredRow.create(
        plan_row=target,
        detector_identity_hash=sha256_text("detector"),
        threshold_hash=sha256_text("threshold"),
        threshold_value=0.5,
        pristine_score=0.8,
        transformed_score=0.7,
    )
    predictors = build_ecs1_predictor_rows(
        plan,
        (scored,),
        {target.prompt_id: MidDevAnalysisSplit.EVALUATION},
    )
    assert len(predictors) == 1
    predictor = predictors[0]
    assert predictor.analysis_split is MidDevAnalysisSplit.EVALUATION
    assert predictor.word_edit_rate == pytest.approx(0.02)
    assert predictor.old_observation_replacement_ratio == pytest.approx(0.2)
    assert predictor.exact_destruction_ratio == pytest.approx(0.2)
    assert predictor.exact_survival_ratio == pytest.approx(0.8)
    assert predictor.detector_margin_drop == pytest.approx(0.1)


def _comparison_rows(source_count: int = 32) -> tuple[MidDevScoredRow, ...]:
    rows: list[MidDevScoredRow] = []
    for group_index in range(source_count):
        for label in (WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED):
            baseline = _row(
                group_index=group_index,
                label=label,
                condition=MidDevCondition.CURRENT_STRONGEST_BASELINE,
                budget=4,
            )
            greedy = _row(
                group_index=group_index,
                label=label,
                condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
                budget=4,
            )
            if label is WatermarkLabel.WATERMARKED:
                baseline_drop, greedy_drop = 0.10, 0.20
            else:
                baseline_drop, greedy_drop = 0.01, 0.03
            for plan_row, drop in ((baseline, baseline_drop), (greedy, greedy_drop)):
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


def test_source_grouped_comparison_is_matched_control_adjusted_and_source_level() -> None:
    result = source_grouped_control_adjusted_comparison(
        _comparison_rows(),
        comparison_condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=4,
        bootstrap_replicates=500,
        bootstrap_seed=17,
    )
    assert result.source_group_count == 32
    assert result.mean_watermarked_difference == pytest.approx(0.10)
    assert result.mean_control_difference == pytest.approx(0.02)
    assert result.mean_control_adjusted_difference == pytest.approx(0.08)
    assert result.bootstrap_lower == pytest.approx(0.08)
    assert result.bootstrap_upper == pytest.approx(0.08)
    assert result.positive_adjusted_count == 32
    assert result.two_sided_sign_p_value < 1e-8


def test_middev_foundation_modules_do_not_import_detectors_or_secret_material() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "fuckmark" / "corpus" / "mid_dev.py",
        root / "fuckmark" / "experiments" / "mid_dev_context_survival.py",
    )
    forbidden = ("detector", "g_value", "gvalue", "watermark_key", "secret_key")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
        assert all(
            not any(value in name.lower() for value in forbidden)
            for name in imported
        ), (path, imported)
