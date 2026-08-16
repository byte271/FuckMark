from dataclasses import replace

import pytest

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import (
    CandidateRejection,
    ProtectedSpanExtractor,
    ProtectedSpanKind,
    TransformOperation,
    TransformResult,
    TransformationTrace,
    default_transform_registry,
)


def spans_of(text, kind):
    return tuple(span for span in ProtectedSpanExtractor().extract(text).spans if kind in span.kinds)


def test_multiline_inline_code_protects_second_line_until_matching_backticks():
    text = "`header\ndo not edit` after"
    spans = spans_of(text, ProtectedSpanKind.CODE)
    assert any(span.exact_text == "`header\ndo not edit`" for span in spans)
    enumeration = default_transform_registry().enumerate(text)
    assert not enumeration.candidates
    assert any(rejection.source_text == "do not" for rejection in enumeration.rejections)


def test_inline_code_requires_same_backtick_run_length():
    text = "`head`` do not edit` after"
    spans = spans_of(text, ProtectedSpanKind.CODE)
    assert any(span.exact_text == "`head`` do not edit`" for span in spans)
    assert not default_transform_registry().enumerate(text).candidates


def test_numeric_start_inline_math_is_fully_protected():
    text = "$12 + do not$ after"
    spans = spans_of(text, ProtectedSpanKind.MATH)
    assert any(span.exact_text == "$12 + do not$" for span in spans)
    assert not default_transform_registry().enumerate(text).candidates


def test_leading_decimal_inline_math_is_fully_protected():
    text = "$.5 + do not$ after"
    spans = spans_of(text, ProtectedSpanKind.MATH)
    assert any(span.exact_text == "$.5 + do not$" for span in spans)
    assert not default_transform_registry().enumerate(text).candidates


def test_two_currency_amounts_do_not_become_math():
    text = "Costs are $12 and $15, and we do not wait."
    assert not spans_of(text, ProtectedSpanKind.MATH)
    assert any(candidate.source_text == "do not" for candidate in default_transform_registry().enumerate(text).candidates)


def test_unicode_casefold_lookalike_is_not_ascii_domain():
    text = "example.cK and do not wait"
    assert not spans_of(text, ProtectedSpanKind.URL)
    assert any(candidate.source_text == "do not" for candidate in default_transform_registry().enumerate(text).candidates)


def test_unicode_casefold_lookalike_is_not_ascii_email():
    text = "foo@examplı.com and do not wait"
    assert not spans_of(text, ProtectedSpanKind.EMAIL)
    assert any(candidate.source_text == "do not" for candidate in default_transform_registry().enumerate(text).candidates)


def test_nbsp_percentage_is_one_protected_span():
    span = spans_of("50\u00a0%", ProtectedSpanKind.PERCENTAGE)[0]
    assert span.exact_text == "50\u00a0%"


def test_nbsp_currency_is_one_protected_span():
    span = spans_of("USD\u00a012.50", ProtectedSpanKind.CURRENCY)[0]
    assert span.exact_text == "USD\u00a012.50"


def test_day_first_slash_date_is_protected():
    span = spans_of("31/12/2026", ProtectedSpanKind.DATE)[0]
    assert span.exact_text == "31/12/2026"


def test_english_date_does_not_cross_newline():
    assert not spans_of("Sep\n16 2026", ProtectedSpanKind.DATE)


def test_escaped_delimited_math_opener_is_not_protected():
    text = r"Literal \\(do not wait and do not leave"
    enumeration = default_transform_registry().enumerate(text)
    assert len(enumeration.candidates) == 2


def test_trace_rejects_duplicate_precondition_failures_even_when_rehashed():
    registry = default_transform_registry()
    enumeration = registry.enumerate("DO NOT PANIC. We do not wait.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    failure = result.trace.precondition_failures[0]
    failures = (failure, failure)
    payload = result.trace._payload()
    payload["precondition_failures"] = failures
    with pytest.raises(ValueError, match="unique"):
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
            0,
            result.trace.invariant_report,
            sha256_json(payload),
        )


