import pytest

from fuckmark.cycle7.density import durable_density_row
from fuckmark.cycle7.durable_rules import (
    cycle7_complementizer_that_rules,
    cycle7_coordinating_conjunction_comma_rules,
    cycle7_discourse_comma_rules,
    cycle7_format_boundary_rules,
    cycle7_parenthetical_adverb_rules,
    cycle7_prenominal_modifier_rules,
)
from fuckmark.cycle7.fixtures import (
    COMPLEMENTIZER_RICH,
    COORD_COMMA_RICH,
    FORMAT_RICH,
    PARENTHETICAL_RICH,
    PRENOMINAL_RICH,
)
from fuckmark.cycle7.registry import cycle7_durable_transform_registry
from fuckmark.cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace, sanitize_cycle7_variant
from fuckmark.transforms.format_rules import FormatConstruction
from fuckmark.transforms.hard_invariants import validate_hard_invariants
from fuckmark.transforms.lexical_rules import LexicalConstruction
from fuckmark.transforms.schema import CandidateRejectionReason, InvariantStatus
from fuckmark.transforms.syntax_rules import SyntaxConstruction


def _apply_rule(text: str, rule_id: str) -> str:
    registry = cycle7_durable_transform_registry()
    enumeration = registry.enumerate(text)
    selected = tuple(
        candidate for candidate in enumeration.candidates if candidate.rule_id == rule_id
    )
    assert selected, (rule_id, tuple(candidate.rule_id for candidate in enumeration.candidates), text)
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    return result.output_text


def test_format_boundary_rules_swap_space_and_newline() -> None:
    rules = cycle7_format_boundary_rules()
    assert len(rules) == 6
    assert all(rule._payload()["construction"] == FormatConstruction.SENTENCE_BOUNDARY_NEWLINE.value for rule in rules)
    text = "Careful testing matters. Independent replication remains required."
    output = _apply_rule(text, "cycle7-format-sentence-period-newline")
    assert output == "Careful testing matters.\nIndependent replication remains required."
    assert collapse_horizontal_ascii_whitespace(output) == output
    for variant in (
        "raw",
        "nfkc",
        "cf_strip",
        "nfkc_cf_strip",
        "ws_collapse",
        "ws_collapse_nfkc_cf_strip",
    ):
        assert sanitize_cycle7_variant(variant, output) == output
    restored = _apply_rule(output, "cycle7-format-sentence-period-space")
    assert restored == text
    assert validate_hard_invariants(text, output).status is InvariantStatus.PASS


def test_format_boundary_blocks_abbreviations_initials_digits_and_ellipsis() -> None:
    registry = cycle7_durable_transform_registry()
    blocked = (
        "Dr. Smith left early.",
        "See Fig. 2 next.",
        "Meet at 3. Next steps wait.",
        "The U.S. Army stayed.",
        "Wait... Next measurements decide.",
        "Hello. world stays lowercase.",
    )
    for text in blocked:
        enumeration = registry.enumerate(text)
        assert not any(
            candidate.rule_id.startswith("cycle7-format-sentence-") for candidate in enumeration.candidates
        ), text


def test_format_question_and_exclamation_boundaries_fire() -> None:
    question = _apply_rule("Does this protocol still hold? Next measurements decide.", "cycle7-format-sentence-question-newline")
    assert question == "Does this protocol still hold?\nNext measurements decide."
    bang = _apply_rule("Stop! Further edits stay local.", "cycle7-format-sentence-exclamation-newline")
    assert bang == "Stop!\nFurther edits stay local."


def test_format_density_on_format_rich_fixture() -> None:
    row = durable_density_row("format-rich", FORMAT_RICH)
    assert int(row["format_candidate_count"]) >= 3


def test_complementizer_that_drop_and_insert_are_bounded() -> None:
    rules = cycle7_complementizer_that_rules()
    assert {rule.construction for rule in rules} == {
        SyntaxConstruction.BOUNDED_COMPLEMENTIZER_THAT_DROP,
        SyntaxConstruction.BOUNDED_COMPLEMENTIZER_THAT_INSERT,
        SyntaxConstruction.BOUNDED_OBJECT_RELATIVE_THAT_DROP,
    }
    dropped = _apply_rule("I think that the protocol works.", "cycle7-syntax-complementizer-that-drop")
    assert dropped == "I think the protocol works."
    inserted = _apply_rule("I think the protocol works.", "cycle7-syntax-complementizer-that-insert")
    assert inserted == "I think that the protocol works."
    relative = _apply_rule("The protocol that we used stayed fixed.", "cycle7-syntax-relative-that-drop")
    assert relative == "The protocol we used stayed fixed."
    assert validate_hard_invariants("I think that the protocol works.", dropped).status is InvariantStatus.PASS


def test_complementizer_false_positives_are_blocked() -> None:
    registry = cycle7_durable_transform_registry()
    blocked = (
        "I found that book on the shelf.",
        "So that the logs remain aligned.",
        "The a that we mentioned is invalid.",
        "I THINK THAT THE PROTOCOL WORKS.",
    )
    for text in blocked:
        enumeration = registry.enumerate(text)
        assert not any(
            candidate.rule_id.startswith("cycle7-syntax-complementizer-")
            or candidate.rule_id.startswith("cycle7-syntax-relative-")
            for candidate in enumeration.candidates
        ), text


def test_complementizer_density_on_rich_fixture() -> None:
    row = durable_density_row("complementizer-rich", COMPLEMENTIZER_RICH)
    assert int(row["complementizer_candidate_count"]) >= 3


