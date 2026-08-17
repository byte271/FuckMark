from dataclasses import replace

import pytest

from confirmatory_helpers import (
    confirmatory_condition_plan,
    confirmatory_manifest,
    preregistration_inputs,
)
from test_confirmatory_preflight_verification import _bayesian_materials
from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.corpus import TextOnlyTokenRecord, WatermarkLabel
from fuckmark.detectors import apply_calibration
from fuckmark.detectors.bayesian_calibration import bayesian_calibration_evidence
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_outcome_replay import build_confirmatory_outcome_fields
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    default_transform_registry,
)


def _fixture():
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    bayesian_bundle, _, artifacts = _bayesian_materials(
        inputs.model_tokenizers[0].identity_hash
    )
    calibration_bundles = inputs.calibration_bundles + (bayesian_bundle,)
    condition_plan = confirmatory_condition_plan(
        calibration_bundles=calibration_bundles
    )
    inputs = replace(
        inputs,
        calibration_bundles=calibration_bundles,
        budget_config_hash=condition_plan.plan_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    manifest = confirmatory_manifest(inputs)
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    source_sample = next(
        value
        for value in manifest.samples
        if value.label is WatermarkLabel.WATERMARKED
        and preregistration.watermark_tracks.track_for(
            value.watermark.watermark_config_hash
        ).matches_detector_identity(bayesian_bundle.detector_identity)
    )
    condition = next(
        value
        for value in condition_plan.conditions
        if value.schedule_policy is SchedulePolicy.RANDOM_VALID
        and value.calibration_bundle_hash == bayesian_bundle.bundle_hash
    )
    registry = default_transform_registry()
    enumeration = registry.enumerate(source_sample.text)
    schedule_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        budget_unit=condition.budget_unit,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    seed = 2718281828
    schedule_result = CandidateScheduler().schedule(
        schedule_input,
        condition.schedule_policy,
        condition.budget,
        seed,
    )
    transform_result = registry.apply(
        enumeration,
        schedule_result.selected_candidate_ids,
        seed,
    )
    transformed_tokens = TextOnlyTokenRecord.create(
        sha256_text(transform_result.output_text),
        source_sample.generation_tokens.continuation_token_ids,
        source_sample.model.identity_hash,
    )
    original_batch = build_native_observations(
        source_sample.sample_id,
        source_sample.generation_tokens.continuation_token_ids,
        source_sample.model.eos_token_id,
        adapter,
    )
    transformed_batch = build_native_observations(
        f"{source_sample.sample_id}:{condition.transform_condition_id}:transformed",
        transformed_tokens.token_ids,
        source_sample.model.eos_token_id,
        adapter,
    )
    original_evidence = bayesian_calibration_evidence(
        original_batch,
        artifacts.checkpoint,
        artifacts.readiness,
    )
    transformed_evidence = bayesian_calibration_evidence(
        transformed_batch,
        artifacts.checkpoint,
        artifacts.readiness,
    )
    original_result = apply_calibration(
        original_evidence,
        bayesian_bundle,
        condition.target_fpr,
    )
    transformed_result = apply_calibration(
        transformed_evidence,
        bayesian_bundle,
        condition.target_fpr,
    )
    arguments = {
        "preregistration": preregistration,
        "condition_plan": condition_plan,
        "corpus_manifest": manifest,
        "authorized_corpus_manifest_hash": manifest.manifest_hash,
        "source_sample": source_sample,
        "adapter": adapter,
        "transformed_tokens": transformed_tokens,
        "schedule_input": schedule_input,
        "schedule_result": schedule_result,
        "transform_result": transform_result,
        "original_batch": original_batch,
        "transformed_batch": transformed_batch,
        "original_evidence": original_evidence,
        "transformed_evidence": transformed_evidence,
        "calibration_bundle": bayesian_bundle,
        "original_detector_result": original_result,
        "transformed_detector_result": transformed_result,
        "condition_id": condition.condition_id,
        "expected_schedule_seed": seed,
        "worker_version": "bayesian-row-replay-test-v1",
        "environment_snapshot_hash": sha256_text("environment"),
        "authorization_hash": sha256_text("authorization"),
        "ledger_hash": sha256_text("ledger"),
        "timestamp_utc": "2026-08-16T21:30:00Z",
    }
    return arguments, artifacts


def test_bayesian_confirmatory_outcome_replay_binds_checkpoint_and_artifact_bundle() -> None:
    arguments, artifacts = _fixture()
    fields = build_confirmatory_outcome_fields(
        **arguments,
        bayesian_artifacts=artifacts,
    )
    detector = fields[10]
    audit = fields[12]
    assert detector.checkpoint_hash == artifacts.checkpoint.checkpoint_hash
    assert artifacts.bundle_hash in audit.artifact_hashes


def test_bayesian_confirmatory_outcome_replay_fails_closed_without_artifacts() -> None:
    arguments, _ = _fixture()
    with pytest.raises(Exception, match="readiness artifact"):
        build_confirmatory_outcome_fields(**arguments)
