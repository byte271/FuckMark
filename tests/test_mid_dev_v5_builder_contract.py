import pytest

from fuckmark.experiments.mid_dev_plan_v5 import MidDevNormalizedPlanner
from fuckmark.experiments.mid_dev_v5_builder import (
    MID_DEV_V5_REQUIRED_CELL_REGISTRY,
    MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
    MidDevNormalizedSelectionTrace,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.search.visible_cost_budget import VisibleCostTier, policy_for_tier


def _h(value):
    return sha256_text(value)


def test_required_v5_cells_are_exact_and_exclude_killed_beam_v3():
    assert MID_DEV_V5_REQUIRED_CELL_REGISTRY == (
        "LEGACY_NO_OP",
        "LEGACY_CURRENT_STRONGEST_KEY_BLIND_BASELINE_B1_B2_B4_B6",
        "LEGACY_CONTEXT_SURVIVAL_GREEDY_B1_B2_B4_B6",
        "LEGACY_CONTEXT_SURVIVAL_BEAM_V2_B4_B6",
        "NORMALIZED_BEAM_V2_STRICT",
        "NORMALIZED_BEAM_V2_RELAXED",
        "NORMALIZED_RANDOM_SAFE_MATCHED_COST_STRICT_X16",
        "NORMALIZED_RANDOM_SAFE_MATCHED_COST_RELAXED_X16",
    )
    assert all("BEAM_V3" not in value for value in MID_DEV_V5_REQUIRED_CELL_REGISTRY)
    assert MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH == sha256_json(MID_DEV_V5_REQUIRED_CELL_REGISTRY)


def test_normalized_beam_trace_cannot_carry_random_matching_reference():
    policy = policy_for_tier(VisibleCostTier.STRICT)
    with pytest.raises(ValueError, match="cannot carry"):
        MidDevNormalizedSelectionTrace.create(
            source_group_id="group",
            sample_id="sample",
            planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
            tier=VisibleCostTier.STRICT,
            replicate=0,
            seed=0,
            policy_hash=policy.policy_hash,
            candidate_registry_hash=_h("registry"),
            reference_state_hash=_h("reference"),
            matched_cost_envelope_hash=_h("envelope"),
            search_result_hash=_h("result"),
            final_search_state_hash=_h("state"),
            candidate_hashes=(),
            operation_hashes=(),
            rule_hashes=(),
            status="NORMALIZED_FRONTIER",
            detector_access_observed=False,
            secret_access_observed=False,
        )


def test_normalized_random_trace_requires_beam_reference_and_aligned_rule_usage():
    policy = policy_for_tier(VisibleCostTier.RELAXED)
    with pytest.raises(ValueError, match="requires Beam v2 reference"):
        MidDevNormalizedSelectionTrace.create(
            source_group_id="group",
            sample_id="sample",
            planner=MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
            tier=VisibleCostTier.RELAXED,
            replicate=0,
            seed=1,
            policy_hash=policy.policy_hash,
            candidate_registry_hash=_h("registry"),
            reference_state_hash=None,
            matched_cost_envelope_hash=None,
            search_result_hash=_h("result"),
            final_search_state_hash=_h("state"),
            candidate_hashes=(),
            operation_hashes=(),
            rule_hashes=(),
            status="MATCHED_COST_INSUFFICIENT",
            detector_access_observed=False,
            secret_access_observed=False,
        )
    trace = MidDevNormalizedSelectionTrace.create(
        source_group_id="group",
        sample_id="sample",
        planner=MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
        tier=VisibleCostTier.RELAXED,
        replicate=15,
        seed=1,
        policy_hash=policy.policy_hash,
        candidate_registry_hash=_h("registry"),
        reference_state_hash=_h("reference"),
        matched_cost_envelope_hash=_h("envelope"),
        search_result_hash=_h("result"),
        final_search_state_hash=_h("state"),
        candidate_hashes=(_h("candidate"),),
        operation_hashes=(_h("operation"),),
        rule_hashes=(_h("rule"),),
        status="MATCHED_COST_SUCCESS",
        detector_access_observed=False,
        secret_access_observed=False,
    )
    assert trace.replicate == 15
    assert trace.rule_hashes == (_h("rule"),)
