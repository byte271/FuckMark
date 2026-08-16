from dataclasses import replace

import pytest

from fuckmark.transforms.fidelity_readiness import (
    TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
    FidelityReadinessStatus,
    build_task29_fidelity_readiness,
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


def test_task29_readiness_report_rejects_rehashed_status_tampering() -> None:
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
