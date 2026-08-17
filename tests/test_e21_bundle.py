import pytest

from test_e20_execution import T0, T1, T2, _sealed_execution_fixture
from test_e21_rerun import _rerun_manifest
from fuckmark.environment import capture_environment
from fuckmark.experiments.e20_bundle import _compatible_condition_ids
from fuckmark.experiments.e20_execution import complete_e20_run, create_e20_run_ledger, start_e20_run
from fuckmark.experiments.e20_rows import ExperimentReasonCode
from fuckmark.experiments.e21_bundle import (
    E21ResultBundleError,
    build_e21_result_bundle,
    verify_e21_result_bundle,
)
from fuckmark.experiments.e21_execution import create_e21_run_ledger, start_e21_run
from fuckmark.experiments.e21_rerun import authorize_e21_execution, build_e21_rerun_seal
from fuckmark.experiments.e21_rows import E21AuditFields, E21FailureRow, E21FailureStage, E21IdentityFields
from fuckmark.hashing import sha256_text


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
    ) = _sealed_execution_fixture()
    e20_ledger = create_e20_run_ledger(e20_authorization, T0)
    e20_ledger = start_e20_run(e20_ledger, T1)
    e20_ledger = complete_e20_run(e20_ledger, T2, sha256_text("e20-result-for-e21-bundle"))
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
        dependency_lock_hash=sha256_text("e21-bundle-lock"),
        worker_version="e21-bundle-test-worker-v1",
        shard_count=4,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    ledger = create_e21_run_ledger(authorization, "2026-08-16T21:00:00Z")
    ledger = start_e21_run(ledger, "2026-08-16T21:01:00Z")
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    failures = []
    for sample in e21_manifest.samples:
        condition_ids = _compatible_condition_ids(
            preregistration,
            condition_plan,
            sample.watermark.watermark_config_hash,
        )
        for condition_id in condition_ids:
            condition = condition_by_id[condition_id]
            detail_hash = sha256_text(f"e21-tokenization:{sample.sample_id}:{condition_id}")
            audit = E21AuditFields(
                authorization.worker_version,
                "2026-08-16T21:02:00Z",
                authorization.environment_snapshot_hash,
                authorization.authorization_hash,
                ledger.ledger_hash,
                tuple(sorted((sample.record_hash, condition.condition_hash, detail_hash))),
            )
            failures.append(
                E21FailureRow.create(
                    E21IdentityFields(
                        authorization.execution_id,
                        authorization.execution_id,
                        "E21",
                        condition_id,
                        sample.sample_id,
                        sample.match_id,
                    ),
                    E21FailureStage.TOKENIZATION,
                    ExperimentReasonCode.TOKENIZATION_FAILURE,
                    sample.record_hash,
                    detail_hash,
                    audit,
                )
            )
    return authorization, ledger, preregistration, e21_manifest, condition_plan, tuple(failures)


def test_e21_result_bundle_requires_exact_sealed_population() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (),
        failures,
    )
    assert bundle.expected_row_count == len(failures)
    assert bundle.observed_row_count == len(failures)
    assert bundle.outcome_row_count == 0
    assert bundle.failure_row_count == len(failures)
    verify_e21_result_bundle(
        bundle,
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
    )


def test_e21_result_bundle_rejects_missing_and_duplicate_rows() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    with pytest.raises(E21ResultBundleError, match="coverage mismatch"):
        build_e21_result_bundle(
            authorization,
            ledger,
            preregistration,
            manifest,
            condition_plan,
            (),
            failures[:-1],
        )
    with pytest.raises(E21ResultBundleError, match="duplicate sample and condition"):
        build_e21_result_bundle(
            authorization,
            ledger,
            preregistration,
            manifest,
            condition_plan,
            (),
            (*failures, failures[0]),
        )


def test_e21_result_bundle_rejects_wrong_started_ledger_binding() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    wrong = E21AuditFields(
        failures[0].audit.worker_version,
        failures[0].audit.timestamp_utc,
        failures[0].audit.environment_snapshot_hash,
        failures[0].audit.authorization_hash,
        sha256_text("different-e21-ledger"),
        failures[0].audit.artifact_hashes,
    )
    forged = E21FailureRow.create(
        failures[0].identity,
        failures[0].stage,
        failures[0].reason_code,
        failures[0].source_sample_record_hash,
        failures[0].detail_hash,
        wrong,
    )
    with pytest.raises(E21ResultBundleError, match="audit ledger"):
        build_e21_result_bundle(
            authorization,
            ledger,
            preregistration,
            manifest,
            condition_plan,
            (),
            (forged, *failures[1:]),
        )
