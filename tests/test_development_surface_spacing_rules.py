import pytest

from fuckmark.experiments.e24_protected_span_stress import (
    E24ProtectedSpanStressStatus,
    run_e24_protected_span_stress,
)
from fuckmark.transforms import (
    TransformFamily,
    TransformTier,
    default_contraction_rules,
    default_transform_registry,
    development_transform_registry,
    release_transform_registry,
)
from fuckmark.transforms.rules import SURFACE_SPACING_RULE_ALGORITHM_VERSION, SurfaceSpacingRule
from fuckmark.transforms.surface_rules import SURFACE_RULESET_ALGORITHM_VERSION, development_surface_rules


def test_surface_spacing_rules_are_case_safe_tier_one_orthography() -> None:
    rules = development_surface_rules()
    assert SURFACE_SPACING_RULE_ALGORITHM_VERSION == "surface-spacing-rule-v2"
    assert SURFACE_RULESET_ALGORITHM_VERSION == "development-surface-rules-v4"
    assert tuple(rule.rule_id for rule in rules) == (
        "surface-space-after-is",
        "surface-space-after-of",
        "surface-space-after-to",
        "surface-space-after-the",
        "surface-space-after-and",
        "surface-space-after-in",
        "surface-space-after-for",
        "surface-space-after-on",
        "surface-space-after-with",
        "surface-space-after-as",
        "surface-space-after-from",
        "surface-space-after-that",
        "surface-space-after-this",
        "surface-space-after-was",
        "surface-space-after-are",
        "surface-space-after-be",
        "surface-space-after-can",
        "surface-space-after-will",
        "surface-space-after-have",
        "surface-space-after-has",
        "surface-space-after-not",
        "surface-space-after-but",
        "surface-space-after-or",
        "surface-space-after-by",
        "surface-space-after-at",
        "surface-space-after-it",
        "surface-space-after-we",
        "surface-space-after-you",
        "surface-space-after-they",
        "surface-space-after-period",
        "surface-space-after-comma",
        "surface-space-after-semicolon",
        "surface-space-after-colon",
        "surface-space-after-question",
        "surface-space-after-exclamation",
    )
    assert all(isinstance(rule, SurfaceSpacingRule) for rule in rules)
    assert all(rule.family is TransformFamily.ORTHOGRAPHY for rule in rules)
    assert all(rule.tier is TransformTier.SURFACE for rule in rules)
    assert all(rule.replacement == rule.source + " " for rule in rules)
    assert len({rule.rule_hash for rule in rules}) == len(rules)


def test_word_spacing_rule_requires_lowercase_word_with_same_line_content() -> None:
    rule = development_surface_rules()[0]
    assert tuple(match.group(0) for match in rule.pattern().finditer("this is stable")) == ("is",)
    assert tuple(match.group(0) for match in rule.pattern().finditer("this is\tstable")) == ("is",)
    assert tuple(match.group(0) for match in rule.pattern().finditer("Is this stable?")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is, this stable?")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is\nnext")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is \nnext")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is   stable")) == ("is",)


def test_line_end_surface_spacing_does_not_create_markdown_hard_break() -> None:
    registry = development_transform_registry()
    text = "This is\nnext. This is \nnext. This is\t\nnext."
    enumeration = registry.enumerate(text)
    assert not tuple(value for value in enumeration.candidates if value.rule_id == "surface-space-after-is")


def test_expanded_surface_battery_enumerates_common_function_words() -> None:
    registry = development_transform_registry()
    text = "the and in for on with as from is of to that this was are be can will have has not but or by at it we you they remain. Safe."
    enumeration = registry.enumerate(text)
    ids = {candidate.rule_id for candidate in enumeration.candidates}
    assert {
        "surface-space-after-the",
        "surface-space-after-and",
        "surface-space-after-in",
        "surface-space-after-for",
        "surface-space-after-on",
        "surface-space-after-with",
        "surface-space-after-as",
        "surface-space-after-from",
        "surface-space-after-is",
        "surface-space-after-of",
        "surface-space-after-to",
        "surface-space-after-that",
        "surface-space-after-this",
        "surface-space-after-was",
        "surface-space-after-are",
        "surface-space-after-be",
        "surface-space-after-can",
        "surface-space-after-will",
        "surface-space-after-have",
        "surface-space-after-has",
        "surface-space-after-not",
        "surface-space-after-but",
        "surface-space-after-or",
        "surface-space-after-by",
        "surface-space-after-at",
        "surface-space-after-it",
        "surface-space-after-we",
        "surface-space-after-you",
        "surface-space-after-they",
    } <= ids


def test_expanded_surface_battery_enumerates_sentence_punctuation() -> None:
    registry = development_transform_registry()
    enumeration = registry.enumerate("Alpha, beta; gamma: delta? yes! Final. Done.")
    ids = {candidate.rule_id for candidate in enumeration.candidates}
    assert {
        "surface-space-after-comma",
        "surface-space-after-semicolon",
        "surface-space-after-colon",
        "surface-space-after-question",
        "surface-space-after-exclamation",
        "surface-space-after-period",
    } <= ids


def test_surface_spacing_rule_adds_only_one_space_and_preserves_hard_invariants() -> None:
    registry = development_transform_registry()
    text = "This is stable for https://example.com and value 123. Keep it. Safe."
    enumeration = registry.enumerate(text)
    candidate = next(value for value in enumeration.candidates if value.rule_id == "surface-space-after-is")
    result = registry.apply(enumeration, (candidate.candidate_id,), seed=7)
    assert result.output_text == "This is  stable for https://example.com and value 123. Keep it. Safe."
    assert "https://example.com" in result.output_text
    assert "123" in result.output_text
    assert result.trace.protected_span_violation_count == 0
    assert result.trace.invariant_report.status.value == "pass"


def test_surface_rules_remain_development_only() -> None:
    surface_hashes = {rule.rule_hash for rule in development_surface_rules()}
    default_hashes = {rule.rule_hash for rule in default_transform_registry().rules}
    release_hashes = {rule.rule_hash for rule in release_transform_registry().rules}
    contraction_hashes = {rule.rule_hash for rule in default_contraction_rules()}
    assert default_hashes == contraction_hashes
    assert release_hashes == set()
    assert surface_hashes.isdisjoint(default_hashes)
    assert surface_hashes <= {rule.rule_hash for rule in development_transform_registry().rules}


def test_surface_rules_preserve_e24_protected_span_stress_gate() -> None:
    report = run_e24_protected_span_stress(development_transform_registry())
    assert report.status is E24ProtectedSpanStressStatus.PASS
    assert report.coverage_failure_count == 0
    assert report.protected_violation_count == 0


def test_surface_spacing_rule_rejects_case_mutation_contracts() -> None:
    with pytest.raises(ValueError, match="lowercase alphabetic"):
        SurfaceSpacingRule.create("bad-title", "v1", "Is", "Is ")
    with pytest.raises(ValueError, match="exactly one trailing space"):
        SurfaceSpacingRule.create("bad-edit", "v1", "is", "was ")
