from dataclasses import replace

import pytest

from fuckmark.hashing import sha256_json
from fuckmark.transforms.fidelity_readiness import (
    TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
    FidelityReadinessStatus,
    FidelityReadinessVerificationError,
    Task29FidelityReadinessReport,
    build_task29_fidelity_readiness,
    verify_task29_fidelity_readiness,
)


def test_task29_default_readiness_reports_real_external_evidence_blockers() -> None:
    report = build_task29_fidelity_readiness()
    assert report.algorithm_version == TASK29_FIDELITY_READINESS_ALGORITHM_VERSION
    assert len(report.rows) == 2
    assert {row.status for row in report.rows} == {
        FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE
    }
    assert report.has_missing_evidence
    assert not report.confirmatory_scale_ready
    assert {row.rule_id for row in report.rows} == {
        "lexical-for-example-for-instance",
        "syntax-semicolon-however-split",
    }
    verify_task29_fidelity_readiness(report)


def test_task29_readiness_report_rejects_invalid_status_or_hash_tampering() -> None:
    report = build_task29_fidelity_readiness()
    first = report.rows[0]
    with pytest.raises(ValueError):
        replace(
            first,
            status=FidelityReadinessStatus.VERIFIED_LEXICAL_RELEASE_EVIDENCE,
            evidence_hash=None,
        )
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, report_hash="f" * 64)


def test_task29_readiness_replay_rejects_rehashed_verified_status_without_evidence() -> None:
    report = build_task29_fidelity_readiness()
    first = report.rows[0]
    forged_first = replace(
        first,
        status=FidelityReadinessStatus.VERIFIED_LEXICAL_RELEASE_EVIDENCE,
        evidence_hash="a" * 64,
    )
    rows = (forged_first, *report.rows[1:])
    payload = {
        "algorithm_version": TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        "rows": rows,
    }
    forged = Task29FidelityReadinessReport(
        TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        rows,
        sha256_json(payload),
    )
    with pytest.raises(FidelityReadinessVerificationError, match="does not replay exactly"):
        verify_task29_fidelity_readiness(forged)


def test_task29_readiness_rejects_rehashed_unknown_rule_identity() -> None:
    report = build_task29_fidelity_readiness()
    forged_first = replace(report.rows[0], rule_id="unknown-development-rule")
    rows = tuple(sorted((forged_first, *report.rows[1:]), key=lambda value: (value.family.value, value.rule_id, value.rule_hash)))
    payload = {
        "algorithm_version": TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        "rows": rows,
    }
    with pytest.raises(ValueError, match="exactly cover current development rules"):
        Task29FidelityReadinessReport(
            TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
            rows,
            sha256_json(payload),
        )
