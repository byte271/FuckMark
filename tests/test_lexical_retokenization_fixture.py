from dataclasses import replace

import pytest

from corpus_helpers import model_identity
from fuckmark.hashing import sha256_json
from fuckmark.transforms.lexical_rules import LexicalConstruction, LexicalTemplateRule, development_lexical_rules
from fuckmark.transforms.lexical_tokenization import (
    LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION,
    LexicalRetokenizationVerificationError,
    capture_lexical_retokenization_fixture,
    verify_lexical_retokenization_fixture,
)


def _tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def test_lexical_retokenization_fixture_captures_pinned_identity_and_replays() -> None:
    rule = development_lexical_rules()[0]
    identity = model_identity()
    fixture = capture_lexical_retokenization_fixture(
        "toy-retokenization",
        rule,
        identity,
        "For example, use a cache.",
        _tokenizer,
    )
    assert fixture.algorithm_version == LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION
    assert fixture.transformed_text == "For instance, use a cache."
    assert fixture.source_token_ids == _tokenizer(fixture.source_text)
    assert fixture.transformed_token_ids == _tokenizer(fixture.transformed_text)
    verify_lexical_retokenization_fixture(fixture, rule, identity, _tokenizer)


def test_lexical_retokenization_verifier_rejects_self_valid_token_forgery() -> None:
    rule = development_lexical_rules()[0]
    identity = model_identity()
    fixture = capture_lexical_retokenization_fixture(
        "toy-retokenization",
        rule,
        identity,
        "For example, use a cache.",
        _tokenizer,
    )
    forged_tokens = (999, *fixture.source_token_ids[1:])
    forged_payload = fixture._payload()
    forged_payload["source_token_ids"] = forged_tokens
    forged_payload["source_token_hash"] = sha256_json(forged_tokens)
    forged = replace(
        fixture,
        source_token_ids=forged_tokens,
        source_token_hash=sha256_json(forged_tokens),
        fixture_hash=sha256_json(forged_payload),
    )
    with pytest.raises(LexicalRetokenizationVerificationError, match="source tokens do not replay"):
        verify_lexical_retokenization_fixture(forged, rule, identity, _tokenizer)


def test_lexical_retokenization_verifier_rejects_rule_and_tokenizer_identity_drift() -> None:
    rule = development_lexical_rules()[0]
    identity = model_identity()
    fixture = capture_lexical_retokenization_fixture(
        "toy-retokenization",
        rule,
        identity,
        "For example, use a cache.",
        _tokenizer,
    )
    changed_rule = LexicalTemplateRule.create(
        "lexical-for-example-for-instance-alt",
        "v1",
        "for example,",
        "for illustration,",
        LexicalConstruction.SENTENCE_INITIAL_DISCOURSE_MARKER,
    )
    with pytest.raises(LexicalRetokenizationVerificationError, match="rule hash"):
        verify_lexical_retokenization_fixture(fixture, changed_rule, identity, _tokenizer)
    other_identity = model_identity()
    other_identity = replace(
        other_identity,
        tokenizer_id="example/other-tokenizer",
        identity_hash="0" * 64,
    )
    with pytest.raises(ValueError, match="identity_hash"):
        verify_lexical_retokenization_fixture(fixture, rule, other_identity, _tokenizer)


def test_lexical_retokenization_capture_requires_exactly_one_candidate() -> None:
    rule = development_lexical_rules()[0]
    identity = model_identity()
    with pytest.raises(ValueError, match="exactly one lexical candidate"):
        capture_lexical_retokenization_fixture(
            "ambiguous-source",
            rule,
            identity,
            "For example, first. For example, second.",
            _tokenizer,
        )