def test_discourse_comma_drop_and_insert_are_sentence_initial() -> None:
    assert all(
        rule.construction is LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_COMMA
        for rule in cycle7_discourse_comma_rules()
    )
    dropped = _apply_rule("However, the replica failed.", "lexical-discourse-drop-comma-however")
    assert dropped == "However the replica failed."
    inserted = _apply_rule("However the replica failed.", "lexical-discourse-insert-comma-however")
    assert inserted == "However, the replica failed."
    registry = cycle7_durable_transform_registry()
    degree = registry.enumerate("However much evidence remains, the threshold stays.")
    assert not any(
        candidate.rule_id == "lexical-discourse-insert-comma-however" for candidate in degree.candidates
    )
    mid = registry.enumerate("The replica failed however, the notes stayed.")
    assert not any(
        candidate.rule_id.startswith("lexical-discourse-") for candidate in mid.candidates
    )


def test_prenominal_hyphen_requires_a_following_noun() -> None:
    assert all(
        rule.construction is LexicalConstruction.ATTESTED_PRENOMINAL_HYPHEN_MODIFIER
        for rule in cycle7_prenominal_modifier_rules()
    )
    hyphenated = _apply_rule("A well known method stayed.", "lexical-prenominal-hyphenate-well-known")
    assert hyphenated == "A well-known method stayed."
    opened = _apply_rule("A well-known method stayed.", "lexical-prenominal-open-well-known")
    assert opened == "A well known method stayed."
    registry = cycle7_durable_transform_registry()
    predicative = registry.enumerate("The method is well known.")
    assert not any(
        candidate.rule_id == "lexical-prenominal-hyphenate-well-known" for candidate in predicative.candidates
    )
    row = durable_density_row("prenominal-rich", PRENOMINAL_RICH)
    assert int(row["prenominal_candidate_count"]) >= 3


def test_parenthetical_conjunctive_adverb_is_reversible() -> None:
    assert all(
        rule.construction is SyntaxConstruction.PARENTHETICAL_CONJUNCTIVE_ADVERB
        for rule in cycle7_parenthetical_adverb_rules()
    )
    dropped = _apply_rule(
        "The first replica failed, however, the second replica passed.",
        "cycle7-syntax-parenthetical-drop-however",
    )
    assert dropped == "The first replica failed however the second replica passed."
    restored = _apply_rule(dropped, "cycle7-syntax-parenthetical-insert-however")
    assert restored == "The first replica failed, however, the second replica passed."
    row = durable_density_row("parenthetical-rich", PARENTHETICAL_RICH)
    assert int(row["parenthetical_candidate_count"]) >= 2


def test_coordinating_comma_drop_and_gated_insert() -> None:
    assert all(
        rule.construction is SyntaxConstruction.COORDINATING_CONJUNCTION_COMMA
        for rule in cycle7_coordinating_conjunction_comma_rules()
    )
    dropped = _apply_rule(
        "The first replica failed, and the second replica passed.",
        "cycle7-syntax-coord-comma-drop-and",
    )
    assert dropped == "The first replica failed and the second replica passed."
    inserted = _apply_rule(
        "The first replica failed and the second replica passed.",
        "cycle7-syntax-coord-comma-insert-and",
    )
    assert inserted == "The first replica failed, and the second replica passed."
    registry = cycle7_durable_transform_registry()
    np_coord = registry.enumerate("You and I stayed.")
    assert not any(
        candidate.rule_id == "cycle7-syntax-coord-comma-insert-and" for candidate in np_coord.candidates
    )
    cats = registry.enumerate("Cats and dogs stayed outside.")
    assert not any(
        candidate.rule_id == "cycle7-syntax-coord-comma-insert-and" for candidate in cats.candidates
    )
    numbered = registry.enumerate("Take 1, and 2 together.")
    assert not any(
        candidate.rule_id == "cycle7-syntax-coord-comma-drop-and" for candidate in numbered.candidates
    )
    row = durable_density_row("coord-comma-rich", COORD_COMMA_RICH)
    assert int(row["coord_comma_candidate_count"]) >= 2


def test_stage_b_families_respect_protected_spans_and_quotes() -> None:
    registry = cycle7_durable_transform_registry()
    cases = (
        "Visit https://example.com/path. Continue afterwards.",
        "On 2024-08-25 we do not change the timestamp.",
        "Run `well known` as a literal command token.",
        "Digest deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef is fixed.",
    )
    from fuckmark.transforms import ProtectedSpanExtractor

    for text in cases:
        enumeration = registry.enumerate(text)
        protected = ProtectedSpanExtractor().extract(text).spans
        for candidate in enumeration.candidates:
            assert all(
                not (candidate.start < span.end and span.start < candidate.end)
                for span in protected
            ), (text, candidate.rule_id, candidate.source_text)
    quoted = 'He said, "I think that the protocol works."'
    enumeration = registry.enumerate(quoted)
    selected = tuple(
        candidate
        for candidate in enumeration.candidates
        if candidate.rule_id == "cycle7-syntax-complementizer-that-drop"
    )
    assert selected
    result = registry.apply(enumeration, (selected[0].candidate_id,))
    assert result.output_text.count('"') == quoted.count('"')
    assert result.output_text.startswith('He said, "')
    assert "I think the protocol works" in result.output_text


def test_gpt2_tokenization_changes_for_stage_b_channels() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
    )
    pairs = (
        ("Hello. World", "Hello.\nWorld"),
        ("I think that the protocol works", "I think the protocol works"),
        ("The first replica failed and the second replica passed.", "The first replica failed, and the second replica passed."),
        ("A well known method stayed.", "A well-known method stayed."),
    )
    for left, right in pairs:
        assert tokenizer.encode(left, add_special_tokens=False) != tokenizer.encode(
            right, add_special_tokens=False
        )
