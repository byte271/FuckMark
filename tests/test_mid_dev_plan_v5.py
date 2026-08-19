import json

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus.schema import CorpusDomain, WatermarkLabel
from fuckmark.experiments.mid_dev_context_survival import (
    MidDevCondition,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
)
from fuckmark.experiments.mid_dev_freeze import (
    MidDevDeterministicComputeRow,
    MidDevDeterministicFrozenPlan,
)
from fuckmark.experiments.mid_dev_plan_v5 import (
    MID_DEV_DEVELOPMENT_PLAN_VERSION,
    MID_DEV_DEVELOPMENT_ROLE,
    MidDevDevelopmentPlanV5,
    MidDevNormalizedCostRow,
    MidDevNormalizedPlanner,
)
from fuckmark.experiments.mid_dev_plan_v5_io import _normalized_row
from fuckmark.hashing import sha256_text
from fuckmark.search.visible_cost_budget import VisibleCostTier


_SOURCE = "A stable source sentence for normalized MidDev planning."
_SOURCE_HASH = sha256_text(_SOURCE)
_SAMPLE_ID = "sample-watermarked"
_GROUP_ID = "group-0001"
_COMMIT = "a" * 40


def _legacy_plan():
    selection = MidDevSelectionConfig.frozen()
    attestation = MidDevSelectionAttestation.from_observed(
        attested_expander_count=1,
        detector_access_observed=False,
        secret_access_observed=False,
        detector_query_count=0,
        secret_query_count=0,
    )
    row = MidDevPlanRow.create(
        source_group_id=_GROUP_ID,
        prompt_id="prompt-0001",
        sample_id=_SAMPLE_ID,
        source_label=WatermarkLabel.WATERMARKED,
        prompt_family_id="family-0001",
        domain=next(iter(CorpusDomain)),
        target_length=128,
        source_text_hash=_SOURCE_HASH,
        condition=MidDevCondition.NO_OP,
        budget=0,
        replicate=0,
        transformed_text=_SOURCE,
        operation_count=0,
        status="SUCCESS",
        selection_trace_hash=sha256_text("legacy-trace"),
    )
    quality = MidDevQualityRow.create(
        plan_row_hash=row.plan_row_hash,
        word_edit_rate=0.0,
        old_observation_replacement_ratio=0.0,
        exact_destruction_ratio=0.0,
        exact_survival_ratio=1.0,
        token_edit_distance=0,
        length_ratio=1.0,
        numbers_preserved_fraction=1.0,
        urls_preserved_fraction=1.0,
        protected_span_violation_count=0,
        hard_invariant_status="pass",
    )
    compute = MidDevDeterministicComputeRow.create(
        plan_row_hash=row.plan_row_hash,
        expanded_state_count=0,
        pruned_state_count=0,
        candidate_evaluation_count=0,
        expansion_cache_hit_count=0,
        expansion_cache_miss_count=0,
        geometry_cache_hit_count=0,
    )
    return MidDevDeterministicFrozenPlan.create(
        corpus_artifact_hash=sha256_text("corpus"),
        source_profile_hash=sha256_text("source-profile"),
        analysis_split_hash=sha256_text("analysis-split"),
        source_code_commit=_COMMIT,
        selection_config=selection,
        selection_attestation=attestation,
        rows=(row,),
        quality_rows=(quality,),
        compute_rows=(compute,),
    )


def _normalized_row_value(
    *,
    tier=VisibleCostTier.STRICT,
    planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
    replicate=0,
):
    return MidDevNormalizedCostRow.create(
        source_group_id=_GROUP_ID,
        sample_id=_SAMPLE_ID,
        source_text_hash=_SOURCE_HASH,
        planner=planner,
        tier=tier,
        replicate=replicate,
        candidate_registry_hash=sha256_text("candidate-registry"),
        maximum_search_operations=12,
        realized_operation_count=0,
        transformed_text=_SOURCE,
        final_search_state_hash=sha256_text("state"),
        search_result_hash=sha256_text("result"),
        selection_trace_hash=sha256_text("normalized-trace"),
        residual_geometry_hash=sha256_text("residual-geometry"),
        word_edit_rate=0.0,
        character_edit_rate=0.0,
        token_edit_distance=0,
        length_ratio=1.0,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
    )


