from dataclasses import replace

import pytest

from test_e20_execution import T0, T1, T2, _authorize
from test_e21_rerun import _rerun_manifest
from fuckmark.environment import capture_environment
from fuckmark.experiments.e20_bundle import E20ReasonCount
from fuckmark.experiments.e20_execution import complete_e20_run, create_e20_run_ledger, start_e20_run
from fuckmark.experiments.e20_report import (
    E20_REPORT_ALGORITHM_VERSION,
    E20ConfirmatoryReport,
    E20HeadlineCondition,
    E20HumanFidelitySummary,
    E20ReportStatus,
)
from fuckmark.experiments.e20_rows import ExperimentReasonCode
from fuckmark.experiments.e21_execution import complete_e21_run, create_e21_run_ledger, start_e21_run
from fuckmark.experiments.e21_replication import (
    E21HeadlineEvidence,
    E21ReplicationError,
    E21ReplicationStatus,
    build_e21_replication_comparison,
    verify_e21_replication_comparison,
)
from fuckmark.experiments.e21_rerun import authorize_e21_execution, build_e21_rerun_seal
from fuckmark.hashing import sha256_json, sha256_text


def _human_summary():
    payload = {
        "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
        "unique_transform_count": 0,
        "reviewed_transform_count": 0,
        "equivalent_or_minor_count": 0,
        "material_change_count": 0,
        "cannot_judge_count": 0,
        "hard_invariant_failure_count": 0,
        "equivalent_or_minor_rate": None,
        "equivalent_or_minor_interval": None,
        "audit_verified": False,
        "selection_hash": None,
        "audit_hash": None,
        "gate_passed": False,
    }
    return E20HumanFidelitySummary(
        0,
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        False,
        None,
        None,
        False,
        sha256_json(payload),
    )


def _headline(condition, index: int):
    payload = {
        "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
        "condition_id": condition.condition_id,
        "calibration_bundle_hash": condition.calibration_bundle_hash,
        "target_fpr": condition.target_fpr,
        "expected_row_count": 1,
        "failure_row_count": 0,
        "tpr_change": -0.2 - index * 0.01,
        "tpr_change_ci_lower": -0.3 - index * 0.01,
        "tpr_change_ci_upper": -0.1 - index * 0.01,
        "transformed_tpr": 0.6 - index * 0.01,
        "standardized_margin_drop": 1.2 + index * 0.01,
        "coverage_efficiency": 2.0 + index * 0.01,
        "decision_loss_rate": 0.3 + index * 0.01,
        "holm_adjusted_p_value": 0.01,
        "key_summary_hash": sha256_text(f"key-summary:{condition.condition_id}"),
        "headline_eligible": True,
    }
    return E20HeadlineCondition(
        condition.condition_id,
        condition.calibration_bundle_hash,
        condition.target_fpr,
        1,
        0,
        payload["tpr_change"],
        payload["tpr_change_ci_lower"],
        payload["tpr_change_ci_upper"],
        payload["transformed_tpr"],
        payload["standardized_margin_drop"],
        payload["coverage_efficiency"],
        payload["decision_loss_rate"],
        payload["holm_adjusted_p_value"],
        payload["key_summary_hash"],
        True,
        sha256_json(payload),
    )


