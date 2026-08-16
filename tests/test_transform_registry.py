from dataclasses import replace

import pytest

from fuckmark.transforms import (
    CandidateRejectionReason,
    InvariantStatus,
    LiteralTransformRule,
    TransformFamily,
    TransformRegistry,
    TransformTier,
    UserProtectedRange,
    default_transform_registry,
    validate_protected_invariants,
)


def test_no_candidate_is_explicit_and_empty_application_is_stable() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("Nothing needs changing.")
    assert enumeration.candidates == ()
    result = registry.apply(enumeration, ())
    assert result.output_text == "Nothing needs changing."
    assert result.trace.operations == ()
    assert result.trace.invariant_report.status is InvariantStatus.PASS


def test_one_contraction_applies_exactly() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("You do not need to wait.")
    assert len(enumeration.candidates) == 1
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text == "You don't need to wait."
    assert result.trace.operations[0].before_text == "do not"
    assert result.trace.operations[0].after_text == "don't"


def test_two_nonoverlap_contractions_apply_in_source_order() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("You do not wait and you will not leave.")
    assert len(enumeration.candidates) == 2
    result = registry.apply(enumeration, tuple(reversed(tuple(value.candidate_id for value in enumeration.candidates))))
    assert result.output_text == "You don't wait and you won't leave."
    assert tuple(value.source_start for value in result.trace.operations) == tuple(sorted(value.source_start for value in result.trace.operations))


def test_overlapping_candidates_have_conflict_graph_and_cannot_both_apply() -> None:
    first = LiteralTransformRule.create(
        "first",
        "v1",
        TransformFamily.CONTRACTION,
        TransformTier.SURFACE,
        "do not",
        "don't",
    )
    second = LiteralTransformRule.create(
        "second",
        "v1",
        TransformFamily.ORTHOGRAPHY,
        TransformTier.EXPERIMENTAL,
        "not panic",
        "not-panic",
    )
    registry = TransformRegistry((first, second))
    enumeration = registry.enumerate("do not panic")
    assert len(enumeration.candidates) == 2
    assert len(enumeration.conflicts) == 1
    with pytest.raises(ValueError, match="overlapping"):
        registry.apply(enumeration, tuple(value.candidate_id for value in enumeration.candidates))


def test_all_caps_block_is_recorded_as_precondition_failure() -> None:
    enumeration = default_transform_registry().enumerate("DO NOT PANIC.")
    assert enumeration.candidates == ()
    assert len(enumeration.rejections) == 1
    assert enumeration.rejections[0].reason is CandidateRejectionReason.ALL_CAPS_BLOCKED