def test_v5_wraps_legacy_plan_without_mutating_legacy_matrix():
    legacy = _legacy_plan()
    normalized = _normalized_row_value()
    plan = MidDevDevelopmentPlanV5.create(
        source_code_commit=_COMMIT,
        legacy_plan=legacy,
        normalized_rows=(normalized,),
    )
    assert plan.algorithm_version == MID_DEV_DEVELOPMENT_PLAN_VERSION
    assert plan.role == MID_DEV_DEVELOPMENT_ROLE
    assert plan.legacy_plan is legacy
    assert plan.legacy_plan_hash == legacy.plan_hash
    assert plan.normalized_rows == (normalized,)


def test_v5_rejects_normalized_row_bound_to_different_legacy_sample():
    legacy = _legacy_plan()
    row = _normalized_row_value()
    bad = MidDevNormalizedCostRow.create(
        source_group_id="different-group",
        sample_id=row.sample_id,
        source_text_hash=row.source_text_hash,
        planner=row.planner,
        tier=row.tier,
        replicate=row.replicate,
        candidate_registry_hash=row.candidate_registry_hash,
        maximum_search_operations=row.maximum_search_operations,
        realized_operation_count=row.realized_operation_count,
        transformed_text=row.transformed_text,
        final_search_state_hash=row.final_search_state_hash,
        search_result_hash=row.search_result_hash,
        selection_trace_hash=row.selection_trace_hash,
        residual_geometry_hash=row.residual_geometry_hash,
        word_edit_rate=row.word_edit_rate,
        character_edit_rate=row.character_edit_rate,
        token_edit_distance=row.token_edit_distance,
        length_ratio=row.length_ratio,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
    )
    with pytest.raises(ValueError, match="legacy sample identity"):
        MidDevDevelopmentPlanV5.create(
            source_code_commit=_COMMIT,
            legacy_plan=legacy,
            normalized_rows=(bad,),
        )


def test_normalized_row_enforces_tier_and_planner_contracts():
    with pytest.raises(ValueError, match="eligible"):
        MidDevNormalizedCostRow.create(
            source_group_id=_GROUP_ID,
            sample_id=_SAMPLE_ID,
            source_text_hash=_SOURCE_HASH,
            planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
            tier=VisibleCostTier.STRICT,
            replicate=0,
            candidate_registry_hash=sha256_text("candidate-registry"),
            maximum_search_operations=12,
            realized_operation_count=1,
            transformed_text=_SOURCE + "x",
            final_search_state_hash=sha256_text("state-bad"),
            search_result_hash=sha256_text("result-bad"),
            selection_trace_hash=sha256_text("trace-bad"),
            residual_geometry_hash=sha256_text("geometry-bad"),
            word_edit_rate=0.0,
            character_edit_rate=0.02,
            token_edit_distance=1,
            length_ratio=1.0,
            protected_span_violation_count=0,
            hard_invariant_passed=True,
        )
    with pytest.raises(ValueError, match="replicate=0"):
        _normalized_row_value(replicate=1)
    random_row = _normalized_row_value(
        tier=VisibleCostTier.RELAXED,
        planner=MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
        replicate=15,
    )
    assert random_row.replicate == 15


def test_normalized_row_json_parser_replays_hashes_and_enums():
    row = _normalized_row_value()
    value = json.loads(canonical_json_text(row))
    replayed = _normalized_row(value)
    assert replayed == row
    value["tier"] = "RELAXED"
    with pytest.raises(ValueError):
        _normalized_row(value)
