from fuckmark.cycle7.density import durable_density_row
from fuckmark.cycle7.durable_rules import cycle7_compound_rules
from fuckmark.cycle7.fixtures import COMPOUND_RICH
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from fuckmark.transforms import ProtectedSpanExtractor
from fuckmark.transforms.lexical_rules import LexicalConstruction
from fuckmark.transforms.schema import CandidateRejectionReason, TransformFamily


def test_compound_rules_use_attested_construction() -> None:
    rules = cycle7_compound_rules()
    assert rules
    assert all(rule.construction is LexicalConstruction.ATTESTED_OPEN_HYPHEN_COMPOUND for rule in rules)
    assert all(rule.family is TransformFamily.LEXICAL_TEMPLATE for rule in rules)
    assert all(" " in rule.source or "-" in rule.source for rule in rules)
    assert all("  " not in rule.replacement for rule in rules)


def test_open_and_hyphenated_compounds_are_reversible_and_survive_collapse() -> None:
    registry = cycle7_durable_transform_registry()
    text = "A proof of concept needs a point-of-view check."
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate.candidate_id
        for candidate in enumeration.candidates
        if candidate.rule_id
        in {
            "lexical-compound-hyphenate-proof-of-concept",
            "lexical-compound-open-point-of-view",
        }
    )
    assert len(selected) == 2
    result = registry.apply(enumeration, selected)
    assert result.output_text == "A proof-of-concept needs a point of view check."
    assert collapse_horizontal_ascii_whitespace(result.output_text) == result.output_text
    inverse = registry.enumerate(result.output_text)
    reverse = tuple(
        candidate.candidate_id
        for candidate in inverse.candidates
        if candidate.rule_id
        in {
            "lexical-compound-open-proof-of-concept",
            "lexical-compound-hyphenate-point-of-view",
        }
    )
    restored = registry.apply(inverse, reverse)
    assert restored.output_text == text


def test_compound_accepts_sentence_final_punctuation() -> None:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate("This is a proof of concept.")
    selected = tuple(
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "lexical-compound-hyphenate-proof-of-concept"
    )
    assert len(selected) == 1
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    assert result.output_text == "This is a proof-of-concept."


def test_hyphen_chain_and_path_false_positives_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    chained = registry.enumerate("See the proof-of-concept-note before shipping.")
    assert not any(
        candidate.rule_id == "lexical-compound-open-proof-of-concept"
        for candidate in chained.candidates
    )
    assert any(
        rejection.rule_id == "lexical-compound-open-proof-of-concept"
        and rejection.reason is CandidateRejectionReason.PRECONDITION_FAILED
        for rejection in chained.rejections
    )
    incomplete = registry.enumerate("The proof of conceptual coverage is separate.")
    assert not any(
        candidate.rule_id.startswith("lexical-compound-") for candidate in incomplete.candidates
    )
    one_to_one_range = registry.enumerate("Count from one to one hundred carefully.")
    assert not any(
        "one-to-one" in candidate.rule_id for candidate in one_to_one_range.candidates
    )


def test_compound_rules_respect_protected_urls_dates_numbers_and_code() -> None:
    registry = cycle7_durable_transform_registry()
    cases = (
        "Visit https://example.com/proof-of-concept and continue.",
        "On 2024-08-25 the proof of concept remains dated.",
        "Run `proof of concept` as a literal command token.",
        "Figure 3.5 reports the proof of concept result.",
    )
    for text in cases:
        enumeration = registry.enumerate(text)
        protected = ProtectedSpanExtractor().extract(text).spans
        for candidate in enumeration.candidates:
            if not candidate.rule_id.startswith("lexical-compound-"):
                continue
            assert all(
                not (candidate.start < span.end and span.start < candidate.end)
                for span in protected
            ), (text, candidate.rule_id, candidate.source_text)


def test_compound_density_on_compound_rich_fixture() -> None:
    row = durable_density_row("compound-rich", COMPOUND_RICH)
    assert int(row["compound_candidate_count"]) >= 4
    assert collapse_horizontal_ascii_whitespace(COMPOUND_RICH) == COMPOUND_RICH


def test_compound_inside_quotes_does_not_change_delimiters() -> None:
    registry = cycle7_durable_transform_registry()
    text = 'He said, "This proof of concept works."'
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "lexical-compound-hyphenate-proof-of-concept"
    )
    assert len(selected) == 1
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    assert result.output_text == 'He said, "This proof-of-concept works."'
    assert result.output_text.count('"') == text.count('"')
