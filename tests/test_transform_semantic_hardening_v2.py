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


def test_unicode_dotless_i_does_not_match_ascii_will_not_rule() -> None:
    enum = default_transform_registry().enumerate("We wıll not leave.")
    assert not enum.candidates


def test_unicode_dotted_capital_i_does_not_match_ascii_will_not_rule() -> None:
    enum = default_transform_registry().enumerate("We WİLL NOT leave.")
    assert not enum.candidates


def test_nothing_to_everything_changes_negation_signature() -> None:
    report = validate_hard_invariants("Nothing changed.", "Everything changed.")
    assert report.status is InvariantStatus.FAIL
    assert HardInvariantReason.NEGATION_CHANGED in report.reasons


def test_obligation_to_permission_changes_modality_signature() -> None:
    report = validate_hard_invariants("You have to wait.", "You may wait.")
    assert report.status is InvariantStatus.FAIL
    assert HardInvariantReason.MODALITY_CHANGED in report.reasons


def test_ascii_rule_does_not_match_inside_unicode_word_boundaries() -> None:
    assert not default_transform_registry().enumerate("αdo notβ").candidates
