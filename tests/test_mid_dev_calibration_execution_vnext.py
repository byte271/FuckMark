from __future__ import annotations

import ast
from pathlib import Path

from fuckmark.corpus import CalibrationRole
from fuckmark.experiments.mid_dev_calibration_readiness import (
    FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN,
    MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE,
    MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE,
)
from fuckmark.experiments.mid_dev_vnext import (
    CalibrationReadinessStatus,
    MidDevCalibrationReadiness,
)


def _python_source(path: str) -> tuple[str, ast.AST]:
    source = Path(path).read_text(encoding="utf-8")
    return source, ast.parse(source)


def test_frozen_readiness_uses_independent_select_and_audit_candidate_pools() -> None:
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    assert readiness.negatives_per_target == 20_000
    assert readiness.shard_size == 500
    assert len(readiness.select_plan.shards) == MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE == 80
    assert len(readiness.audit_plan.shards) == MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE == 80
    assert len(readiness.select_plan.prompt_ids) == MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE == 40_000
    assert len(readiness.audit_plan.prompt_ids) == MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE == 40_000
    assert readiness.select_plan.role is CalibrationRole.SELECT
    assert readiness.audit_plan.role is CalibrationRole.AUDIT
    assert readiness.select_plan.plan_hash != readiness.audit_plan.plan_hash
    assert not set(readiness.select_plan.prompt_ids) & set(readiness.audit_plan.prompt_ids)
    assert not set(readiness.select_plan.seeds) & set(readiness.audit_plan.seeds)


def test_frozen_readiness_is_formally_ready() -> None:
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    assert isinstance(readiness, MidDevCalibrationReadiness)
    assert readiness.status is CalibrationReadinessStatus.READY
    assert readiness.readiness_hash


def test_opportunity_audit_source_cannot_access_detector_or_calibration_thresholds() -> None:
    source, tree = _python_source("fuckmark/mid_dev_opportunity_audit_hf.py")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "HuggingFaceSynthIDAdapter" not in names
    assert "calibrate_detector" not in names
    assert "build_frozen_calibration_threshold_registry" not in names
    assert "audit_frozen_calibration_threshold_registry" not in names
    assert '"attack_transform_count": 0' in source
    assert '"attack_score_count": 0' in source
    assert '"detector_score_count": 0' in source
    assert '"calibration_threshold_constructed": False' in source
    assert '"cal_select_or_audit_samples_consumed": False' in source


def test_opportunity_workflow_is_manual_only() -> None:
    source = Path(".github/workflows/middev-opportunity-audit.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "python -m fuckmark.mid_dev_opportunity_audit_hf" in source


def test_large_calibration_workflow_is_manual_and_threshold_job_cannot_see_audit_data() -> None:
    source = Path(".github/workflows/middev-calibration-shards.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "opportunity_run_id:" in source
    assert "source_coverage_run_id:" in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "select_matrix: ${{ steps.freeze.outputs.select_matrix }}" in source
    assert "audit_matrix: ${{ steps.freeze.outputs.audit_matrix }}" in source
    assert "assert len(select_include) == 80" in source
    assert "assert len(audit_include) == 80" in source
    assert "max-parallel: 20" in source
    assert "needs: [preflight, generate-select]" in source
    assert "needs: [preflight, generate-audit]" in source
    assert "--opportunity-audit-hash" in source
    assert "--regime-decision-hash" in source
    assert "mid_dev_calibration_compact_hf" in source
    threshold_block = source.split("\n  threshold:\n", 1)[1].split("\n  audit:\n", 1)[0]
    assert "needs: [preflight, compact-select]" in threshold_block
    assert "middev-cal-v2-audit-candidates" not in threshold_block
    assert "middev-cal-v2-audit-compacted" not in threshold_block
    assert "middev-cal-v2-candidate-pair" not in threshold_block
    assert "--audit-json" not in threshold_block
    assert "--audit-compaction-provenance-json" not in threshold_block
    assert "--select-compaction-provenance-json" in threshold_block
    assert "mid_dev_calibration_threshold_compacted_hf" in threshold_block
    audit_block = source.split("\n  audit:\n", 1)[1]
    assert "--threshold-provenance-json" in audit_block
    assert "--audit-compaction-provenance-json" in audit_block
    assert "threshold_recalibration_performed" not in threshold_block
    assert "CALIBRATION_AUDIT_FPR_UNSTABLE" in audit_block