def test_trace_rejects_precondition_failure_from_another_input():
    registry = default_transform_registry()
    enumeration = registry.enumerate("DO NOT PANIC. We do not wait.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    failure = result.trace.precondition_failures[0]
    other_hash = sha256_text("different input")
    failure_payload = failure._payload()
    failure_payload["input_hash"] = other_hash
    forged = CandidateRejection(
        other_hash,
        failure.rule_id,
        failure.rule_version,
        failure.rule_hash,
        failure.start,
        failure.end,
        failure.source_text,
        failure.reason,
        failure.protected_span_hashes,
        sha256_json(failure_payload),
    )
    payload = result.trace._payload()
    payload["precondition_failures"] = (forged,)
    with pytest.raises(ValueError, match="input hashes"):
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
            (forged,),
            0,
            result.trace.invariant_report,
            sha256_json(payload),
        )


def test_result_reconstructs_and_validates_operation_before_text():
    registry = default_transform_registry()
    enumeration = registry.enumerate("We do not wait.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    operation = result.trace.operations[0]
    forged_before = "go not"
    operation_payload = operation._payload()
    operation_payload["before_text"] = forged_before
    forged_operation = TransformOperation(
        operation.candidate_id,
        operation.rule_id,
        operation.rule_version,
        operation.rule_hash,
        operation.source_start,
        operation.source_end,
        operation.output_start,
        operation.output_end,
        forged_before,
        operation.after_text,
        sha256_json(operation_payload),
    )
    trace_payload = result.trace._payload()
    trace_payload["operations"] = (forged_operation,)
    forged_trace = TransformationTrace(
        result.trace.algorithm_version,
        result.trace.registry_version,
        result.trace.selection_policy_id,
        result.trace.seed,
        result.trace.input_hash,
        result.trace.output_hash,
        result.trace.ruleset_hash,
        result.trace.enumeration_hash,
        result.trace.selected_candidate_ids,
        (forged_operation,),
        result.trace.precondition_failures,
        0,
        result.trace.invariant_report,
        sha256_json(trace_payload),
    )
    with pytest.raises(ValueError, match="reconstruct trace input hash"):
        TransformResult(result.output_text, forged_trace, sha256_json({"output_text": result.output_text, "trace": forged_trace}))


def test_passing_protected_report_identity_binds_configured_identifier_policy():
    from fuckmark.transforms import validate_protected_invariants
    text = "Keep TOKEN unchanged."
    default = validate_protected_invariants(text, text)
    configured = validate_protected_invariants(text, text, identifiers=("TOKEN",))
    assert default.status is configured.status
    assert default.original_manifest_hash != configured.original_manifest_hash
    assert default.report_hash != configured.report_hash


def test_english_date_validation_is_locale_independent_by_construction():
    from fuckmark.transforms.protected_patterns import _valid_english_date
    assert _valid_english_date("Sep 16, 2026")
    assert _valid_english_date("16 September 2026")
    assert not _valid_english_date("Sep 31, 2026")


def test_ambiguous_extended_path_beyond_scan_limit_fails_closed():
    text = "/root/My Folder/" + ("segment name/" * 400) + "tail"
    with pytest.raises(ValueError, match="extended path scan exceeded resource limit"):
        ProtectedSpanExtractor().extract(text)


def test_display_math_skips_escaped_double_dollar_closer():
    text = r"$$ x + \$$ do not edit $$ after"
    spans = spans_of(text, ProtectedSpanKind.MATH)
    assert any(span.exact_text == r"$$ x + \$$ do not edit $$" for span in spans)
    assert not default_transform_registry().enumerate(text).candidates


def test_path_filename_is_not_misclassified_as_bare_domain_url():
    for text in ("/tmp/report.json", r"C:\Temp\report.json"):
        spans = ProtectedSpanExtractor().extract(text).spans
        assert any(ProtectedSpanKind.POSIX_PATH in span.kinds or ProtectedSpanKind.WINDOWS_PATH in span.kinds for span in spans)
        assert all(ProtectedSpanKind.URL not in span.kinds for span in spans)


def test_many_currency_dollars_remain_non_math():
    text = " ".join("$12" for _ in range(5000))
    assert not spans_of(text, ProtectedSpanKind.MATH)
