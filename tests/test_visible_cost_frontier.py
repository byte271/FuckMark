from fuckmark.experiments.visible_cost_frontier import VISIBLE_COST_FRONTIER_ARTIFACT_VERSION
from fuckmark.search.visible_cost_budget import (
    RELAXED_VISIBLE_COST_POLICY,
    STRICT_VISIBLE_COST_POLICY,
    VisibleCostTier,
)


def test_visible_cost_frontier_versions_and_policies_are_frozen():
    assert VISIBLE_COST_FRONTIER_ARTIFACT_VERSION == "tiny-dev-visible-cost-frontier-v1"
    assert STRICT_VISIBLE_COST_POLICY.tier is VisibleCostTier.STRICT
    assert RELAXED_VISIBLE_COST_POLICY.tier is VisibleCostTier.RELAXED
    assert STRICT_VISIBLE_COST_POLICY.word_edit_rate_max == 0.03
    assert STRICT_VISIBLE_COST_POLICY.character_edit_rate_max == 0.015
    assert STRICT_VISIBLE_COST_POLICY.length_ratio_min == 0.97
    assert STRICT_VISIBLE_COST_POLICY.length_ratio_max == 1.03
    assert RELAXED_VISIBLE_COST_POLICY.word_edit_rate_max == 0.05
    assert RELAXED_VISIBLE_COST_POLICY.character_edit_rate_max == 0.03
    assert RELAXED_VISIBLE_COST_POLICY.length_ratio_min is None
    assert RELAXED_VISIBLE_COST_POLICY.length_ratio_max is None
