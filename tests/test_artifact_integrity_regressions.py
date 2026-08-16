import pytest

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import (
    CandidateRejection,
    InvariantDifference,
    InvariantStatus,
    ProtectedInvariantReport,
    ProtectedSpan,
    ProtectedSpanKind,
    TransformCandidate,
    TransformationTrace,
    default_transform_registry,
)


def test_protected_span_rejects_geometry_that_does_not_match_exact_text() -> None:
    text_hash = sha256_text("12")
    payload = {
        "start": 0,
        "end": 3,
        "kinds": (ProtectedSpanKind.NUMBER.value,),
        "exact_text": "12",
        "text_hash": text_hash,
    }
    with pytest.raises(ValueError, match="geometry does not match exact_text"):
        ProtectedSpan(
            0,
            3,
            (ProtectedSpanKind.NUMBER,),
            "12",
            text_hash,
            sha256_json(payload),
        )


def test_transform_candidate_rejects_geometry_that_does_not_match_source_text() -> None:
    candidate = default_transform_registry().enumerate("We do not wait.").candidates[0]
    payload = candidate._payload()
    payload["end"] = candidate.end + 1
    with pytest.raises(ValueError, match="candidate span does not match source_text"):
        TransformCandidate(
            sha256_json(payload),
            candidate.input_hash,
            candidate.rule_id,
            candidate.rule_version,
            candidate.rule_hash,
            candidate.family,
            candidate.tier,
            candidate.start,
            candidate.end + 1,
            candidate.source_text,
            candidate.replacement_text,
        )


def test_candidate_rejection_rejects_geometry_that_does_not_match_source_text() -> None:
    rejection = default_transform_registry().enumerate("`do not`").rejections[0]
    payload = rejection._payload()
    payload["end"] = rejection.end + 1
    with pytest.raises(ValueError, match="rejection span does not match source_text"):
        CandidateRejection(
            rejection.input_hash,
            rejection.rule_id,
            rejection.rule_version,
            rejection.rule_hash,
            rejection.start,
            rejection.end + 1,
            rejection.source_text,
            rejection.reason,
            rejection.protected_span_hashes,
            sha256_json(payload),
        )


def test_protected_invariant_report_rejects_noncanonical_difference_order() -> None:
    number = InvariantDifference(ProtectedSpanKind.NUMBER, "12", 1, 0)
    email = InvariantDifference(ProtectedSpanKind.EMAIL, "a@example.com", 1, 0)
    differences = (number, email)
    original_hash = sha256_text("original")
    transformed_hash = sha256_text("transformed")
    payload = {
        "algorithm_version": "protected-invariant-validator-v2",
        "status": InvariantStatus.FAIL.value,
        "original_hash": original_hash,
        "transformed_hash": transformed_hash,
        "differences": differences,
    }
    with pytest.raises(ValueError, match="canonically ordered"):
        ProtectedInvariantReport(
            InvariantStatus.FAIL,
            original_hash,
            transformed_hash,
            differences,
            sha256_json(payload),
        )


def test_protected_invariant_report_rejects_duplicate_difference_keys() -> None:
    first = InvariantDifference(ProtectedSpanKind.NUMBER, "12", 1, 0)
    second = InvariantDifference(ProtectedSpanKind.NUMBER, "12", 2, 0)
    differences = (first, second)
    original_hash = sha256_text("original")
    transformed_hash = sha256_text("transformed")
    payload = {
        "algorithm_version": "protected-invariant-validator-v2",
        "status": InvariantStatus.FAIL.value,
        "original_hash": original_hash,
        "transformed_hash": transformed_hash,
        "differences": differences,
    }
    with pytest.raises(ValueError, match="duplicate protected keys"):
        ProtectedInvariantReport(
            InvariantStatus.FAIL,
            original_hash,
            transformed_hash,
            differences,
            sha256_json(payload),
        )


def test_trace_rejects_precondition_failure_from_another_input() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("We do not wait.")
    result = registry.apply(enumeration, ())
    foreign_failure = registry.enumerate("`do not`").rejections[0]
    failures = (foreign_failure,)
    payload = result.trace._payload()
    payload["precondition_failures"] = failures
    with pytest.raises(ValueError, match="must match trace input"):
        TransformationTrace(
            result.trace.algorithm_version,
            result.trace.registry_version,
            result.trace.selection_policy_id,
            result.trace.seed,
            result.trace.input_hash,
            result.trace.output_hash,
            result.trace.ruleset_hash,
            result.trace.enumeration_hash,
            result.trace.selected_candidate_ids,
            result.trace.operations,
            failures,
            result.trace.protected_span_violation_count,
            result.trace.invariant_report,
            sha256_json(payload),
        )
