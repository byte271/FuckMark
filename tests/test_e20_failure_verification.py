from dataclasses import replace

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.corpus import WatermarkLabel
from fuckmark.environment import capture_environment
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_corpus import build_confirmatory_corpus_seal
from fuckmark.experiments.e20_authorization import _authorize_e20_execution_unchecked as authorize_e20_execution
from fuckmark.experiments.e20_execution import create_e20_run_ledger, start_e20_run
from fuckmark.experiments.e20_failure_verification import (
    E20FailureVerificationError,
    build_e20_failure_row,
    verify_e20_failure_row,
)
from fuckmark.experiments.e20_rows import E20FailureStage, ExperimentReasonCode
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy


TIMESTAMP = "2026-08-16T20:40:00Z"


def _failure_fixture(started: bool = True):
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    condition_plan = confirmatory_condition_plan()
    corpus_manifest = confirmatory_manifest(inputs)
    key_manifest = confirmatory_test_key_manifest(inputs)
    inputs = replace(
        inputs,
        sealed_test_key_hash=key_manifest.manifest_hash,
        sealed_test_corpus_hash=corpus_manifest.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    seal = build_confirmatory_corpus_seal(preregistration, corpus_manifest, key_manifest)
    _, calibration_evidence = calibration_materials()
    secret_by_key = {
        "test-key-0": b"secret-test-key-0",
        "test-key-1": b"secret-test-key-1",
    }
    authorization = authorize_e20_execution(
        preregistration,
        condition_plan,
        seal,
        corpus_manifest,
        key_manifest,
        capture_environment(),
        serialized_test_key_material={
            entry.entry_hash: secret_by_key[entry.key_id] for entry in key_manifest.entries
        },
        dependency_lock_hash=sha256_text("failure-test-lock"),
        worker_version="e20-failure-test-worker-v1",
        shard_count=2,
        dirty_worktree=False,
        output_namespace_available=True,
        prior_ledgers=(),
        code_commit=preregistration.code_commit,
        spec_revision_hash=preregistration.spec_revision_hash,
        power_analysis_hash=preregistration.power_analysis_hash,
        verification_test_hashes=preregistration.verification_test_hashes,
        model_tokenizers=preregistration.model_tokenizers,
        calibration_negative_evidence=calibration_evidence,
    )
    ledger = create_e20_run_ledger(authorization, "2026-08-16T20:39:00Z")
    if started:
        ledger = start_e20_run(ledger, "2026-08-16T20:39:30Z")
    condition = next(
        value
        for value in condition_plan.conditions
        if value.schedule_policy is SchedulePolicy.RANDOM_VALID
    )
    source_sample = next(
        value
        for value in corpus_manifest.samples
        if value.label is WatermarkLabel.WATERMARKED
    )
    return {
        "authorization": authorization,
        "ledger": ledger,
        "preregistration": preregistration,
        "condition_plan": condition_plan,
        "corpus_manifest": corpus_manifest,
        "source_sample": source_sample,
        "condition_id": condition.condition_id,
        "stage": E20FailureStage.TOKENIZATION,
        "reason_code": ExperimentReasonCode.TOKENIZATION_FAILURE,
        "detail_hash": sha256_text("tokenizer failure details"),
        "timestamp_utc": TIMESTAMP,
    }


def test_e20_failure_row_replays_from_started_sealed_execution() -> None:
    artifacts = _failure_fixture()
    row = build_e20_failure_row(**artifacts)
    assert row.reason_code is ExperimentReasonCode.TOKENIZATION_FAILURE
    assert row.stage is E20FailureStage.TOKENIZATION
    assert row.source_sample_record_hash == artifacts["source_sample"].record_hash
    assert row.detail_hash in row.audit.artifact_hashes
    verify_e20_failure_row(row, **artifacts)


def test_e20_failure_row_source_replay_rejects_different_detail_evidence() -> None:
    artifacts = _failure_fixture()
    row = build_e20_failure_row(**artifacts)
    changed = dict(artifacts)
    changed["detail_hash"] = sha256_text("different detail evidence")
    with pytest.raises(E20FailureVerificationError, match="does not replay exactly"):
        verify_e20_failure_row(row, **changed)


def test_e20_failure_row_source_replay_rejects_different_source_sample() -> None:
    artifacts = _failure_fixture()
    row = build_e20_failure_row(**artifacts)
    changed = dict(artifacts)
    changed["source_sample"] = next(
        value
        for value in artifacts["corpus_manifest"].samples
        if value.sample_id != artifacts["source_sample"].sample_id
    )
    with pytest.raises(E20FailureVerificationError, match="does not replay exactly"):
        verify_e20_failure_row(row, **changed)


def test_e20_failure_row_cannot_be_written_before_run_starts() -> None:
    artifacts = _failure_fixture(started=False)
    with pytest.raises(E20FailureVerificationError, match="only while the sealed run is STARTED"):
        build_e20_failure_row(**artifacts)


def test_e20_failure_row_rejects_unsealed_condition() -> None:
    artifacts = _failure_fixture()
    artifacts["condition_id"] = "not-a-sealed-condition"
    with pytest.raises(KeyError):
        build_e20_failure_row(**artifacts)


def test_e20_failure_row_rejects_reason_stage_mismatch() -> None:
    artifacts = _failure_fixture()
    artifacts["stage"] = E20FailureStage.DETECTOR
    with pytest.raises(ValueError, match="required failure stage"):
        build_e20_failure_row(**artifacts)
