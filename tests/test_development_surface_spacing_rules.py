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
from fuckmark.transforms.rules import SurfaceSpacingRule
from fuckmark.transforms.surface_rules import development_surface_rules


def test_surface_spacing_rules_are_case_safe_tier_one_orthography() -> None:
    rules = development_surface_rules()
    assert tuple(rule.rule_id for rule in rules) == (
        "surface-space-after-is",
        "surface-space-after-of",
        "surface-space-after-to",
        "surface-space-after-period",
    )
    assert all(isinstance(rule, SurfaceSpacingRule) for rule in rules)
    assert all(rule.family is TransformFamily.ORTHOGRAPHY for rule in rules)
    assert all(rule.tier is TransformTier.SURFACE for rule in rules)
    assert all(rule.replacement == rule.source + " " for rule in rules)
    assert len({rule.rule_hash for rule in rules}) == len(rules)


def test_word_spacing_rule_requires_lowercase_word_followed_by_whitespace() -> None:
    rule = development_surface_rules()[0]
    assert tuple(match.group(0) for match in rule.pattern().finditer("this is stable")) == ("is",)
    assert tuple(match.group(0) for match in rule.pattern().finditer("Is this stable?")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is, this stable?")) == ()
    assert tuple(match.group(0) for match in rule.pattern().finditer("is\nnext")) == ("is",)


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
    assert default_hashes == release_hashes == contraction_hashes
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
