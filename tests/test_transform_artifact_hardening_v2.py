from dataclasses import replace

import pytest

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import (
    CandidateEnumeration,
    HardInvariantReason,
    HardInvariantReport,
    InvariantStatus,
    LiteralTransformRule,
    ProtectedSpan,
    ProtectedSpanExtractor,
    ProtectedSpanKind,
    TransformCandidate,
    TransformFamily,
    TransformOperation,
    TransformRegistry,
    TransformResult,
    TransformTier,
    TransformationTrace,
    UserProtectedRange,
    default_transform_registry,
    validate_hard_invariants,
)


def test_duplicate_identifiers_are_rejected_instead_of_silently_deduplicated() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        ProtectedSpanExtractor(("TOKEN", "TOKEN"))


def test_duplicate_user_range_geometry_is_rejected() -> None:
    first = UserProtectedRange.create(0, 4, "a")
    second = UserProtectedRange.create(0, 4, "b")
    with pytest.raises(ValueError, match="duplicate protected geometry"):
        ProtectedSpanExtractor().extract("test", (first, second))


def test_protected_span_snapshots_mutable_kind_sequence() -> None:
    kinds = [ProtectedSpanKind.NUMBER]
    payload = {
        "start": 0,
        "end": 2,
        "kinds": ("number",),
        "exact_text": "12",
        "text_hash": sha256_text("12"),
    }
    span = ProtectedSpan(0, 2, kinds, "12", payload["text_hash"], sha256_json(payload))
    kinds.append(ProtectedSpanKind.DATE)
    assert span.kinds == (ProtectedSpanKind.NUMBER,)


def test_candidate_enumeration_snapshots_mutable_candidate_sequence() -> None:
    enum = default_transform_registry().enumerate("We do not wait.")
    candidates = list(enum.candidates)
    rebuilt = CandidateEnumeration(
        enum.algorithm_version,
        enum.input_text,
        enum.input_hash,
        enum.ruleset_hash,
        enum.protected_manifest,
        candidates,
        list(enum.rejections),
        list(enum.conflicts),
        enum.enumeration_hash,
    )
    candidates.clear()
    assert rebuilt.candidates == enum.candidates


def test_hard_invariant_report_rejects_forged_pass() -> None:
    failed = validate_hard_invariants("We do not wait.", "We do wait.")
    payload = {
        "algorithm_version": "hard-invariant-validator-v2",
        "status": "pass",
        "original_hash": failed.original_hash,
        "transformed_hash": failed.transformed_hash,
        "protected_report": failed.protected_report,
        "original_signature": failed.original_signature,
        "transformed_signature": failed.transformed_signature,
        "reasons": (),
    }
    with pytest.raises(ValueError, match="do not match component reports"):
        HardInvariantReport(
            InvariantStatus.PASS,
            failed.original_hash,
            failed.transformed_hash,
            failed.protected_report,
            failed.original_signature,
            failed.transformed_signature,
            (),
            sha256_json(payload),
        )


def test_candidate_enumeration_rejects_candidate_inside_protected_span_even_with_valid_hashes() -> None:
    registry = default_transform_registry()
    text = "`do not`"
    base = registry.enumerate(text)
    rule = next(rule for rule in registry.rules if rule.source == "do not")
    start = text.index("do not")
    end = start + len("do not")
    candidate_payload = {
        "input_hash": base.input_hash,
        "rule_id": rule.rule_id,
        "rule_version": rule.version,
        "rule_hash": rule.rule_hash,
        "family": rule.family.value,
        "tier": rule.tier.value,
        "start": start,
        "end": end,
        "source_text": "do not",
        "replacement_text": "don't",
    }
    candidate = TransformCandidate(
        sha256_json(candidate_payload),
        base.input_hash,
        rule.rule_id,
        rule.version,
        rule.rule_hash,
        rule.family,
        rule.tier,
        start,
        end,
        "do not",
        "don't",
    )
    enumeration_payload = {
        "algorithm_version": base.algorithm_version,
        "input_hash": base.input_hash,
        "ruleset_hash": base.ruleset_hash,
        "protected_manifest_hash": base.protected_manifest.manifest_hash,
        "candidates": (candidate,),
        "rejections": (),
        "conflicts": (),
    }
    with pytest.raises(ValueError, match="candidate overlaps a protected span"):
        CandidateEnumeration(
            base.algorithm_version,
            text,
            base.input_hash,
            base.ruleset_hash,
            base.protected_manifest,
            (candidate,),
            (),
            (),
            sha256_json(enumeration_payload),
        )


