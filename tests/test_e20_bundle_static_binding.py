from dataclasses import replace

import pytest

from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture
from fuckmark.experiments.e20_bundle import E20ResultBundleError, build_e20_result_bundle
from fuckmark.experiments.e20_rows import (
    E20AuditFields,
    E20DetectorFields,
    E20FailureRow,
    E20OutcomeRow,
)
from fuckmark.hashing import sha256_text


def _mixed_bundle_inputs():
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    chosen = condition_plan.conditions[0]
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    chosen_failures = tuple(
        value for value in failures if value.identity.condition_id == chosen.condition_id
    )
    outcomes = tuple(
        _outcome_for(
            authorization,
            preregistration,
            corpus_manifest,
            chosen,
            sample_by_id[value.identity.sample_id],
            value,
        )
        for value in chosen_failures
    )
    removed = {
        (value.identity.sample_id, value.identity.condition_id)
        for value in chosen_failures
    }
    remaining_failures = tuple(
        value
        for value in failures
        if (value.identity.sample_id, value.identity.condition_id) not in removed
    )
    build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        remaining_failures,
    )
    return (
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        remaining_failures,
    )


def test_result_bundle_rejects_rehashed_failure_with_wrong_source_record_hash() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    source = failures[0]
    forged = E20FailureRow.create(
        source.identity,
        source.stage,
        source.reason_code,
        sha256_text("forged-source-record"),
        source.detail_hash,
        source.audit,
    )
    with pytest.raises(E20ResultBundleError, match="source sample hash"):
        build_e20_result_bundle(
            authorization,
            preregistration,
            corpus_manifest,
            condition_plan,
            (),
            (forged, *failures[1:]),
        )


def test_result_bundle_rejects_rehashed_failure_from_wrong_authorization_audit() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    source = failures[0]
    forged_audit = E20AuditFields(
        source.audit.worker_version,
        source.audit.timestamp_utc,
        source.audit.environment_snapshot_hash,
        sha256_text("different-authorization"),
        source.audit.ledger_hash,
        source.audit.artifact_hashes,
    )
    forged = E20FailureRow.create(
        source.identity,
        source.stage,
        source.reason_code,
        source.source_sample_record_hash,
        source.detail_hash,
        forged_audit,
    )
    with pytest.raises(E20ResultBundleError, match="audit authorization"):
        build_e20_result_bundle(
            authorization,
            preregistration,
            corpus_manifest,
            condition_plan,
            (),
            (forged, *failures[1:]),
        )


def test_result_bundle_rejects_self_consistent_outcome_with_unsealed_threshold() -> None:
    (
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        failures,
    ) = _mixed_bundle_inputs()
    source = outcomes[0]
    forged_threshold = 0.123456789
    if forged_threshold == source.detector.threshold_value:
        forged_threshold = 0.234567891
    scale = source.detector.robust_scale
    pristine = source.detector.pristine_raw_score
    transformed = source.detector.transformed_raw_score
    operator = source.detector.comparison_operator
    if operator.value == ">=":
        pristine_decision = pristine >= forged_threshold
        transformed_decision = transformed >= forged_threshold
    else:
        pristine_decision = pristine > forged_threshold
        transformed_decision = transformed > forged_threshold
    forged_detector = E20DetectorFields(
        source.detector.detector_family,
        source.detector.detector_config_hash,
        source.detector.checkpoint_hash,
        source.detector.calibration_bundle_hash,
        sha256_text("forged-unsealed-threshold"),
        operator,
        source.detector.target_fpr,
        forged_threshold,
        scale,
        pristine,
        transformed,
        (pristine - forged_threshold) / scale,
        (transformed - forged_threshold) / scale,
        pristine_decision,
        transformed_decision,
    )
    forged = E20OutcomeRow.create(
        source.identity,
        source.source,
        source.model,
        source.watermark,
        source.generation,
        source.text,
        source.transform,
        source.fidelity,
        source.alignment,
        source.observation,
        source.gvalues,
        forged_detector,
        source.statistics,
        source.audit,
    )
    with pytest.raises(E20ResultBundleError, match="threshold"):
        build_e20_result_bundle(
            authorization,
            preregistration,
            corpus_manifest,
            condition_plan,
            (forged, *outcomes[1:]),
            failures,
        )
