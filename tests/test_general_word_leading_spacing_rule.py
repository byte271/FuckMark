import unicodedata

import pytest

from fuckmark.transforms.hard_invariants import validate_hard_invariants
from fuckmark.transforms.registry import TransformRegistry
from fuckmark.transforms.rules import (
    GENERAL_WORD_LEADING_SPACING_RULE_VERSION,
    GeneralWordLeadingSpacingRule,
)


SENTENCE_TEXT = "The first sentence ends here. Another sentence starts? Yes it does! Final words."


def leading_rule() -> GeneralWordLeadingSpacingRule:
    return GeneralWordLeadingSpacingRule.create("surface-space-before-sentence")


def test_general_word_leading_spacing_rule_version_is_pinned():
    assert GENERAL_WORD_LEADING_SPACING_RULE_VERSION == "general-word-space-before-v1"


def test_leading_rule_matches_sentence_initial_words_only():
    rule = leading_rule()
    spans = [match.span() for match in rule.pattern().finditer(SENTENCE_TEXT)]
    assert len(spans) == 3
    starts = [SENTENCE_TEXT[start:end] for start, end in spans]
    assert starts == ["Another", "Yes", "Final"]


def test_leading_rule_replacement_prepends_exactly_one_space():
    rule = leading_rule()
    match = next(rule.pattern().finditer(SENTENCE_TEXT))
    replacement = rule.replacement_for(match.group(0))
    assert replacement == " " + match.group(0)
    transformed = SENTENCE_TEXT[: match.start()] + replacement + SENTENCE_TEXT[match.end() :]
    assert transformed.count("Another") == 1
    assert " ends here.  Another" in transformed


def test_leading_rule_output_is_nfc_stable_and_single_line():
    rule = leading_rule()
    transformed = rule.pattern().sub(lambda m: " " + m.group(0), SENTENCE_TEXT)
    assert unicodedata.normalize("NFC", transformed) == transformed
    assert "\n" not in transformed and "\r" not in transformed


def test_leading_rule_does_not_touch_document_start():
    rule = leading_rule()
    text = "Document start has no preceding punctuation."
    assert list(rule.pattern().finditer(text)) == []


def test_leading_rule_survives_hard_invariants():
    rule = leading_rule()
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate(SENTENCE_TEXT)
    assert enumeration.candidates
    result = registry.apply(enumeration, [candidate.candidate_id for candidate in enumeration.candidates])
    report = validate_hard_invariants(SENTENCE_TEXT, result.output_text, (), ())
    assert str(report.status.value).lower() == "pass"


def test_leading_rule_wording_bytes_are_preserved_outside_spaces():
    rule = leading_rule()
    transformed = rule.pattern().sub(lambda m: " " + m.group(0), SENTENCE_TEXT)
    assert transformed.replace(" ", "") == SENTENCE_TEXT.replace(" ", "")


def test_leading_rule_rejects_wrong_sentinel_contract():
    with pytest.raises(ValueError):
        GeneralWordLeadingSpacingRule(
            rule_id="bad-rule",
            version=GENERAL_WORD_LEADING_SPACING_RULE_VERSION,
            family=None,
            tier=None,
            source="word ",
            replacement="word ",
            whole_word=False,
            preserve_simple_case=False,
            block_all_caps=False,
            rule_hash="0" * 64,
        )
