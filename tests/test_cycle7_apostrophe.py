from fuckmark.cycle7.density import durable_density_row
from fuckmark.cycle7.durable_rules import cycle7_typographic_apostrophe_rules
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace, sanitize_cycle7_variant
from fuckmark.transforms.hard_invariants import validate_hard_invariants
from fuckmark.transforms.lexical_rules import LexicalConstruction
from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus, TransformFamily


def test_typographic_apostrophe_rules_are_inword_and_reversible() -> None:
    rules = cycle7_typographic_apostrophe_rules()
    assert len(rules) == 2
    assert all(rule.construction is LexicalConstruction.INWORD_TYPOGRAPHIC_APOSTROPHE for rule in rules)
    assert all(rule.family is TransformFamily.LEXICAL_TEMPLATE for rule in rules)
    registry = cycle7_durable_transform_registry()
    text = "It's ready and we don't wait."
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate.candidate_id
        for candidate in enumeration.candidates
        if candidate.rule_id == "lexical-apostrophe-ascii-to-typographic"
    )
    assert len(selected) == 2
    result = registry.apply(enumeration, selected)
    assert "'" not in result.output_text
    assert "\u2019" in result.output_text
    assert collapse_horizontal_ascii_whitespace(result.output_text) == result.output_text
    for variant in (
        "raw",
        "nfkc",
        "cf_strip",
        "nfkc_cf_strip",
        "ws_collapse",
        "ws_collapse_nfkc_cf_strip",
    ):
        assert sanitize_cycle7_variant(variant, result.output_text) == result.output_text
    inverse = registry.enumerate(result.output_text)
    reverse = tuple(
        candidate.candidate_id
        for candidate in inverse.candidates
        if candidate.rule_id == "lexical-apostrophe-typographic-to-ascii"
    )
    restored = registry.apply(inverse, reverse)
    assert restored.output_text == text
    report = validate_hard_invariants(text, result.output_text)
    assert report.status is InvariantStatus.PASS


def test_typographic_apostrophe_skips_quote_delimiters_and_plural_possessives() -> None:
    registry = cycle7_durable_transform_registry()
    quoted = registry.enumerate("'Keep this quoted.'")
    assert not any(
        candidate.rule_id.startswith("lexical-apostrophe-") for candidate in quoted.candidates
    )
    possessive = registry.enumerate("The students' notes remained.")
    assert not any(
        candidate.rule_id.startswith("lexical-apostrophe-") for candidate in possessive.candidates
    )


def test_typographic_apostrophe_all_caps_and_code_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    all_caps = registry.enumerate("WE DON'T STOP.")
    assert not any(
        candidate.rule_id.startswith("lexical-apostrophe-") for candidate in all_caps.candidates
    )
    assert any(
        rejection.rule_id == "lexical-apostrophe-ascii-to-typographic"
        and rejection.reason is CandidateRejectionReason.PRECONDITION_FAILED
        for rejection in all_caps.rejections
    )
    code = registry.enumerate("Run `don't` as a literal command token.")
    assert not any(
        candidate.rule_id.startswith("lexical-apostrophe-") for candidate in code.candidates
    )


def test_typographic_apostrophe_density_on_contraction_prose() -> None:
    row = durable_density_row("apostrophe-prose", "It's not uncommon, and I've seen it.")
    assert "lexical-apostrophe-ascii-to-typographic" in row["rule_ids"]
    assert int(row["candidate_count"]) >= 2
