from types import SimpleNamespace

import pytest

from test_e20_bundle import _bundle_fixture, _synthetic_outcome
from fuckmark.experiments.confirmatory_detector_readiness import build_confirmatory_detector_readiness
from fuckmark.experiments.e20_aggregate import build_e20_aggregate_bundle
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_inference import build_e20_inference_bundle
from fuckmark.experiments.e20_key_analysis import build_e20_key_analysis_bundle
from fuckmark.experiments.e20_report import (
    E20ConfirmatoryReport,
    E20ReportStatus,
    _human_fidelity_summary,
    build_e20_confirmatory_report,
    verify_e20_confirmatory_report,
)
from fuckmark.experiments.e20_rows import ExperimentReasonCode
from fuckmark.hashing import sha256_json, sha256_text


def _failure_only_report_fixture():
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    key_analysis = build_e20_key_analysis_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    inference = build_e20_inference_bundle(
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    readiness = build_confirmatory_detector_readiness(preregistration)
    report = build_e20_confirmatory_report(
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    return (
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        report,
        failures,
    )


def test_report_blocks_confirmatory_claims_when_detector_readiness_is_incomplete() -> None:
    (
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        report,
        _,
    ) = _failure_only_report_fixture()
    assert readiness.ready_for_e20 is False
    assert report.status is E20ReportStatus.BLOCKED_DETECTOR_READINESS
    assert report.human_fidelity.reviewed_transform_count == 0
    assert report.human_fidelity.gate_passed is False
    assert all(value.headline_eligible is False for value in report.headlines)
    tokenization_failures = next(
        value.count
        for value in report.reason_counts
        if value.reason_code is ExperimentReasonCode.TOKENIZATION_FAILURE
    )
    assert tokenization_failures == result_bundle.failure_row_count
    verify_e20_confirmatory_report(
        report,
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )


def test_report_replay_rejects_rehashed_wrong_overall_status() -> None:
    (
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        report,
        _,
    ) = _failure_only_report_fixture()
    payload = report._payload()
    payload["status"] = E20ReportStatus.BLOCKED_FIDELITY_AUDIT.value
    forged = E20ConfirmatoryReport(
        report.algorithm_version,
        report.execution_id,
        report.result_bundle_hash,
        report.aggregate_hash,
        report.key_analysis_hash,
        report.inference_hash,
        report.detector_readiness_hash,
        report.human_fidelity,
        report.reason_counts,
        report.headlines,
        E20ReportStatus.BLOCKED_FIDELITY_AUDIT,
        sha256_json(payload),
    )
    with pytest.raises(ValueError, match="does not replay exactly"):
        verify_e20_confirmatory_report(
            forged,
            result_bundle,
            aggregate,
            key_analysis,
            inference,
            readiness,
            preregistration,
            corpus_manifest,
            condition_plan,
            authorization,
        )


def test_human_fidelity_summary_deduplicates_detector_evaluations_of_same_transform() -> None:
    _, preregistration, _, condition_plan, failures = _bundle_fixture()
    first_condition = condition_plan.conditions[0]
    peer_condition = next(
        value
        for value in condition_plan.conditions
        if value.transform_condition_id == first_condition.transform_condition_id
        and value.condition_id != first_condition.condition_id
    )
    failure = failures[0]
    transformed_hash = sha256_text("shared-transform-for-human-audit")
    first = _synthetic_outcome(
        failure,
        first_condition,
        transformed_hash=transformed_hash,
    )
    second = _synthetic_outcome(
        failure,
        peer_condition,
        transformed_hash=transformed_hash,
    )
    summary = _human_fidelity_summary(
        SimpleNamespace(outcome_rows=(first, second), failure_rows=()),
        condition_plan,
        preregistration,
    )
    assert summary.unique_transform_count == 1
    assert summary.reviewed_transform_count == 0
    assert summary.gate_passed is False
