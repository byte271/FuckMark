from fuckmark.cycle7.durable_rules import (
    cycle7_bounded_copula_rules,
    cycle7_compound_rules,
    cycle7_new_contraction_rules,
    cycle7_orthography_rules,
    rejected_ambiguous_contraction_examples,
)
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from fuckmark.experiments.cycle6_confirmation import CYCLE6_RULESET_HASH
from fuckmark.transforms import ProtectedSpanExtractor, quote_safe_zrd_transform_registry
from fuckmark.transforms.schema import CandidateRejectionReason, TransformFamily


def test_cycle6_quote_safe_ruleset_hash_is_unchanged() -> None:
    assert quote_safe_zrd_transform_registry().ruleset_hash == CYCLE6_RULESET_HASH


def test_cycle7_catalog_excludes_ambiguous_contractions() -> None:
    catalog = (*cycle7_new_contraction_rules(), *cycle7_bounded_copula_rules())
    pairs = {(rule.source.casefold(), rule.replacement.casefold()) for rule in catalog}
    for source, replacement in rejected_ambiguous_contraction_examples():
        assert (source.casefold(), replacement.casefold()) not in pairs
    assert not any(rule.source.casefold() == "it's been" for rule in catalog)


def test_have_contractions_are_reversible_and_survive_collapse() -> None:
    registry = cycle7_durable_transform_registry()
    text = "I have results and they have time."
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate.candidate_id
        for candidate in enumeration.candidates
        if candidate.rule_id in {"cycle7-contract-i-have", "cycle7-contract-they-have"}
    )
    assert len(selected) == 2
    result = registry.apply(enumeration, selected)
    assert "I've" in result.output_text
    assert "they've" in result.output_text
    assert collapse_horizontal_ascii_whitespace(result.output_text) == result.output_text
    inverse = registry.enumerate(result.output_text)
    reverse = tuple(
        candidate.candidate_id
        for candidate in inverse.candidates
        if candidate.rule_id in {"cycle7-expand-i-have", "cycle7-expand-they-have"}
    )
    restored = registry.apply(inverse, reverse)
    assert restored.output_text == text


def test_bounded_its_important_is_unambiguous_and_ignores_its_been() -> None:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate("It's important to keep logs and it's been archived.")
    selected = tuple(
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "cycle7-expand-its-important"
    )
    assert len(selected) == 1
    assert selected[0].source_text == "It's important"
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    assert "It is important to keep logs" in result.output_text
    assert "it's been archived" in result.output_text
    assert not any(
        candidate.source_text.casefold() == "it's been" for candidate in enumeration.candidates
    )
    assert not any(candidate.rule_id.endswith("its-not") for candidate in enumeration.candidates)
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate("We do not stop.")
    forward = next(candidate for candidate in enumeration.candidates if candidate.rule_id == "contract-do-not")
    result = registry.apply(enumeration, (forward.candidate_id,))
    assert result.output_text == "We don't stop."
    assert collapse_horizontal_ascii_whitespace(result.output_text) == "We don't stop."


def test_orthography_towards_among_is_reversible() -> None:
    registry = cycle7_durable_transform_registry()
    text = "Walk towards the gate amongst the trees."
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate.candidate_id
        for candidate in enumeration.candidates
        if candidate.rule_id in {"cycle7-ortho-towards-toward", "cycle7-ortho-amongst-among"}
    )
    assert len(selected) == 2
    result = registry.apply(enumeration, selected)
    assert result.output_text == "Walk toward the gate among the trees."
    ids = {rule.rule_id for rule in cycle7_orthography_rules()}
    assert "cycle7-ortho-toward-towards" in ids


def test_false_positive_grammar_and_all_caps_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    assert not any(
        candidate.rule_id == "contract-do-not"
        for candidate in registry.enumerate("The donor notes were archived.").candidates
    )
    enumeration = registry.enumerate("WE DO NOT STOP.")
    assert any(
        rejection.rule_id == "contract-do-not"
        and rejection.reason is CandidateRejectionReason.ALL_CAPS_BLOCKED
        for rejection in enumeration.rejections
    )


def test_protected_spans_block_durable_rewrites() -> None:
    registry = cycle7_durable_transform_registry(("CamelCaseThing",))
    cases = (
        "Visit https://example.com/path and continue.",
        "The value 12 is exact.",
        "On 2024-08-25 we do not change the timestamp.",
        "Run `do not` as a literal command token.",
        "Keep CamelCaseThing intact while they are waiting.",
        "The binary /usr/bin/true stays put.",
        r"File C:\Windows\System32\drivers stays put.",
        "Digest deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef is fixed.",
        "Prior work [1] remains cited.",
        "Write lab@example.com immediately.",
    )
    for text in cases:
        enumeration = registry.enumerate(text)
        protected = ProtectedSpanExtractor().extract(text).spans
        for candidate in enumeration.candidates:
            assert all(
                not (candidate.start < span.end and span.start < candidate.end)
                for span in protected
            ), (text, candidate.rule_id, candidate.source_text)


def test_punctuation_url_and_number_boundaries_do_not_fire_inside_tokens() -> None:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate("See do-not-touch and donor.")
    assert not any(candidate.rule_id == "contract-do-not" for candidate in enumeration.candidates)


def test_durable_rules_are_not_spacing_family() -> None:
    for rule in (*cycle7_new_contraction_rules(), *cycle7_orthography_rules(), *cycle7_compound_rules()):
        assert rule.family in {
            TransformFamily.CONTRACTION,
            TransformFamily.ORTHOGRAPHY,
            TransformFamily.LEXICAL_TEMPLATE,
        }
        assert not rule.source.endswith(" ")
        assert "  " not in rule.replacement
