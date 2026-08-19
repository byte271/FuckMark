from __future__ import annotations

import pytest

from fuckmark.corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION,
    CalibrationRole,
    MidDevCalibrationShardError,
    MidDevCalibrationShardOutputManifest,
    build_mid_dev_calibration_shard_plan,
    merge_mid_dev_calibration_shard_outputs,
    validate_calibration_merged_independence,
    validate_calibration_role_independence,
)
from fuckmark.hashing import sha256_json


def _outputs(plan):
    output = []
    for spec in plan.shards:
        indices = tuple(range(spec.start_index, spec.end_index_exclusive))
        sample_ids = tuple(f"{value}-unwatermarked" for value in spec.prompt_ids)
        record_hashes = tuple(sha256_json(("record", plan.role.value, spec.target_length, value)) for value in indices)
        text_hashes = tuple(sha256_json(("text", plan.role.value, spec.target_length, value)) for value in indices)
        token_hashes = tuple(sha256_json(("tokens", plan.role.value, spec.target_length, value)) for value in indices)
        payload = {
            "algorithm_version": MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION,
            "role": plan.role.value,
            "plan_hash": plan.plan_hash,
            "shard_id": spec.shard_id,
            "shard_spec_hash": spec.shard_hash,
            "target_length": spec.target_length,
            "source_indices": indices,
            "prompt_ids": spec.prompt_ids,
            "sample_ids": sample_ids,
            "sample_record_hashes": record_hashes,
            "text_sha256s": text_hashes,
            "continuation_token_hashes": token_hashes,
            "model_tokenizer_identity_hash": "a" * 64,
            "watermark_config_hash": "b" * 64,
            "watermark_condition_hash": "c" * 64,
        }
        output.append(MidDevCalibrationShardOutputManifest(
            MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION, plan.role, plan.plan_hash, spec.shard_id,
            spec.shard_hash, spec.target_length, indices, spec.prompt_ids, sample_ids, record_hashes,
            text_hashes, token_hashes, "a" * 64, "b" * 64, "c" * 64, sha256_json(payload),
        ))
    return tuple(output)


def test_select_audit_plans_are_deterministic_and_disjoint() -> None:
    select = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    audit = build_mid_dev_calibration_shard_plan(CalibrationRole.AUDIT, negatives_per_target=1000, shard_size=250)
    replay = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    assert select.plan_hash == replay.plan_hash
    assert len(select.prompt_ids) == 2000
    assert len(audit.prompt_ids) == 2000
    assert len(select.shards) == 8
    assert len(audit.shards) == 8
    assert set(select.prompt_ids).isdisjoint(audit.prompt_ids)
    assert set(select.seeds).isdisjoint(audit.seeds)
    assert select.prompt_source_id != audit.prompt_source_id
    validate_calibration_role_independence(select, audit)


def test_serious_development_plan_rejects_subminimum_count() -> None:
    with pytest.raises(ValueError):
        build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=999, shard_size=250)


def test_merge_rejects_missing_and_duplicate_shards() -> None:
    plan = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    outputs = _outputs(plan)
    merged = merge_mid_dev_calibration_shard_outputs(plan, outputs)
    assert len(merged.sample_ids) == 2000
    with pytest.raises(MidDevCalibrationShardError):
        merge_mid_dev_calibration_shard_outputs(plan, outputs[:-1])
    with pytest.raises(MidDevCalibrationShardError):
        merge_mid_dev_calibration_shard_outputs(plan, outputs[:-1] + (outputs[0],))


def test_merged_select_audit_manifests_remain_independent() -> None:
    select = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    audit = build_mid_dev_calibration_shard_plan(CalibrationRole.AUDIT, negatives_per_target=1000, shard_size=250)
    validate_calibration_merged_independence(
        merge_mid_dev_calibration_shard_outputs(select, _outputs(select)),
        merge_mid_dev_calibration_shard_outputs(audit, _outputs(audit)),
    )