def _e20_report(authorization, condition_plan):
    headlines = tuple(sorted(
        (_headline(condition, index) for index, condition in enumerate(condition_plan.conditions)),
        key=lambda value: value.condition_id,
    ))
    reason_counts = tuple(E20ReasonCount(reason, 0) for reason in ExperimentReasonCode)
    payload = {
        "algorithm_version": E20_REPORT_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "result_bundle_hash": sha256_text("e20-replication-result-bundle"),
        "aggregate_hash": sha256_text("e20-replication-aggregate"),
        "key_analysis_hash": sha256_text("e20-replication-key-analysis"),
        "inference_hash": sha256_text("e20-replication-inference"),
        "detector_readiness_hash": sha256_text("e20-replication-readiness"),
        "human_fidelity": _human_summary(),
        "reason_counts": reason_counts,
        "headlines": headlines,
        "status": E20ReportStatus.CONFIRMATORY_EVALUABLE.value,
    }
    return E20ConfirmatoryReport(
        E20_REPORT_ALGORITHM_VERSION,
        authorization.execution_id,
        payload["result_bundle_hash"],
        payload["aggregate_hash"],
        payload["key_analysis_hash"],
        payload["inference_hash"],
        payload["detector_readiness_hash"],
        payload["human_fidelity"],
        reason_counts,
        headlines,
        E20ReportStatus.CONFIRMATORY_EVALUABLE,
        sha256_json(payload),
    )


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
    e20_report = _e20_report(e20_authorization, condition_plan)
    e20_ledger = create_e20_run_ledger(e20_authorization, T0)
    e20_ledger = start_e20_run(e20_ledger, T1)
    e20_ledger = complete_e20_run(e20_ledger, T2, e20_report.result_bundle_hash)
    e21_manifest = _rerun_manifest(e20_manifest)
    seal = build_e21_rerun_seal(
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
    )
    e21_authorization = authorize_e21_execution(
        seal,
        preregistration,
        e20_authorization,
        e20_ledger,
        e20_manifest,
        e21_manifest,
        key_manifest,
        capture_environment(),
        serialized_test_key_material=common["serialized_test_key_material"],
        dependency_lock_hash=sha256_text("e21-replication-lock"),
        worker_version="e21-replication-test-worker-v1",
        shard_count=4,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    result_hash = sha256_text("e21-replication-result-bundle")
    e21_ledger = create_e21_run_ledger(e21_authorization, "2026-08-16T20:10:00Z")
    e21_ledger = start_e21_run(e21_ledger, "2026-08-16T20:11:00Z")
    e21_ledger = complete_e21_run(e21_ledger, "2026-08-16T20:12:00Z", result_hash)
    evidence = tuple(
        E21HeadlineEvidence.create(
            headline.condition_id,
            headline.target_fpr,
            result_hash,
            tpr_change=headline.tpr_change + 0.05,
            tpr_change_ci_lower=headline.tpr_change_ci_lower + 0.05,
            tpr_change_ci_upper=headline.tpr_change_ci_upper + 0.05,
            transformed_tpr=headline.transformed_tpr + 0.02,
            standardized_margin_drop=headline.standardized_margin_drop - 0.1,
            coverage_efficiency=headline.coverage_efficiency + 0.2,
            decision_loss_rate=headline.decision_loss_rate - 0.05,
            holm_adjusted_p_value=0.02,
            headline_eligible=True,
        )
        for headline in e20_report.headlines
    )
    return e20_report, e21_authorization, seal, e21_ledger, evidence


def test_e21_replication_comparison_is_descriptive_and_replayable() -> None:
    e20_report, authorization, seal, ledger, evidence = _fixture()
    comparison = build_e21_replication_comparison(
        e20_report,
        authorization,
        seal,
        ledger,
        evidence,
    )
    assert comparison.status is E21ReplicationStatus.DESCRIPTIVE_COMPLETE
    assert all(value.both_headline_eligible for value in comparison.conditions)
    assert all(value.tpr_change_delta == pytest.approx(0.05) for value in comparison.conditions)
    assert all(value.coverage_efficiency_delta == pytest.approx(0.2) for value in comparison.conditions)
    verify_e21_replication_comparison(
        comparison,
        e20_report,
        authorization,
        seal,
        ledger,
        evidence,
    )


def test_e21_replication_rejects_result_bundle_and_fpr_drift() -> None:
    e20_report, authorization, seal, ledger, evidence = _fixture()
    wrong_hash = replace(
        evidence[0],
        source_result_bundle_hash=sha256_text("wrong-e21-result"),
        evidence_hash=sha256_json({
            **evidence[0]._payload(),
            "source_result_bundle_hash": sha256_text("wrong-e21-result"),
        }),
    )
    with pytest.raises(E21ReplicationError, match="completed E21 result bundle"):
        build_e21_replication_comparison(
            e20_report,
            authorization,
            seal,
            ledger,
            (wrong_hash, *evidence[1:]),
        )
    changed_fpr_payload = evidence[0]._payload()
    changed_fpr_payload["target_fpr"] = evidence[0].target_fpr + 0.001
    wrong_fpr = replace(
        evidence[0],
        target_fpr=evidence[0].target_fpr + 0.001,
        evidence_hash=sha256_json(changed_fpr_payload),
    )
    with pytest.raises(E21ReplicationError, match="target FPR changed"):
        build_e21_replication_comparison(
            e20_report,
            authorization,
            seal,
            ledger,
            (wrong_fpr, *evidence[1:]),
        )
