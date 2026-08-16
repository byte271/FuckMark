from dataclasses import replace
from functools import lru_cache

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.corpus import KeySplit
from fuckmark.detectors import ComparisonOperator, DetectorFamily
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
    E20AlignmentFields,
    E20DetectorFields,
    E20FailureRow,
    E20FailureStage,
    E20FidelityFields,
    E20GValueFields,
    E20GenerationFields,
    E20HumanFidelityStatus,
    E20IdentityFields,
    E20ModelFields,
    E20ObservationFields,
    E20OutcomeRow,
    E20SourceFields,
    E20StatisticsFields,
    E20TextFields,
    E20TransformFields,
    E20WatermarkFields,
    ExperimentReasonCode,
)
from fuckmark.hashing import sha256_json, sha256_text


TIMESTAMP = "2026-08-16T20:50:00Z"


@lru_cache(maxsize=1)
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


def _synthetic_outcome(failure, condition, *, transformed_hash, transform_suffix="shared"):
    identity = E20IdentityFields(
        failure.identity.execution_id,
        failure.identity.run_id,
        failure.identity.experiment_id,
        condition.condition_id,
        failure.identity.sample_id,
        failure.identity.pair_id,
    )
    schedule_seed = int(sha256_text(condition.transform_condition_id)[:16], 16)
    return E20OutcomeRow.create(
        identity,
        E20SourceFields("test-adapter", "a" * 40, sha256_text("adapter-config")),
        E20ModelFields("example/model", "b" * 40, "example/tokenizer", "c" * 40),
        E20WatermarkFields(sha256_text("watermark-config"), KeySplit.TEST, "test-key-0"),
        E20GenerationFields(7, 0.8, 40, 0.95, 8),
        E20TextFields(
            sha256_text(f"source:{failure.identity.sample_id}"),
            transformed_hash,
            100,
            98,
            20,
            20,
            8,
            8,
        ),
        E20TransformFields(
            sha256_text("ruleset"),
            condition.schedule_policy,
            schedule_seed,
            condition.budget,
            condition.budget_unit,
            1,
            sha256_text(f"candidate-pool:{condition.transform_condition_id}"),
            sha256_text(f"scheduler-input:{condition.transform_condition_id}"),
            sha256_text(f"schedule-result:{condition.transform_condition_id}:{transform_suffix}"),
            sha256_text(f"operation-trace:{condition.transform_condition_id}:{transform_suffix}"),
            True,
        ),
        E20FidelityFields(
            True,
            (ExperimentReasonCode.OK,),
            2,
            1,
            1,
            E20HumanFidelityStatus.NOT_SELECTED,
            None,
        ),
        E20AlignmentFields("canonical-token-levenshtein-v1", sha256_text("edit-script"), 0),
        E20ObservationFields(6, 6, 5, 1, 0, 0, 0, 0),
        E20GValueFields(3, sha256_text("per-depth-summary"), 6, 1),
        E20DetectorFields(
            DetectorFamily.MEAN,
            sha256_text(f"detector-config:{condition.calibration_bundle_hash}"),
            None,
            condition.calibration_bundle_hash,
            sha256_text(f"threshold:{condition.calibration_bundle_hash}:{condition.target_fpr}"),
            ComparisonOperator.GREATER_THAN_OR_EQUAL,
            condition.target_fpr,
            0.5,
            0.1,
            0.8,
            0.7,
            3.0,
            2.0,
            True,
            True,
        ),
        E20StatisticsFields(
            sha256_text("synthetic-stratum"),
            failure.identity.sample_id,
            condition.hypothesis_class,
        ),
        failure.audit,
    )


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


def test_result_bundle_requires_shared_transform_across_detector_evaluations() -> None:
    authorization, corpus_manifest, condition_plan, failures = _bundle_fixture()
    sample_id = failures[0].identity.sample_id
    conditions = tuple(
        value
        for value in condition_plan.conditions
        if value.transform_condition_id == condition_plan.conditions[0].transform_condition_id
    )
    assert len(conditions) == 2
    failure_by_key = {(value.identity.sample_id, value.identity.condition_id): value for value in failures}
    first_failure = failure_by_key[(sample_id, conditions[0].condition_id)]
    second_failure = failure_by_key[(sample_id, conditions[1].condition_id)]
    transformed_hash = sha256_text("shared transformed text")
    first = _synthetic_outcome(first_failure, conditions[0], transformed_hash=transformed_hash)
    second = _synthetic_outcome(second_failure, conditions[1], transformed_hash=transformed_hash)
    removed = {
        (sample_id, conditions[0].condition_id),
        (sample_id, conditions[1].condition_id),
    }
    remaining = tuple(
        value
        for value in failures
        if (value.identity.sample_id, value.identity.condition_id) not in removed
    )
    bundle = build_e20_result_bundle(
        authorization,
        corpus_manifest,
        condition_plan,
        (first, second),
        remaining,
    )
    assert bundle.outcome_row_count == 2
    assert bundle.failure_row_count == 478
    inconsistent = _synthetic_outcome(
        second_failure,
        conditions[1],
        transformed_hash=sha256_text("different transformed text"),
        transform_suffix="different",
    )
    with pytest.raises(E20ResultBundleError, match="changed the frozen transform"):
        build_e20_result_bundle(
            authorization,
            corpus_manifest,
            condition_plan,
            (first, inconsistent),
            remaining,
        )
