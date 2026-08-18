import pytest

from fuckmark.transforms import (
    InvariantStatus,
    TransformFamily,
    TransformTier,
    development_transform_registry,
)
from fuckmark.transforms.format_rules import FormatTransformRule, development_format_rules
from fuckmark.transforms.rules import LiteralTransformRule, default_contraction_rules
from fuckmark.transforms.surface_rules import development_surface_rules


def test_format_rule_is_explicit_tier_zero_and_multiline_only_there() -> None:
    (rule,) = development_format_rules()
    assert isinstance(rule, FormatTransformRule)
    assert rule.family is TransformFamily.FORMAT
    assert rule.tier is TransformTier.FORMAT
    assert rule.source == "\n\n"
    assert rule.replacement == "\n"
    assert not rule.whole_word
    assert not rule.preserve_simple_case
    assert not rule.block_all_caps
    with pytest.raises(ValueError, match="single-line"):
        LiteralTransformRule.create(
            rule_id="invalid-multiline-surface",
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.SURFACE,
            source="\n\n",
            replacement="\n",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
        )


def test_development_registry_collapses_blank_line_without_changing_words() -> None:
    registry = development_transform_registry()
    text = "First paragraph.\n\nSecond paragraph."
    enumeration = registry.enumerate(text)
    candidate = next(
        value for value in enumeration.candidates
        if value.rule_id == "format-collapse-blank-line"
    )
    result = registry.apply(enumeration, (candidate.candidate_id,), seed=7)
    assert result.output_text == "First paragraph.\nSecond paragraph."
    assert result.trace.invariant_report.status is InvariantStatus.PASS
    assert result.trace.protected_span_violation_count == 0


def test_surface_period_spacing_rule_is_tier_one_orthography() -> None:
    (rule,) = development_surface_rules()
    assert rule.family is TransformFamily.ORTHOGRAPHY
    assert rule.tier is TransformTier.SURFACE
    assert rule.source == ". "
    assert rule.replacement == ".  "
    registry = development_transform_registry()
    text = "One sentence. Another sentence. Final sentence."
    enumeration = registry.enumerate(text)
    candidates = tuple(
        value for value in enumeration.candidates
        if value.rule_id == "surface-period-space-double"
    )
    assert len(candidates) == 2
    result = registry.apply(
        enumeration,
        tuple(value.candidate_id for value in candidates),
        seed=11,
    )
    assert result.output_text == "One sentence.  Another sentence.  Final sentence."
    assert result.trace.invariant_report.status is InvariantStatus.PASS


def test_development_registry_adds_rules_without_changing_default_contraction_identity() -> None:
    contractions = default_contraction_rules()
    development = development_transform_registry()
    by_identity = {(rule.rule_id, rule.version): rule.rule_hash for rule in development.rules}
    for rule in contractions:
        assert by_identity[(rule.rule_id, rule.version)] == rule.rule_hash
    assert ("format-collapse-blank-line", "v1") in by_identity
    assert ("surface-period-space-double", "v1") in by_identity


def test_format_rule_rejects_carriage_returns_and_case_semantics() -> None:
    with pytest.raises(ValueError, match="carriage returns"):
        FormatTransformRule.create("bad-cr", "v1", "\r\n", "\n")
    with pytest.raises(ValueError, match="format family"):
        FormatTransformRule(
            rule_id="bad-family",
            version="v1",
            family=TransformFamily.ORTHOGRAPHY,
            tier=TransformTier.FORMAT,
            source="\n\n",
            replacement="\n",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash="0" * 64,
        )
