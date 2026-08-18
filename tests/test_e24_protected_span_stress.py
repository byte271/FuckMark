from dataclasses import replace

import pytest

from fuckmark.experiments.e24_protected_span_stress import (
    E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION,
    E24ProtectedSpanStressStatus,
    run_e24_protected_span_stress,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import ProtectedSpanKind, development_transform_registry


def test_e24_default_development_registry_passes_full_protected_span_stress() -> None:
    report = run_e24_protected_span_stress(development_transform_registry())

    assert report.algorithm_version == E24_PROTECTED_SPAN_STRESS_ALGORITHM_VERSION
    assert report.status is E24ProtectedSpanStressStatus.PASS
    assert report.coverage_failure_count == 0
    assert report.protected_violation_count == 0
    assert tuple(value.kind for value in report.protected_kind_results) == tuple(
        sorted(tuple(ProtectedSpanKind), key=lambda value: value.value)
    )
    assert all(value.observed for value in report.protected_kind_results)
    assert all(value.safe_application_attempted for value in report.protected_kind_results)
    assert all(value.protected_violation_count == 0 for value in report.protected_kind_results)
    assert all(value.protected_overlap_rejection_count == value.rule_count for value in report.family_results)
    assert all(value.safe_application_attempt_count == value.rule_count for value in report.family_results)
    assert all(value.protected_violation_count == 0 for value in report.family_results)
    assert report.inactive_families == ()


def test_e24_report_is_byte_deterministic_for_the_same_registry() -> None:
    first = run_e24_protected_span_stress(development_transform_registry())
    second = run_e24_protected_span_stress(development_transform_registry())

    assert first == second
    assert first.report_hash == second.report_hash


def test_e24_report_hash_binds_ruleset_provenance() -> None:
    report = run_e24_protected_span_stress(development_transform_registry())

    with pytest.raises(ValueError, match="report_hash"):
        replace(report, ruleset_hash=sha256_text("tampered-e24-ruleset"))
