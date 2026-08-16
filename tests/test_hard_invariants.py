import pytest

from fuckmark.transforms import (
    HardInvariantReason,
    InvariantStatus,
    LiteralTransformRule,
    TransformFamily,
    TransformRegistry,
    TransformTier,
    hard_invariant_signature,
    validate_hard_invariants,
)


def test_contracted_and_expanded_negation_share_signature() -> None:
    expanded = hard_invariant_signature("We do not wait and we will not leave.")
    contracted = hard_invariant_signature("We don't wait and we won't leave.")
    assert expanded == contracted


def test_cannot_and_cant_share_negation_and_modality_signature() -> None:
    assert hard_invariant_signature("We cannot wait.") == hard_invariant_signature("We can't wait.")


def test_curly_and_ascii_apostrophes_share_signature() -> None:
    assert hard_invariant_signature("We don’t wait.") == hard_invariant_signature("We don't wait.")


def test_hard_invariant_report_detects_removed_negation() -> None:
    report = validate_hard_invariants("We do not wait.", "We do wait.")
    assert report.status is InvariantStatus.FAIL
    assert HardInvariantReason.NEGATION_CHANGED in report.reasons


def test_hard_invariant_report_detects_changed_modality() -> None:
    report = validate_hard_invariants("We should wait.", "We might wait.")
    assert report.status is InvariantStatus.FAIL
    assert HardInvariantReason.MODALITY_CHANGED in report.reasons


def test_hard_invariant_report_detects_protected_literal_change() -> None:
    report = validate_hard_invariants("Value is 12.", "Value is 13.")
    assert report.status is InvariantStatus.FAIL
    assert HardInvariantReason.PROTECTED_CONTENT_CHANGED in report.reasons


def test_registry_rejects_custom_rule_that_removes_negation() -> None:
    rule = LiteralTransformRule.create(
        "unsafe-remove-negation",
        "v1",
        TransformFamily.ORTHOGRAPHY,
        TransformTier.EXPERIMENTAL,
        "do not",
        "do",
    )
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate("We do not wait.")
    with pytest.raises(ValueError, match="hard content invariants"):
        registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))


def test_registry_rejects_custom_rule_that_changes_modality() -> None:
    rule = LiteralTransformRule.create(
        "unsafe-modality",
        "v1",
        TransformFamily.ORTHOGRAPHY,
        TransformTier.EXPERIMENTAL,
        "should wait",
        "might wait",
    )
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate("We should wait.")
    with pytest.raises(ValueError, match="hard content invariants"):
        registry.apply(enumeration, (enumeration.candidates[0].candidate_id,))
