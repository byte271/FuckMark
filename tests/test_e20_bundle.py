from dataclasses import replace

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.environment import capture_environment
from fuckmark.experiments import authorize_e20_execution
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_corpus import build_confirmatory_corpus_seal
from fuckmark.experiments.e20_bundle import (
    E20ReasonCount,
    E20ResultBundle,
    E20ResultBundleError,
    build_e20_result_bundle,
    verify_e20_result_bundle,
)
from fuckmark.experiments.e20_execution import create_e20_run_ledger, start_e20_run
from fuckmark.experiments.e20_failure_verification import build_e20_failure_row
from fuckmark.experiments.e20_rows import (
    E20FailureRow,
    E20FailureStage,
    E20IdentityFields,
    ExperimentReasonCode,
)
from fuckmark.hashing import sha256_json, sha256_text


TIMESTAMP = "2026-08-16T20:50:00Z"


def _bundle_fixture():
    inputs = preregistration_inputs(final_n_per_core_cell=1)
    condition_plan = confirmatory_condition_plan(calibration_bundles=inputs.calibration_bundles)
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
        dependency_lock_hash=sha256_text("bundle-test-lock"),
        worker_version="e20-bundle-test-worker-v1",
        shard_count=4,
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
    ledger = start_e20_run(
        create_e20_run_ledger(authorization, "2026-08-16T20:49:00Z"),
        "2026-08-16T20:49:30Z",
    )
    failures = []
    for sample in corpus_manifest.samples:
        for condition in condition_plan.conditions:
            failures.append(
                build_e20_failure_row(
                    authorization,
                    ledger,
                    preregistration,
                    condition_plan,
                    corpus_manifest,
                    sample,
                    condition_id=condition.condition_id,
                    stage=E20FailureStage.TOKENIZATION,
                    reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
                    detail_hash=sha256_text(
                        f"tokenization-failure:{sample.sample_id}:{condition.condition_id}"
                    ),
                    timestamp_utc=TIMESTAMP,
                )
            )
    return authorization, corpus_manifest, condition_plan, tuple(failures)


def _reason_count(bundle, reason):
    return next(value.count for value in bundle.reason_counts if value.reason_code is reason)


def test_result_bundle_requires_exact_full_sample_by_evaluation_condition_population() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    bundle = build_e20_result_bundle(
        authorization,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    assert len(corpus_manifest.samples) == 80
    assert len(condition_plan.conditions) == 6
    assert bundle.expected_row_count == 480
    assert bundle.observed_row_count == 480
    assert bundle.outcome_row_count == 0
    assert bundle.failure_row_count == 480
    assert _reason_count(bundle, ExperimentReasonCode.TOKENIZATION_FAILURE) == 480
    assert _reason_count(bundle, ExperimentReasonCode.OK) == 0
    assert len(bundle.reason_counts) == len(ExperimentReasonCode)
    verify_e20_result_bundle(bundle, authorization, corpus_manifest, condition_plan)


def test_result_bundle_rejects_one_missing_row_instead_of_silent_drop() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    with pytest.raises(E20ResultBundleError, match="coverage mismatch"):
        build_e20_result_bundle(
            authorization,
            corpus_manifest,
            condition_plan,
            (),
            failures[:-1],
        )


def test_result_bundle_rejects_duplicate_sample_condition_row() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    with pytest.raises(E20ResultBundleError, match="duplicate sample and condition"):
        build_e20_result_bundle(
            authorization,
            corpus_manifest,
            condition_plan,
            (),
            (*failures, failures[0]),
        )


def test_result_bundle_rejects_extra_unsealed_condition() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    source = failures[0]
    forged_identity = E20IdentityFields(
        source.identity.execution_id,
        source.identity.run_id,
        source.identity.experiment_id,
        "not-a-sealed-condition",
        source.identity.sample_id,
        source.identity.pair_id,
    )
    extra = E20FailureRow.create(
        forged_identity,
        source.stage,
        source.reason_code,
        source.source_sample_record_hash,
        source.detail_hash,
        source.audit,
    )
    with pytest.raises(E20ResultBundleError, match="coverage mismatch"):
        build_e20_result_bundle(
            authorization,
            corpus_manifest,
            condition_plan,
            (),
            (*failures, extra),
        )


def test_result_bundle_rejects_row_from_different_execution() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    source = failures[0]
    forged_execution = sha256_text("different-e20-execution")
    forged_identity = E20IdentityFields(
        forged_execution,
        forged_execution,
        source.identity.experiment_id,
        source.identity.condition_id,
        source.identity.sample_id,
        source.identity.pair_id,
    )
    forged = E20FailureRow.create(
        forged_identity,
        source.stage,
        source.reason_code,
        source.source_sample_record_hash,
        source.detail_hash,
        source.audit,
    )
    with pytest.raises(E20ResultBundleError, match="different sealed execution"):
        build_e20_result_bundle(
            authorization,
            corpus_manifest,
            condition_plan,
            (),
            (forged, *failures[1:]),
        )


def test_result_bundle_rejects_rehashed_forged_reason_counts() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    bundle = build_e20_result_bundle(
        authorization,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    bad_counts = tuple(
        E20ReasonCount(
            value.reason_code,
            value.count - 1 if value.reason_code is ExperimentReasonCode.TOKENIZATION_FAILURE else (
                value.count + 1 if value.reason_code is ExperimentReasonCode.DETECTOR_SCORE_NA else value.count
            ),
        )
        for value in bundle.reason_counts
    )
    payload = bundle._payload()
    payload["reason_counts"] = bad_counts
    with pytest.raises(ValueError, match="do not replay"):
        E20ResultBundle(
            bundle.algorithm_version,
            bundle.execution_id,
            bundle.authorization_hash,
            bundle.corpus_manifest_hash,
            bundle.condition_plan_hash,
            bundle.outcome_rows,
            bundle.failure_rows,
            bad_counts,
            bundle.expected_row_count,
            bundle.observed_row_count,
            bundle.outcome_row_count,
            bundle.failure_row_count,
            sha256_json(payload),
        )
