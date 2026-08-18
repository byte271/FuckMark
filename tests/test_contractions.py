from __future__ import annotations

from fuckmark.transforms.contractions import (
    context_survival_contraction_rules,
    contraction_semantic_site,
    reverse_contraction_rules,
    reversible_contraction_metadata,
)
from fuckmark.transforms.protected_artifacts import UserProtectedRange
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import default_contraction_rules
from fuckmark.transforms.schema import CandidateRejectionReason, TransformFamily, TransformTier


def test_reversible_metadata_matches_existing_forward_rules() -> None:
    metadata = reversible_contraction_metadata()
    forward = {rule.rule_id: rule for rule in default_contraction_rules()}
    assert len(metadata) == 6
    assert len({value.inverse_semantic_group_id for value in metadata}) == 6
    assert len({value.metadata_hash for value in metadata}) == 6
    for value in metadata:
        rule = forward[value.forward_rule_id]
        assert rule.source == value.expanded_form
        assert rule.replacement == value.contracted_form
        assert value.reverse_rule_id.startswith("expand-")


def test_reverse_rules_are_exact_tier_one_contraction_inverses() -> None:
    metadata = {value.reverse_rule_id: value for value in reversible_contraction_metadata()}
    rules = reverse_contraction_rules()
    assert len(rules) == 6
    for rule in rules:
        value = metadata[rule.rule_id]
        assert rule.family is TransformFamily.CONTRACTION
        assert rule.tier is TransformTier.SURFACE
        assert rule.source == value.contracted_form
        assert rule.replacement == value.expanded_form
        assert rule.whole_word is True
        assert rule.preserve_simple_case is True
        assert rule.block_all_caps is True


def test_reverse_contraction_preserves_supported_simple_case() -> None:
    registry = TransformRegistry(reverse_contraction_rules())
    enumeration = registry.enumerate("Don't stop.")
    candidates = tuple(value for value in enumeration.candidates if value.rule_id == "expand-do-not")
    assert len(candidates) == 1
    result = registry.apply(enumeration, (candidates[0].candidate_id,))
    assert result.output_text == "Do not stop."


def test_reverse_contraction_blocks_all_caps() -> None:
    registry = TransformRegistry(reverse_contraction_rules())
    enumeration = registry.enumerate("DON'T STOP.")
    assert not enumeration.candidates
    matching = tuple(value for value in enumeration.rejections if value.rule_id == "expand-do-not")
    assert len(matching) == 1
    assert matching[0].reason is CandidateRejectionReason.ALL_CAPS_BLOCKED


def test_reverse_contraction_respects_user_protected_range() -> None:
    registry = TransformRegistry(reverse_contraction_rules())
    text = "We don't agree."
    start = text.index("don't")
    protected = (UserProtectedRange.create(start, start + len("don't"), "quoted-form"),)
    enumeration = registry.enumerate(text, protected)
    assert not enumeration.candidates
    matching = tuple(value for value in enumeration.rejections if value.rule_id == "expand-do-not")
    assert len(matching) == 1
    assert matching[0].reason is CandidateRejectionReason.PROTECTED_OVERLAP


def test_combined_catalog_keeps_forward_and_reverse_rule_ids_unique() -> None:
    rules = context_survival_contraction_rules()
    assert len(rules) == 12
    assert len({(rule.rule_id, rule.version) for rule in rules}) == 12
    assert len({rule.rule_hash for rule in rules}) == 12


def test_semantic_site_is_stable_across_forward_then_reverse() -> None:
    registry = TransformRegistry(context_survival_contraction_rules())
    text = "We do not agree, and they do not agree."
    first = registry.enumerate(text)
    forward = tuple(value for value in first.candidates if value.rule_id == "contract-do-not")
    assert len(forward) == 2
    selected = forward[1]
    before = contraction_semantic_site(text, selected)
    assert before is not None
    result = registry.apply(first, (selected.candidate_id,))
    second = registry.enumerate(result.output_text)
    reverse = tuple(
        value
        for value in second.candidates
        if value.rule_id == "expand-do-not" and value.start > result.output_text.index("and")
    )
    assert len(reverse) == 1
    after = contraction_semantic_site(result.output_text, reverse[0])
    assert after is not None
    assert before.group_id == after.group_id
    assert before.site_id == after.site_id
    assert before.direction == "forward"
    assert after.direction == "reverse"
