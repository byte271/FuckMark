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
from fuckmark.transforms.lexical_rules import development_lexical_rules
from fuckmark.transforms.syntax_rules import development_syntax_rules


def test_task29_default_readiness_reports_real_external_evidence_blockers() -> None:
    report = build_task29_fidelity_readiness()
    assert report.algorithm_version == TASK29_FIDELITY_READINESS_ALGORITHM_VERSION
    assert len(report.rows) == 2
    assert {row.status for row in report.rows} == {
        FidelityReadinessStatus.MISSING_SOURCE_GROUNDED_EVIDENCE
    }
    assert report.has_missing_evidence
    assert not report.selection_frozen
    assert report.selected_rows == ()
    assert not report.confirmatory_scale_ready
    assert {row.rule_id for row in report.rows} == {
        "lexical-for-example-for-instance",
        "syntax-semicolon-however-split",
    }
    verify_task29_fidelity_readiness(report)


def test_explicitly_frozen_empty_task29_selection_does_not_block_confirmatory_scale() -> None:
    report = build_task29_fidelity_readiness(confirmatory_rule_hashes=())
    assert report.selection_frozen
    assert report.selected_rows == ()
    assert report.has_missing_evidence
    assert not report.has_selected_missing_evidence
    assert report.confirmatory_scale_ready
    verify_task29_fidelity_readiness(report, confirmatory_rule_hashes=())


def test_selected_lexical_rule_without_source_grounded_evidence_blocks_confirmatory_scale() -> None:
    rule = development_lexical_rules()[0]
    report = build_task29_fidelity_readiness(confirmatory_rule_hashes=(rule.rule_hash,))
    assert report.selection_frozen
    assert tuple(row.rule_hash for row in report.selected_rows) == (rule.rule_hash,)
    assert report.has_selected_missing_evidence
    assert not report.confirmatory_scale_ready


def test_selected_syntax_rule_without_release_grade_evidence_blocks_confirmatory_scale() -> None:
    rule = development_syntax_rules()[0]
    report = build_task29_fidelity_readiness(confirmatory_rule_hashes=(rule.rule_hash,))
    assert report.selection_frozen
    assert tuple(row.rule_hash for row in report.selected_rows) == (rule.rule_hash,)
    assert report.has_selected_missing_evidence
    assert not report.confirmatory_scale_ready


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
        selected_for_confirmatory=True,
    )
    rows = tuple(
        sorted(
            (forged_first, *report.rows[1:]),
            key=lambda value: (value.family.value, value.rule_id, value.rule_hash),
        )
    )
    payload = {
        "algorithm_version": TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        "rows": rows,
        "selection_frozen": True,
    }
    forged = Task29FidelityReadinessReport(
        TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        rows,
        True,
        sha256_json(payload),
    )
    with pytest.raises(FidelityReadinessVerificationError, match="does not replay exactly"):
        verify_task29_fidelity_readiness(
            forged,
            confirmatory_rule_hashes=(first.rule_hash,),
        )


def test_task29_readiness_rejects_rehashed_unknown_rule_identity() -> None:
    report = build_task29_fidelity_readiness()
    forged_first = replace(report.rows[0], rule_id="unknown-development-rule")
    rows = tuple(sorted((forged_first, *report.rows[1:]), key=lambda value: (value.family.value, value.rule_id, value.rule_hash)))
    payload = {
        "algorithm_version": TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
        "rows": rows,
        "selection_frozen": False,
    }
    with pytest.raises(ValueError, match="exactly cover current development rules"):
        Task29FidelityReadinessReport(
            TASK29_FIDELITY_READINESS_ALGORITHM_VERSION,
            rows,
            False,
            sha256_json(payload),
        )
