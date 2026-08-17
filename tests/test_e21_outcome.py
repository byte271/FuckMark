from test_e20_execution import T0, T1, T2, _authorize
from test_e21_rerun import _rerun_manifest
from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.corpus import TextOnlyTokenRecord, WatermarkLabel
from fuckmark.detectors import apply_calibration, mean_evidence
from fuckmark.environment import capture_environment
from fuckmark.experiments.e20_execution import complete_e20_run, create_e20_run_ledger, start_e20_run
from fuckmark.experiments.e21_execution import create_e21_run_ledger, start_e21_run
from fuckmark.experiments.e21_outcome import build_e21_outcome_row, verify_e21_outcome_row
from fuckmark.experiments.e21_rerun import authorize_e21_execution, build_e21_rerun_seal
from fuckmark.experiments.e21_seed import derive_e21_condition_seed
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations
from fuckmark.transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    default_transform_registry,
)


TIMESTAMP = "2026-08-16T21:20:00Z"


def _fixture():
    (
        e20_authorization,
        preregistration,
        condition_plan,
        _,
        e20_manifest,
        key_manifest,
        _,
        common,
    ) = _authorize()
    e20_ledger = create_e20_run_ledger(e20_authorization, T0)
    e20_ledger = start_e20_run(e20_ledger, T1)
    e20_ledger = complete_e20_run(e20_ledger, T2, sha256_text("e20-for-e21-outcome"))
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    authorization = authorize_e21_execution(
        seal,
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
        capture_environment(),
        serialized_test_key_material=common["serialized_test_key_material"],
        dependency_lock_hash=sha256_text("e21-outcome-lock"),
        worker_version="e21-outcome-test-worker-v1",
        shard_count=4,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    ledger = create_e21_run_ledger(authorization, "2026-08-16T21:18:00Z")
    ledger = start_e21_run(ledger, "2026-08-16T21:19:00Z")
    source_sample = next(
        value
        for value in e21_manifest.samples
        if value.label is WatermarkLabel.WATERMARKED
        and value.watermark.key_id == "test-key-0"
    )
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    calibration_bundle = next(
        value
        for value in preregistration.calibration_bundles
        if value.detector_identity.adapter_id == adapter.adapter_id
        and preregistration.watermark_tracks.track_for(
            source_sample.watermark.watermark_config_hash
        ).matches_detector_identity(value.detector_identity)
    )
    condition = next(
        value
        for value in condition_plan.conditions
        if value.schedule_policy is SchedulePolicy.RANDOM_VALID
        and value.calibration_bundle_hash == calibration_bundle.bundle_hash
    )
    registry = default_transform_registry()
    enumeration = registry.enumerate(source_sample.text)
    schedule_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        budget_unit=condition.budget_unit,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    seed = derive_e21_condition_seed(
        authorization,
        e21_manifest,
        source_sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
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
    original_evidence = mean_evidence(original_batch)
    transformed_evidence = mean_evidence(transformed_batch)
    original_result = apply_calibration(
        original_evidence,
        calibration_bundle,
        condition.target_fpr,
    )
    transformed_result = apply_calibration(
        transformed_evidence,
        calibration_bundle,
        condition.target_fpr,
    )
    return {
        "authorization": authorization,
        "ledger": ledger,
        "preregistration": preregistration,
        "condition_plan": condition_plan,
        "corpus_manifest": e21_manifest,
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
        "calibration_bundle": calibration_bundle,
        "original_detector_result": original_result,
        "transformed_detector_result": transformed_result,
        "condition_id": condition.condition_id,
        "timestamp_utc": TIMESTAMP,
    }


def test_e21_outcome_row_replays_from_fresh_seed_source_chain() -> None:
    artifacts = _fixture()
    row = build_e21_outcome_row(**artifacts)
    assert row.identity.experiment_id == "E21"
    assert row.identity.sample_id == artifacts["source_sample"].sample_id
    assert row.transform.schedule_seed == artifacts["schedule_result"].seed
    verify_e21_outcome_row(row, **artifacts)


def test_e21_outcome_rejects_e20_style_schedule_seed() -> None:
    artifacts = _fixture()
    wrong_schedule = CandidateScheduler().schedule(
        artifacts["schedule_input"],
        artifacts["schedule_result"].policy,
        artifacts["schedule_result"].budget,
        artifacts["schedule_result"].seed + 1,
    )
    registry = default_transform_registry()
    enumeration = registry.enumerate(artifacts["source_sample"].text)
    wrong_transform = registry.apply(
        enumeration,
        wrong_schedule.selected_candidate_ids,
        wrong_schedule.seed,
    )
    changed = dict(artifacts)
    changed["schedule_result"] = wrong_schedule
    changed["transform_result"] = wrong_transform
    try:
        build_e21_outcome_row(**changed)
    except ValueError as error:
        assert "seed" in str(error)
    else:
        raise AssertionError("E21 outcome accepted a non-derived schedule seed")
