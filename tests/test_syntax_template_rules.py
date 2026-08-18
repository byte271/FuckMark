from dataclasses import replace

import pytest

from fuckmark.transforms import development_transform_registry
from fuckmark.transforms.registry import TransformRegistry, default_transform_registry
from fuckmark.transforms.schema import CandidateRejectionReason, TransformFamily, TransformTier
from fuckmark.transforms.syntax_rules import (
    SYNTAX_TEMPLATE_RULE_ALGORITHM_VERSION,
    SyntaxConstruction,
    development_syntax_rules,
)


POSITIVE_FIXTURES = (
    ("The build passed; however, the deploy failed.", "The build passed. However, the deploy failed."),
    ("We checked the cache; however, the value was stale.", "We checked the cache. However, the value was stale."),
    ("The request completed; However, the result was empty.", "The request completed. However, the result was empty."),
    ("The worker stayed online; however, the queue remained blocked.", "The worker stayed online. However, the queue remained blocked."),
    ("The first attempt failed; however, the second attempt succeeded.", "The first attempt failed. However, the second attempt succeeded."),
)

NEGATIVE_FIXTURES = (
    "Passed; however, the deploy failed.",
    "The build passed; however, failed.",
    "- The build passed; however, the deploy failed.",
    "* The build passed; however, the deploy failed.",
    "1. The build passed; however, the deploy failed.",
)


def _registry() -> TransformRegistry:
    return TransformRegistry(development_syntax_rules())


def test_development_syntax_rule_is_tier_three_and_closed_construction() -> None:
    rule = development_syntax_rules()[0]
    assert SYNTAX_TEMPLATE_RULE_ALGORITHM_VERSION == "syntax-template-rule-v1"
    assert rule.family is TransformFamily.SYNTAX_TEMPLATE
    assert rule.tier is TransformTier.SYNTAX
    assert rule.construction is SyntaxConstruction.SEMICOLON_CONJUNCTIVE_ADVERB_SPLIT
    assert rule.minimum_clause_word_count == 2


@pytest.mark.parametrize(("source", "expected"), POSITIVE_FIXTURES)
def test_semicolon_however_positive_fixtures(source: str, expected: str) -> None:
    registry = _registry()
    enumeration = registry.enumerate(source)
    assert len(enumeration.candidates) == 1
    assert enumeration.rejections == ()
    candidate = enumeration.candidates[0]
    assert candidate.family is TransformFamily.SYNTAX_TEMPLATE
    assert candidate.tier is TransformTier.SYNTAX
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == expected
    assert registry.enumerate(result.output_text).candidates == ()


@pytest.mark.parametrize("source", NEGATIVE_FIXTURES)
def test_syntax_negative_contexts_are_explicit_precondition_failures(source: str) -> None:
    enumeration = _registry().enumerate(source)
    assert enumeration.candidates == ()
    assert len(enumeration.rejections) == 1
    assert enumeration.rejections[0].reason is CandidateRejectionReason.PRECONDITION_FAILED


def test_syntax_punctuation_mismatch_does_not_create_candidate() -> None:
    enumeration = _registry().enumerate("The build passed; however the deploy failed.")
    assert enumeration.candidates == ()
    assert enumeration.rejections == ()


def test_syntax_all_caps_and_protected_quote_are_blocked() -> None:
    all_caps = _registry().enumerate("THE BUILD PASSED; HOWEVER, THE DEPLOY FAILED.")
    assert all_caps.candidates == ()
    assert all_caps.rejections[0].reason is CandidateRejectionReason.ALL_CAPS_BLOCKED
    quoted = _registry().enumerate('"The build passed; however, the deploy failed."')
    assert quoted.candidates == ()
    assert quoted.rejections[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_default_policy_excludes_syntax_while_development_policy_includes_it() -> None:
    text = "The build passed; however, the deploy failed."
    assert default_transform_registry().enumerate(text).candidates == ()
    enumeration = development_transform_registry().enumerate(text)
    syntax_candidates = tuple(
        candidate for candidate in enumeration.candidates
        if candidate.family is TransformFamily.SYNTAX_TEMPLATE
    )
    assert tuple(candidate.rule_id for candidate in syntax_candidates) == (
        "syntax-semicolon-however-split",
    )
    assert all(candidate.tier is TransformTier.SYNTAX for candidate in syntax_candidates)


def test_syntax_rule_rejects_rehashed_construction_tampering() -> None:
    rule = development_syntax_rules()[0]
    with pytest.raises(ValueError, match="rule_hash"):
        replace(rule, replacement=". Nevertheless, ")
