from dataclasses import replace

import pytest

from fuckmark.experiments.normalization_survival import (
    N4_COPY_PASTE_WHITESPACE,
    normalization_profiles,
    normalize_text,
)
from fuckmark.transforms import (
    DURABLE_SURFACE_PAIR_ALGORITHM_VERSION,
    DURABLE_SURFACE_RULE_ALGORITHM_VERSION,
    DURABLE_SURFACE_RULESET_VERSION,
    CandidateRejectionReason,
    DurableSurfaceConstruction,
    DurableSurfaceRule,
    TransformFamily,
    TransformTier,
    default_transform_registry,
    development_durable_surface_rules,
    development_transform_registry,
    durable_portfolio_transform_registry,
    durable_semantic_site,
    durable_surface_pairs,
)


def _candidate(registry, text: str, rule_id: str):
    enumeration = registry.enumerate(text)
    candidates = tuple(value for value in enumeration.candidates if value.rule_id == rule_id)
    assert len(candidates) == 1
    return enumeration, candidates[0]


def test_durable_catalog_has_distinct_versioned_inverse_pairs() -> None:
    pairs = durable_surface_pairs()
    rules = development_durable_surface_rules()
    assert DURABLE_SURFACE_PAIR_ALGORITHM_VERSION == "durable-surface-pair-v1"
    assert DURABLE_SURFACE_RULE_ALGORITHM_VERSION == "durable-surface-rule-v1"
    assert DURABLE_SURFACE_RULESET_VERSION == "development-durable-surface-rules-v1"
    assert len(pairs) == 7
    assert len(rules) == 14
    assert len({value.pair_id for value in pairs}) == 7
    assert len({value.pair_hash for value in pairs}) == 7
    assert len({value.rule_id for value in rules}) == 14
    assert len({value.rule_hash for value in rules}) == 14
    assert sum(value.tier is TransformTier.FORMAT for value in rules) == 4
    assert sum(value.tier is TransformTier.SURFACE for value in rules) == 10


@pytest.mark.parametrize(
    ("source", "forward_id", "transformed", "reverse_id"),
    (
        (
            "I have written the report.",
            "durable-perfect-i-have-contract",
            "I've written the report.",
            "durable-perfect-i-have-expand",
        ),
        (
            "You have already seen it.",
            "durable-perfect-you-have-contract",
            "You've already seen it.",
            "durable-perfect-you-have-expand",
        ),
        (
            "We have tested the build.",
            "durable-perfect-we-have-contract",
            "We've tested the build.",
            "durable-perfect-we-have-expand",
        ),
        (
            "They have been careful.",
            "durable-perfect-they-have-contract",
            "They've been careful.",
            "durable-perfect-they-have-expand",
        ),
    ),
)
def test_guarded_contractions_replay_in_both_directions(
    source: str,
    forward_id: str,
    transformed: str,
    reverse_id: str,
) -> None:
    registry = durable_portfolio_transform_registry()
    first, forward = _candidate(registry, source, forward_id)
    result = registry.apply(first, (forward.candidate_id,))
    assert result.output_text == transformed
    second, reverse = _candidate(registry, transformed, reverse_id)
    replay = registry.apply(second, (reverse.candidate_id,))
    assert replay.output_text == source
    before = durable_semantic_site(source, forward)
    after = durable_semantic_site(transformed, reverse)
    assert before is not None
    assert after is not None
    assert before.group_id == after.group_id
    assert before.site_id == after.site_id
    assert before.direction == "forward"
    assert after.direction == "reverse"


@pytest.mark.parametrize(
    "source",
    (
        "We have to leave.",
        "We have not finished.",
        "We have a plan.",
        "We have confidence.",
        "We have.",
        "We have already carefully tested it.",
    ),
)
def test_perfect_auxiliary_guard_rejects_unqualified_contexts(source: str) -> None:
    enumeration = durable_portfolio_transform_registry().enumerate(source)
    matching = tuple(
        value
        for value in enumeration.rejections
        if value.rule_id == "durable-perfect-we-have-contract"
    )
    assert len(matching) == 1
    assert matching[0].reason is CandidateRejectionReason.PRECONDITION_FAILED