def test_nonempty_selection_that_nets_to_original_text_is_rejected() -> None:
    rules = (
        LiteralTransformRule.create(
            "expand-a",
            "v1",
            TransformFamily.ORTHOGRAPHY,
            TransformTier.EXPERIMENTAL,
            "a",
            "ab",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        ),
        LiteralTransformRule.create(
            "shrink-bc",
            "v1",
            TransformFamily.ORTHOGRAPHY,
            TransformTier.EXPERIMENTAL,
            "bc",
            "c",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        ),
    )
    registry = TransformRegistry(rules)
    enum = registry.enumerate("abc")
    assert len(enum.candidates) == 2
    with pytest.raises(ValueError, match="no net text change"):
        registry.apply(enum, tuple(candidate.candidate_id for candidate in enum.candidates))


def test_empty_selection_remains_a_valid_explicit_noop_baseline() -> None:
    registry = default_transform_registry()
    enum = registry.enumerate("We do not wait.")
    result = registry.apply(enum, ())
    assert result.output_text == enum.input_text
    assert not result.trace.operations
    assert result.trace.input_hash == result.trace.output_hash


def test_transform_result_rejects_forged_operation_output_text_even_with_recomputed_hashes() -> None:
    registry = default_transform_registry()
    enum = registry.enumerate("We do not wait.")
    result = registry.apply(enum, (enum.candidates[0].candidate_id,))
    operation = result.trace.operations[0]
    forged_after = "x" * len(operation.after_text)
    operation_payload = {
        "candidate_id": operation.candidate_id,
        "rule_id": operation.rule_id,
        "rule_version": operation.rule_version,
        "rule_hash": operation.rule_hash,
        "source_start": operation.source_start,
        "source_end": operation.source_end,
        "output_start": operation.output_start,
        "output_end": operation.output_end,
        "before_text": operation.before_text,
        "after_text": forged_after,
    }
    forged_operation = TransformOperation(
        operation.candidate_id,
        operation.rule_id,
        operation.rule_version,
        operation.rule_hash,
        operation.source_start,
        operation.source_end,
        operation.output_start,
        operation.output_end,
        operation.before_text,
        forged_after,
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
    with pytest.raises(ValueError, match="output geometry does not match output_text"):
        TransformResult(
            result.output_text,
            forged_trace,
            sha256_json({"output_text": result.output_text, "trace": forged_trace}),
        )


def test_trace_snapshots_mutable_operation_sequence() -> None:
    registry = default_transform_registry()
    enum = registry.enumerate("We do not wait.")
    result = registry.apply(enum, (enum.candidates[0].candidate_id,))
    operations = list(result.trace.operations)
    trace = TransformationTrace(
        result.trace.algorithm_version,
        result.trace.registry_version,
        result.trace.selection_policy_id,
        result.trace.seed,
        result.trace.input_hash,
        result.trace.output_hash,
        result.trace.ruleset_hash,
        result.trace.enumeration_hash,
        list(result.trace.selected_candidate_ids),
        operations,
        list(result.trace.precondition_failures),
        0,
        result.trace.invariant_report,
        result.trace.trace_hash,
    )
    operations.clear()
    assert trace.operations == result.trace.operations
