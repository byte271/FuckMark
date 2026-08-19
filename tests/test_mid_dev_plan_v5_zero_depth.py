from fuckmark.experiments.mid_dev_plan_v5 import MidDevNormalizedCostRow, MidDevNormalizedPlanner
from fuckmark.hashing import sha256_text
from fuckmark.search.visible_cost_budget import VisibleCostTier


def test_normalized_row_allows_truthful_zero_depth_frontier():
    text = "stable text"
    row = MidDevNormalizedCostRow.create(
        source_group_id="group-zero",
        sample_id="sample-zero",
        source_text_hash=sha256_text(text),
        planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
        tier=VisibleCostTier.STRICT,
        replicate=0,
        candidate_registry_hash=sha256_text("registry"),
        maximum_search_operations=0,
        realized_operation_count=0,
        transformed_text=text,
        final_search_state_hash=sha256_text("state"),
        search_result_hash=sha256_text("result"),
        selection_trace_hash=sha256_text("trace"),
        residual_geometry_hash=sha256_text("geometry"),
        word_edit_rate=0.0,
        character_edit_rate=0.0,
        token_edit_distance=0,
        length_ratio=1.0,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
    )
    assert row.maximum_search_operations == 0
    assert row.realized_operation_count == 0
    assert row.normalized_cost_eligible is True
