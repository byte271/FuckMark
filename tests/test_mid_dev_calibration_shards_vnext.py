from __future__ import annotations

import pytest

from fuckmark.corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION,
    CalibrationRole,
    MidDevCalibrationShardError,
    MidDevCalibrationShardOutputManifest,
    build_mid_dev_calibration_prompt_records,
    build_mid_dev_calibration_shard_plan,
    merge_mid_dev_calibration_shard_outputs,
    validate_calibration_merged_independence,
    validate_calibration_role_independence,
)
from fuckmark.corpus.schema import CorpusSplit
from fuckmark.hashing import sha256_json


def _outputs(plan, *, duplicate_content: bool = False):
    output = []
    for shard_number, spec in enumerate(plan.shards):
        indices = tuple(range(spec.start_index, spec.end_index_exclusive))
        sample_ids = tuple(f"{value}-unwatermarked" for value in spec.prompt_ids)
        record_hashes = tuple(sha256_json(("record", plan.role.value, spec.target_length, value)) for value in indices)
        text_hashes = tuple(sha256_json(("text", plan.role.value, spec.target_length, value)) for value in indices)
        token_hashes = tuple(sha256_json(("tokens", plan.role.value, spec.target_length, value)) for value in indices)
        if duplicate_content and shard_number == 0:
            text_values = list(text_hashes)
            token_values = list(token_hashes)
            text_values[1] = text_values[0]
            token_values[2] = token_values[0]
            text_hashes = tuple(text_values)
            token_hashes = tuple(token_values)
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


def _replace_content_hashes(
    value: MidDevCalibrationShardOutputManifest,
    *,
    text_sha256s: tuple[str, ...] | None = None,
    continuation_token_hashes: tuple[str, ...] | None = None,
) -> MidDevCalibrationShardOutputManifest:
    texts = value.text_sha256s if text_sha256s is None else text_sha256s
    tokens = value.continuation_token_hashes if continuation_token_hashes is None else continuation_token_hashes
    payload = {
        "algorithm_version": value.algorithm_version,
        "role": value.role.value,
        "plan_hash": value.plan_hash,
        "shard_id": value.shard_id,
        "shard_spec_hash": value.shard_spec_hash,
        "target_length": value.target_length,
        "source_indices": value.source_indices,
        "prompt_ids": value.prompt_ids,
        "sample_ids": value.sample_ids,
        "sample_record_hashes": value.sample_record_hashes,
        "text_sha256s": texts,
        "continuation_token_hashes": tokens,
        "model_tokenizer_identity_hash": value.model_tokenizer_identity_hash,
        "watermark_config_hash": value.watermark_config_hash,
        "watermark_condition_hash": value.watermark_condition_hash,
    }
    return MidDevCalibrationShardOutputManifest(
        value.algorithm_version,
        value.role,
        value.plan_hash,
        value.shard_id,
        value.shard_spec_hash,
        value.target_length,
        value.source_indices,
        value.prompt_ids,
        value.sample_ids,
        value.sample_record_hashes,
        texts,
        tokens,
        value.model_tokenizer_identity_hash,
        value.watermark_config_hash,
        value.watermark_condition_hash,
        sha256_json(payload),
    )


def test_calibration_prompts_bind_threshold_calibration_split() -> None:
    prompts = build_mid_dev_calibration_prompt_records(CalibrationRole.SELECT, negatives_per_target=1000)
    assert len(prompts) == 2000
    assert {prompt.split for prompt in prompts} == {CorpusSplit.THRESHOLD_CALIBRATION}


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


def test_raw_candidate_outputs_preserve_duplicate_generated_content() -> None:
    plan = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    outputs = _outputs(plan, duplicate_content=True)
    assert outputs[0].text_sha256s[0] == outputs[0].text_sha256s[1]
    assert outputs[0].continuation_token_hashes[0] == outputs[0].continuation_token_hashes[2]
    merged = merge_mid_dev_calibration_shard_outputs(plan, outputs)
    assert len(merged.sample_ids) == 2000
    assert len(set(merged.text_sha256s)) == 1999
    assert len(set(merged.continuation_token_hashes)) == 1999


def test_merged_select_audit_manifests_remain_independent() -> None:
    select = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    audit = build_mid_dev_calibration_shard_plan(CalibrationRole.AUDIT, negatives_per_target=1000, shard_size=250)
    validate_calibration_merged_independence(
        merge_mid_dev_calibration_shard_outputs(select, _outputs(select)),
        merge_mid_dev_calibration_shard_outputs(audit, _outputs(audit)),
    )


def test_cross_role_content_overlap_remains_a_hard_failure() -> None:
    select_plan = build_mid_dev_calibration_shard_plan(CalibrationRole.SELECT, negatives_per_target=1000, shard_size=250)
    audit_plan = build_mid_dev_calibration_shard_plan(CalibrationRole.AUDIT, negatives_per_target=1000, shard_size=250)
    select_outputs = _outputs(select_plan)
    audit_outputs = list(_outputs(audit_plan))
    audit_texts = list(audit_outputs[0].text_sha256s)
    audit_texts[0] = select_outputs[0].text_sha256s[0]
    audit_outputs[0] = _replace_content_hashes(
        audit_outputs[0],
        text_sha256s=tuple(audit_texts),
    )
    select_manifest = merge_mid_dev_calibration_shard_outputs(select_plan, select_outputs)
    audit_manifest = merge_mid_dev_calibration_shard_outputs(audit_plan, tuple(audit_outputs))
    with pytest.raises(MidDevCalibrationShardError, match="text hashes overlap"):
        validate_calibration_merged_independence(select_manifest, audit_manifest)
