from pathlib import Path

from fuckmark.experiments.mid_dev_calibration_readiness import (
    FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN,
    MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE,
    MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
    MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
    MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE,
    MID_DEV_CALIBRATION_READINESS_VERSION,
)


def test_calibration_readiness_freezes_v2_candidate_pool_dimensions():
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    assert MID_DEV_CALIBRATION_READINESS_VERSION == "mid-dev-calibration-readiness-v2"
    assert MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET == 20_000
    assert MID_DEV_CALIBRATION_READINESS_SHARD_SIZE == 500
    assert MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE == 80
    assert MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE == 40_000
    assert readiness.negatives_per_target == 20_000
    assert readiness.shard_size == 500
    assert len(readiness.select_plan.prompt_ids) == 40_000
    assert len(readiness.audit_plan.prompt_ids) == 40_000
    assert len(readiness.select_plan.shards) == 80
    assert len(readiness.audit_plan.shards) == 80


def test_cal_select_and_cal_audit_plan_domains_are_disjoint():
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    assert readiness.select_plan.prompt_source_id != readiness.audit_plan.prompt_source_id
    assert set(readiness.select_plan.prompt_ids).isdisjoint(readiness.audit_plan.prompt_ids)
    assert set(readiness.select_plan.seeds).isdisjoint(readiness.audit_plan.seeds)
    assert readiness.select_plan_hash != readiness.audit_plan_hash
    assert readiness.role_independence_hash


def test_calibration_readiness_cli_is_generation_and_detector_free():
    source = Path("fuckmark/mid_dev_calibration_readiness.py").read_text(encoding="utf-8").lower()
    assert "huggingface" not in source
    assert "generate(" not in source
    assert "detector" not in source
    assert "calibrate_detector" not in source
    assert "--select-plan-json" in source
    assert "--audit-plan-json" in source