def test_unicode_apostrophe_is_byte_preserved_next_to_contraction() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("It’s ready, so do not wait.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text == "It’s ready, so don't wait."


def test_sentence_start_casing_is_preserved() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("Do not panic.")
    assert enumeration.candidates[0].replacement_text == "Don't"
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text == "Don't panic."


def test_newline_boundary_does_not_create_candidate() -> None:
    assert default_transform_registry().enumerate("Do\nnot panic.").candidates == ()


def test_markdown_bullet_content_can_transform_without_touching_marker() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("- Do not panic.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text == "- Don't panic."


def test_numbered_list_content_can_transform_without_touching_number() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("1. Do not panic.")
    result = registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
    assert result.output_text == "1. Don't panic."


def test_protected_quote_blocks_candidate_before_application() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate('"Do not edit this." Do not wait.')
    assert len(enumeration.candidates) == 1
    protected = tuple(value for value in enumeration.rejections if value.reason is CandidateRejectionReason.PROTECTED_OVERLAP)
    assert len(protected) == 1
    assert protected[0].source_text == "Do not"


def test_inline_code_blocks_candidate_before_application() -> None:
    enumeration = default_transform_registry().enumerate("Use `do not change` here.")
    assert enumeration.candidates == ()
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_configured_identifier_can_block_candidate() -> None:
    registry = default_transform_registry(("do not",))
    enumeration = registry.enumerate("You do not wait.")
    assert enumeration.candidates == ()
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_user_marked_range_blocks_candidate() -> None:
    text = "You do not wait."
    start = text.index("do not")
    marked = UserProtectedRange.create(start, start + len("do not"), "negation")
    enumeration = default_transform_registry().enumerate(text, (marked,))
    assert enumeration.candidates == ()
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_reapply_same_contraction_family_is_idempotent() -> None:
    registry = default_transform_registry()
    first = registry.enumerate("Do not panic.")
    transformed = registry.apply(first, (first.candidates[0].candidate_id,)).output_text
    second = registry.enumerate(transformed)
    assert second.candidates == ()


def test_replay_is_byte_and_hash_stable() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("Do not wait and do not retry.")
    ids = tuple(value.candidate_id for value in enumeration.candidates)
    first = registry.apply(enumeration, ids, seed=1234)
    second = registry.apply(enumeration, tuple(reversed(ids)), seed=1234)
    assert first == second
    assert first.result_hash == second.result_hash
    assert first.trace.trace_hash == second.trace.trace_hash


def test_candidate_identity_is_bound_to_input_text() -> None:
    registry = default_transform_registry()
    first = registry.enumerate("Do not wait.").candidates[0]
    second = registry.enumerate("Do not leave.").candidates[0]
    assert first.start == second.start
    assert first.source_text == second.source_text
    assert first.input_hash != second.input_hash
    assert first.candidate_id != second.candidate_id


def test_unknown_or_rejected_candidate_cannot_apply() -> None:
    registry = default_transform_registry()
    enumeration = registry.enumerate("DO NOT PANIC.")
    with pytest.raises(KeyError):
        registry.apply(enumeration, ("0" * 64,))


def test_forged_candidate_hash_is_rejected() -> None:
    candidate = default_transform_registry().enumerate("Do not wait.").candidates[0]
    with pytest.raises(ValueError, match="candidate_id"):
        replace(candidate, candidate_id="0" * 64)


def test_forged_enumeration_hash_is_rejected() -> None:
    enumeration = default_transform_registry().enumerate("Do not wait.")
    with pytest.raises(ValueError, match="enumeration_hash"):
        replace(enumeration, enumeration_hash="0" * 64)


def test_protected_invariant_validator_detects_number_change() -> None:
    report = validate_protected_invariants("Value is 12.", "Value is 13.")
    assert report.status is InvariantStatus.FAIL
    assert any(value.exact_text == "12" for value in report.differences)
    assert any(value.exact_text == "13" for value in report.differences)


def test_protected_invariant_validator_accepts_safe_contraction() -> None:
    report = validate_protected_invariants("Value 12 does not change.", "Value 12 doesn't change.")
    assert report.status is InvariantStatus.PASS
    assert report.differences == ()


def test_duplicate_rule_identity_is_rejected() -> None:
    rule = LiteralTransformRule.create("same", "v1", TransformFamily.CONTRACTION, TransformTier.SURFACE, "do not", "don't")
    with pytest.raises(ValueError, match="identities"):
        TransformRegistry((rule, rule))


def test_user_marked_duplicate_text_does_not_false_fail_when_unchanged() -> None:
    original = "Aurora is here. Aurora remains."
    start = original.index("Aurora")
    marked = UserProtectedRange.create(start, start + len("Aurora"), "entity")
    report = validate_protected_invariants(original, original, user_ranges=(marked,))
    assert report.status is InvariantStatus.PASS


def test_protected_invariant_validator_detects_url_change() -> None:
    report = validate_protected_invariants(
        "Read https://example.com/a now.",
        "Read https://example.com/b now.",
    )
    assert report.status is InvariantStatus.FAIL


def test_apply_rejects_self_consistent_forged_enumeration() -> None:
    from fuckmark import sha256_json
    from fuckmark.transforms import TransformCandidate

    registry = default_transform_registry()
    enumeration = registry.enumerate("Do not wait.")
    original = enumeration.candidates[0]
    payload = {
        "input_hash": original.input_hash,
        "rule_id": original.rule_id,
        "rule_version": original.rule_version,
        "rule_hash": original.rule_hash,
        "family": original.family.value,
        "tier": original.tier.value,
        "start": original.start,
        "end": original.end,
        "source_text": original.source_text,
        "replacement_text": "Never",
    }
    forged = TransformCandidate(
        sha256_json(payload),
        original.input_hash,
        original.rule_id,
        original.rule_version,
        original.rule_hash,
        original.family,
        original.tier,
        original.start,
        original.end,
        original.source_text,
        "Never",
    )
    enumeration_payload = {
        "algorithm_version": enumeration.algorithm_version,
        "input_hash": enumeration.input_hash,
        "ruleset_hash": enumeration.ruleset_hash,
        "protected_manifest_hash": enumeration.protected_manifest.manifest_hash,
        "candidates": (forged,),
        "rejections": enumeration.rejections,
        "conflicts": (),
    }
    forged_enumeration = replace(
        enumeration,
        candidates=(forged,),
        conflicts=(),
        enumeration_hash=sha256_json(enumeration_payload),
    )
    with pytest.raises(ValueError, match="replay exactly"):
        registry.apply(forged_enumeration, (forged.candidate_id,))


def test_enumeration_rejects_missing_conflict_edge_even_with_rehashed_artifact() -> None:
    from fuckmark import sha256_json

    first = LiteralTransformRule.create("first", "v1", TransformFamily.CONTRACTION, TransformTier.SURFACE, "do not", "don't")
    second = LiteralTransformRule.create("second", "v1", TransformFamily.ORTHOGRAPHY, TransformTier.EXPERIMENTAL, "not panic", "not-panic")
    enumeration = TransformRegistry((first, second)).enumerate("do not panic")
    payload = {
        "algorithm_version": enumeration.algorithm_version,
        "input_hash": enumeration.input_hash,
        "ruleset_hash": enumeration.ruleset_hash,
        "protected_manifest_hash": enumeration.protected_manifest.manifest_hash,
        "candidates": enumeration.candidates,
        "rejections": enumeration.rejections,
        "conflicts": (),
    }
    with pytest.raises(ValueError, match="conflicts"):
        replace(enumeration, conflicts=(), enumeration_hash=sha256_json(payload))
