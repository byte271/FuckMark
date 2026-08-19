from __future__ import annotations

import pytest

from fuckmark.corpus.schema import CorpusDomain, WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    MidDevCondition,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
    SUCCESS,
)
from fuckmark.experiments.mid_dev_freeze import (
    MidDevDeterministicComputeRow,
    MidDevDeterministicFrozenPlan,
    MidDevRuntimeTimingRow,
)
from fuckmark.hashing import sha256_text


def _plan_row() -> MidDevPlanRow:
    text = "deterministic transformed text"
    return MidDevPlanRow.create(
        source_group_id="group-001",
        prompt_id="prompt-001",
        sample_id="sample-001",
        source_label=WatermarkLabel.WATERMARKED,
        prompt_family_id="family",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        target_length=128,
        source_text_hash=sha256_text("source"),
        condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=1,
        replicate=0,
        transformed_text=text,
        operation_count=1,
        status=SUCCESS,
        selection_trace_hash=sha256_text("trace"),
    )


def _quality(row: MidDevPlanRow) -> MidDevQualityRow:
    return MidDevQualityRow.create(
        plan_row_hash=row.plan_row_hash,
        word_edit_rate=0.01,
        old_observation_replacement_ratio=0.1,
        exact_destruction_ratio=0.2,
        exact_survival_ratio=0.8,
        token_edit_distance=1,
        length_ratio=1.0,
        numbers_preserved_fraction=1.0,
        urls_preserved_fraction=1.0,
        protected_span_violation_count=0,
        hard_invariant_status="pass",
    )


def _compute(row: MidDevPlanRow) -> MidDevDeterministicComputeRow:
    return MidDevDeterministicComputeRow.create(
        plan_row_hash=row.plan_row_hash,
        expanded_state_count=1,
        pruned_state_count=0,
        candidate_evaluation_count=3,
        expansion_cache_hit_count=2,
        expansion_cache_miss_count=1,
        geometry_cache_hit_count=4,
    )


def _plan() -> MidDevDeterministicFrozenPlan:
    row = _plan_row()
    return MidDevDeterministicFrozenPlan.create(
        corpus_artifact_hash=sha256_text("corpus"),
        source_profile_hash=sha256_text("profile"),
        analysis_split_hash=sha256_text("split"),
        source_code_commit="a" * 40,
        selection_config=MidDevSelectionConfig.frozen(),
        selection_attestation=MidDevSelectionAttestation.from_observed(
            attested_expander_count=1,
            detector_access_observed=False,
            secret_access_observed=False,
            detector_query_count=0,
            secret_query_count=0,
        ),
        rows=(row,),
        quality_rows=(_quality(row),),
        compute_rows=(_compute(row),),
    )


def test_runtime_timing_does_not_change_deterministic_plan_hash() -> None:
    first = _plan()
    second = _plan()
    timing_a = MidDevRuntimeTimingRow.create(
        plan_row_hash=first.rows[0].plan_row_hash,
        planning_wall_time_ms=1.0,
    )
    timing_b = MidDevRuntimeTimingRow.create(
        plan_row_hash=first.rows[0].plan_row_hash,
        planning_wall_time_ms=999.0,
    )
    assert first.plan_hash == second.plan_hash
    assert timing_a.timing_hash != timing_b.timing_hash
    assert "planning_wall_time_ms" not in first.payload()


def test_deterministic_compute_rejects_selection_detector_query() -> None:
    row = _plan_row()
    with pytest.raises(ValueError, match="detector or secret queries"):
        MidDevDeterministicComputeRow.create(
            plan_row_hash=row.plan_row_hash,
            expanded_state_count=1,
            pruned_state_count=0,
            candidate_evaluation_count=1,
            expansion_cache_hit_count=0,
            expansion_cache_miss_count=1,
            geometry_cache_hit_count=0,
            selection_detector_query_count=1,
        )
