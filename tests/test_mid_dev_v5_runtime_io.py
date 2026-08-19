from pathlib import Path

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.experiments.mid_dev_plan_io import MidDevPlanJsonError
from fuckmark.experiments.mid_dev_plan_v5 import MidDevNormalizedPlanner
from fuckmark.experiments.mid_dev_v5_builder import (
    MidDevNormalizedSelectionTrace,
    MidDevNormalizedTraceArtifact,
)
from fuckmark.experiments.mid_dev_v5_runtime_io import parse_mid_dev_normalized_trace_artifact_json
from fuckmark.hashing import sha256_text
from fuckmark.search.visible_cost_budget import VisibleCostTier, policy_for_tier


def _trace():
    policy = policy_for_tier(VisibleCostTier.STRICT)
    return MidDevNormalizedSelectionTrace.create(
        source_group_id="group-0001",
        sample_id="sample-0001",
        planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
        tier=VisibleCostTier.STRICT,
        replicate=0,
        seed=0,
        policy_hash=policy.policy_hash,
        candidate_registry_hash=sha256_text("registry"),
        reference_state_hash=None,
        matched_cost_envelope_hash=None,
        search_result_hash=sha256_text("result"),
        final_search_state_hash=sha256_text("state"),
        candidate_hashes=(),
        operation_hashes=(),
        rule_hashes=(),
        status="NORMALIZED_FRONTIER",
        detector_access_observed=False,
        secret_access_observed=False,
    )


def test_normalized_trace_artifact_canonical_round_trip():
    artifact = MidDevNormalizedTraceArtifact.create(
        development_plan_hash=sha256_text("development-plan"),
        traces=(_trace(),),
    )
    text = canonical_json_text(artifact)
    assert parse_mid_dev_normalized_trace_artifact_json(text) == artifact
    with pytest.raises(MidDevPlanJsonError, match="not canonical"):
        parse_mid_dev_normalized_trace_artifact_json(text + " ")


def test_v5_scoring_cli_requires_vnext_calibration_artifacts_and_excludes_old_length_calibration():
    source = Path("fuckmark/mid_dev_v5_score_hf.py").read_text(encoding="utf-8")
    assert "--opportunity-audit-json" in source
    assert "--regime-decision-json" in source
    assert "--threshold-registry-json" in source
    assert "mid_dev_vnext_artifact_io" in source
    assert "mid_dev_calibration_io" not in source
    assert "length_calibration" not in source.lower()
    assert "score_mid_dev_development_plan_v5" in source


def test_v5_scoring_cli_is_scoring_only_and_real_middev_remains_blocked():
    source = Path("fuckmark/mid_dev_v5_score_hf.py").read_text(encoding="utf-8")
    assert "build_mid_dev_development_plan_v5" not in source
    assert "build_frozen_calibration_threshold_registry" not in source
    workflow = Path(".github/workflows/mid-dev-context-survival.yml").read_text(encoding="utf-8")
    assert "PRE_RUN_LOCK_REQUIRED_AND_VNEXT_WORKFLOW_NOT_YET_FROZEN" in workflow