@pytest.mark.parametrize(
    ("source", "rule_id", "transformed", "reverse_id"),
    (
        (
            "Wait... continue.",
            "durable-ellipsis-unicode",
            "Wait… continue.",
            "durable-ellipsis-ascii",
        ),
        (
            "- first",
            "durable-markdown-bullet-star",
            "* first",
            "durable-markdown-bullet-dash",
        ),
        (
            "1. first",
            "durable-markdown-ordered-paren",
            "1) first",
            "durable-markdown-ordered-dot",
        ),
    ),
)
def test_punctuation_variants_are_reversible_and_n4_durable(
    source: str,
    rule_id: str,
    transformed: str,
    reverse_id: str,
) -> None:
    registry = durable_portfolio_transform_registry()
    enumeration, candidate = _candidate(registry, source, rule_id)
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == transformed
    profile = next(
        value
        for value in normalization_profiles()
        if value.profile_id == N4_COPY_PASTE_WHITESPACE
    )
    assert normalize_text(source, profile) != normalize_text(transformed, profile)
    reverse_enumeration, reverse = _candidate(registry, transformed, reverse_id)
    replay = registry.apply(reverse_enumeration, (reverse.candidate_id,))
    assert replay.output_text == source


def test_punctuation_guards_exclude_numbers_runs_and_non_list_contexts() -> None:
    registry = durable_portfolio_transform_registry()
    enumeration = registry.enumerate("Version 1...3 stays. Wait.... Inline - text. 12. item")
    assert all(
        not value.rule_id.startswith("durable-ellipsis")
        and not value.rule_id.startswith("durable-markdown")
        for value in enumeration.candidates
    )


def test_durable_candidates_remain_excluded_from_existing_policies() -> None:
    source = "We have tested it. Wait... continue."
    assert all(
        not value.rule_id.startswith("durable-")
        for value in default_transform_registry().enumerate(source).candidates
    )
    assert all(
        not value.rule_id.startswith("durable-")
        for value in development_transform_registry().enumerate(source).candidates
    )
    portfolio = durable_portfolio_transform_registry().enumerate(source)
    assert len(
        [value for value in portfolio.candidates if value.rule_id.startswith("durable-")]
    ) == 2


def test_durable_rules_fail_closed_inside_protected_content() -> None:
    registry = durable_portfolio_transform_registry()
    enumeration = registry.enumerate(
        'Outside text. "We have tested it. Wait..." and `- code`.'
    )
    assert all(not value.rule_id.startswith("durable-") for value in enumeration.candidates)
    reasons = {
        value.reason
        for value in enumeration.rejections
        if value.rule_id.startswith("durable-")
    }
    assert reasons == {CandidateRejectionReason.PROTECTED_OVERLAP}


def test_durable_rule_rejects_rehashed_semantic_tampering() -> None:
    rule = development_durable_surface_rules()[0]
    assert rule.family is TransformFamily.CONTRACTION
    assert rule.construction is DurableSurfaceConstruction.PERFECT_AUXILIARY
    with pytest.raises(ValueError, match="rule_hash"):
        replace(
            rule,
            allowed_following_words=tuple(
                sorted((*rule.allowed_following_words, "zipped"))
            ),
        )


def test_durable_rule_rejects_construction_and_matching_contract_drift() -> None:
    with pytest.raises(ValueError, match="forms"):
        DurableSurfaceRule.create(
            rule_id="invalid-ellipsis",
            source="--",
            replacement="…",
            construction=DurableSurfaceConstruction.ELLIPSIS,
        )
    rule = development_durable_surface_rules()[0]
    with pytest.raises(ValueError, match="matching flags"):
        replace(rule, whole_word=False)


def test_perfect_auxiliary_all_caps_remains_blocked() -> None:
    enumeration = durable_portfolio_transform_registry().enumerate(
        "WE HAVE TESTED THE BUILD."
    )
    matching = tuple(
        value
        for value in enumeration.rejections
        if value.rule_id == "durable-perfect-we-have-contract"
    )
    assert len(matching) == 1
    assert matching[0].reason is CandidateRejectionReason.ALL_CAPS_BLOCKED
