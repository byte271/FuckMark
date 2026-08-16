from dataclasses import replace

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.corpus import TextOnlyTokenRecord, WatermarkLabel
from fuckmark.detectors import apply_calibration, mean_evidence
from fuckmark.environment import capture_environment
from fuckmark.experiments import (
    E20RowVerificationError,
    authorize_e20_execution,
    build_e20_outcome_row,
    verify_e20_outcome_row,
)
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_corpus import build_confirmatory_corpus_seal
from fuckmark.experiments.e20_execution import (
    create_e20_run_ledger,
    derive_e20_condition_seed,
    start_e20_run,
)
from fuckmark.experiments.e20_rows import E20OutcomeRow, E20StatisticsFields, ExperimentReasonCode
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import CandidateScheduler, KeyBlindScheduleInput, ScheduleGeometryMode, SchedulePolicy, default_transform_registry

TIMESTAMP = "2026-08-16T20:30:00Z"


def _fixture():
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    condition_plan = confirmatory_condition_plan(calibration_bundles=inputs.calibration_bundles)
    corpus_manifest = confirmatory_manifest(inputs)
    key_manifest = confirmatory_test_key_manifest(inputs)
    inputs = replace(inputs, sealed_test_key_hash=key_manifest.manifest_hash, sealed_test_corpus_hash=corpus_manifest.manifest_hash)
    preregistration = create_confirmatory_preregistration(inputs)
    corpus_seal = build_confirmatory_corpus_seal(preregistration, corpus_manifest, key_manifest)
    _, calibration_evidence = calibration_materials()
    secret_by_key_id = {"test-key-0": b"secret-test-key-0", "test-key-1": b"secret-test-key-1"}
    authorization = authorize_e20_execution(
        preregistration, condition_plan, corpus_seal, corpus_manifest, key_manifest, capture_environment(),
        serialized_test_key_material={entry.entry_hash: secret_by_key_id[entry.key_id] for entry in key_manifest.entries},
        dependency_lock_hash=sha256_text("test-lockfile-v1"), worker_version="e20-row-test-worker-v1", shard_count=4,
        dirty_worktree=False, output_namespace_available=True, prior_ledgers=(), code_commit=preregistration.code_commit,
        spec_revision_hash=preregistration.spec_revision_hash, power_analysis_hash=preregistration.power_analysis_hash,
        verification_test_hashes=preregistration.verification_test_hashes, model_tokenizers=preregistration.model_tokenizers,
        calibration_negative_evidence=calibration_evidence,
    )
    ledger = start_e20_run(create_e20_run_ledger(authorization, "2026-08-16T20:29:00Z"), "2026-08-16T20:29:30Z")
    source_sample = next(value for value in corpus_manifest.samples if value.label is WatermarkLabel.WATERMARKED and value.watermark.key_id == "test-key-0")
    adapter = DeepMindReferenceAdapter(DeepMindReferenceConfig(ngram_len=3, keys=(11, 22, 33), context_history_size=8))
    calibration_bundle = next(value for value in preregistration.calibration_bundles if value.detector_identity.adapter_id == adapter.adapter_id)
    condition = next(value for value in condition_plan.conditions if value.schedule_policy is SchedulePolicy.RANDOM_VALID and value.calibration_bundle_hash == calibration_bundle.bundle_hash)
    registry = default_transform_registry()
    enumeration = registry.enumerate(source_sample.text)
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration, budget_unit=condition.budget_unit, geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC)
    seed = derive_e20_condition_seed(authorization, corpus_manifest, source_sample.sample_id, condition.transform_condition_id, "schedule")
    schedule_result = CandidateScheduler().schedule(scheduler_input, condition.schedule_policy, condition.budget, seed)
    assert schedule_result.selected_candidate_ids == ()
    transform_result = registry.apply(enumeration, schedule_result.selected_candidate_ids, seed)
    transformed_tokens = TextOnlyTokenRecord.create(source_sample.text_sha256, source_sample.generation_tokens.continuation_token_ids, source_sample.model.identity_hash)
    original_batch = build_native_observations(source_sample.sample_id, source_sample.generation_tokens.continuation_token_ids, source_sample.model.eos_token_id, adapter)
    transformed_batch = build_native_observations(f"{source_sample.sample_id}:{condition.transform_condition_id}:transformed", transformed_tokens.token_ids, source_sample.model.eos_token_id, adapter)
    original_evidence = mean_evidence(original_batch)
    transformed_evidence = mean_evidence(transformed_batch)
    original_detector_result = apply_calibration(original_evidence, calibration_bundle, condition.target_fpr)
    transformed_detector_result = apply_calibration(transformed_evidence, calibration_bundle, condition.target_fpr)
    return {
        "authorization": authorization, "ledger": ledger, "preregistration": preregistration, "condition_plan": condition_plan,
        "corpus_manifest": corpus_manifest, "source_sample": source_sample, "adapter": adapter, "transformed_tokens": transformed_tokens,
        "schedule_input": scheduler_input, "schedule_result": schedule_result, "transform_result": transform_result,
        "original_batch": original_batch, "transformed_batch": transformed_batch, "original_evidence": original_evidence,
        "transformed_evidence": transformed_evidence, "calibration_bundle": calibration_bundle,
        "original_detector_result": original_detector_result, "transformed_detector_result": transformed_detector_result,
        "condition_id": condition.condition_id, "timestamp_utc": TIMESTAMP,
    }


