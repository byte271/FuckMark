from dataclasses import replace

import pytest

from fuckmark.transforms.lexical_rules import (
    LEXICAL_TEMPLATE_RULE_ALGORITHM_VERSION,
    LexicalConstruction,
    LexicalTemplateRule,
    development_lexical_rules,
)
from fuckmark.transforms.registry import TransformRegistry, default_transform_registry
from fuckmark.transforms.schema import CandidateRejectionReason, TransformFamily, TransformTier


POSITIVE_FIXTURES = (
    ("For example, use a cache.", "For instance, use a cache."),
    ("for example, use a cache.", "for instance, use a cache."),
    ("This works. For example, use a cache.", "This works. For instance, use a cache."),
    ("Does this work? For example, retry once.", "Does this work? For instance, retry once."),
    ("Stop!\nFor example, inspect the log.", "Stop!\nFor instance, inspect the log."),
)

NEGATIVE_FIXTURES = (
    "Use, for example, a cache.",
    "Use this—for example, a cache.",
    "Note: For example, retry once.",
    "- For example, retry once.",
    "(For example, retry once.)",
)


def _registry() -> TransformRegistry:
    return TransformRegistry(development_lexical_rules())


def test_development_lexical_rule_is_tier_two_and_separately_versioned() -> None:
    rule = development_lexical_rules()[0]
    assert LEXICAL_TEMPLATE_RULE_ALGORITHM_VERSION == "lexical-template-rule-v1"
    assert rule.family is TransformFamily.LEXICAL_TEMPLATE
    assert rule.tier is TransformTier.LEXICAL
    assert rule.construction is LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_MARKER
    assert rule.rule_hash == type(rule).create(
        rule.rule_id,
        rule.version,
        rule.source,
        rule.replacement,
        rule.construction,
        rule.ambiguity_blacklist,
    ).rule_hash


@pytest.mark.parametrize(("source", "expected"), POSITIVE_FIXTURES)
def test_sentence_initial_lexical_positive_fixtures(source: str, expected: str) -> None:
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert len(enumeration.candidates) == 1
    assert enumeration.rejections == ()
    candidate = enumeration.candidates[0]
    assert candidate.family is TransformFamily.LEXICAL_TEMPLATE
    assert candidate.tier is TransformTier.LEXICAL
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == expected
    assert registry.enumerate(result.output_text).candidates == ()


@pytest.mark.parametrize("source", NEGATIVE_FIXTURES)
def test_lexical_negative_contexts_are_explicit_precondition_failures(source: str) -> None:
    enumeration = _registry().enumerate(source)
    assert enumeration.candidates == ()
    assert len(enumeration.rejections) == 1
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PRECONDITION_FAILED


def test_lexical_punctuation_boundary_mismatch_does_not_create_candidate() -> None:
    enumeration = _registry().enumerate("For example: use a cache.")
    assert enumeration.candidates == ()
    assert enumeration.rejections == ()


def test_lexical_all_caps_and_protected_quote_are_blocked_before_application() -> None:
    all_caps = _registry().enumerate("FOR EXAMPLE, STOP.")
    assert all_caps.candidates == ()
    assert all_caps.rejections[0].reason is CandidateRejectionReason.ALL_CAPS_BLOCKED
    quoted = _registry().enumerate('"For example, use a cache."')
    assert quoted.candidates == ()
    assert quoted.rejections[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_lexical_ambiguity_blacklist_is_canonical_and_enforced() -> None:
    rule = LexicalTemplateRule.create(
        "lexical-blacklist-fixture",
        "v1",
        "for example,",
        "for instance,",
        LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_MARKER,
        ("blocked marker",),
    )
    enumeration = TransformRegistry((rule,)).enumerate("Blocked marker. For example, retry.")
    assert enumeration.candidates == ()
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PRECONDITION_FAILED
    with pytest.raises(ValueError, match="canonically ordered"):
        replace(rule, ambiguity_blacklist=("zeta", "alpha"), rule_hash="0" * 64)


def test_default_registry_does_not_enable_development_lexical_rules() -> None:
    enumeration = default_transform_registry().enumerate("For example, use a cache.")
    assert enumeration.candidates == ()
    assert all(candidate.family is not TransformFamily.LEXICAL_TEMPLATE for candidate in enumeration.candidates)


def test_lexical_rule_rejects_rehashed_construction_tampering() -> None:
    rule = development_lexical_rules()[0]
    with pytest.raises(ValueError, match="rule_hash"):
        replace(rule, replacement="for illustration,")