def test_no_eligible_e20_row_replays_from_full_source_artifact_chain() -> None:
    artifacts = _fixture()
    row = build_e20_outcome_row(**artifacts)
    assert row.fidelity.reason_codes == (ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM,)
    assert row.transform.eligible is False
    assert row.observation.replaced_count == 0
    assert row.gvalues.hamming_difference_count == 0
    assert row.detector.pristine_raw_score == row.detector.transformed_raw_score
    verify_e20_outcome_row(row, **artifacts)


def test_detector_evaluation_conditions_share_transform_seed() -> None:
    artifacts = _fixture()
    current = artifacts["condition_plan"].condition(artifacts["condition_id"])
    other = next(value for value in artifacts["condition_plan"].conditions if value.schedule_policy is current.schedule_policy and value.calibration_bundle_hash != current.calibration_bundle_hash)
    assert current.transform_condition_id == other.transform_condition_id
    first = derive_e20_condition_seed(artifacts["authorization"], artifacts["corpus_manifest"], artifacts["source_sample"].sample_id, current.transform_condition_id, "schedule")
    second = derive_e20_condition_seed(artifacts["authorization"], artifacts["corpus_manifest"], artifacts["source_sample"].sample_id, other.transform_condition_id, "schedule")
    assert first == second


def test_public_outcome_rejects_runtime_bundle_different_from_sealed_condition() -> None:
    artifacts = _fixture()
    current = artifacts["condition_plan"].condition(artifacts["condition_id"])
    wrong_condition = next(value for value in artifacts["condition_plan"].conditions if value.schedule_policy is current.schedule_policy and value.calibration_bundle_hash != current.calibration_bundle_hash)
    changed = dict(artifacts)
    changed["condition_id"] = wrong_condition.condition_id
    with pytest.raises(E20RowVerificationError, match="detector bundle frozen"):
        build_e20_outcome_row(**changed)


def test_source_replay_rejects_internally_valid_rehashed_row_with_wrong_bootstrap_group() -> None:
    artifacts = _fixture()
    row = build_e20_outcome_row(**artifacts)
    forged = E20OutcomeRow.create(row.identity, row.source, row.model, row.watermark, row.generation, row.text, row.transform, row.fidelity, row.alignment, row.observation, row.gvalues, row.detector, E20StatisticsFields(row.statistics.stratum_id, "wrong-bootstrap-group", row.statistics.hypothesis_class), row.audit)
    with pytest.raises(E20RowVerificationError, match="does not replay exactly"):
        verify_e20_outcome_row(forged, **artifacts)


def test_source_replay_rejects_schedule_seed_not_derived_from_sealed_execution() -> None:
    artifacts = _fixture()
    wrong_schedule = CandidateScheduler().schedule(artifacts["schedule_input"], artifacts["schedule_result"].policy, artifacts["schedule_result"].budget, artifacts["schedule_result"].seed + 1)
    registry = default_transform_registry()
    wrong_transform = registry.apply(registry.enumerate(artifacts["source_sample"].text), wrong_schedule.selected_candidate_ids, wrong_schedule.seed)
    changed = dict(artifacts)
    changed["schedule_result"] = wrong_schedule
    changed["transform_result"] = wrong_transform
    with pytest.raises(E20RowVerificationError, match="deterministic transform seed derivation"):
        build_e20_outcome_row(**changed)


def test_source_replay_rejects_transformed_batch_without_transform_bound_identity() -> None:
    artifacts = _fixture()
    wrong_batch = build_native_observations("wrong-transformed-id", artifacts["transformed_tokens"].token_ids, artifacts["source_sample"].model.eos_token_id, artifacts["adapter"])
    changed = dict(artifacts)
    changed["transformed_batch"] = wrong_batch
    changed["transformed_evidence"] = mean_evidence(wrong_batch)
    changed["transformed_detector_result"] = apply_calibration(changed["transformed_evidence"], artifacts["calibration_bundle"], artifacts["original_detector_result"].target_fpr)
    with pytest.raises(E20RowVerificationError, match="canonical transform-bound identity"):
        build_e20_outcome_row(**changed)
