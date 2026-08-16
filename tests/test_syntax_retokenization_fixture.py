from dataclasses import replace

import pytest

from corpus_helpers import model_identity
from fuckmark.hashing import sha256_json
from fuckmark.transforms.syntax_rules import SyntaxConstruction, SyntaxTemplateRule, development_syntax_rules
from fuckmark.transforms.syntax_tokenization import (
    SYNTAX_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION,
    SyntaxRetokenizationVerificationError,
    capture_syntax_retokenization_fixture,
    verify_syntax_retokenization_fixture,
)


def _tokenizer(text: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in text)


def test_syntax_retokenization_fixture_captures_identity_and_replays() -> None:
    rule = development_syntax_rules()[0]
    identity = model_identity()
    fixture = capture_syntax_retokenization_fixture(
        "toy-syntax-retokenization",
        rule,
        identity,
        "The build passed; however, the deploy failed.",
        _tokenizer,
    )
    assert fixture.algorithm_version == SYNTAX_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION
    assert fixture.transformed_text == "The build passed. However, the deploy failed."
    verify_syntax_retokenization_fixture(fixture, rule, identity, _tokenizer)


def test_syntax_retokenization_verifier_rejects_self_valid_token_forgery() -> None:
    rule = development_syntax_rules()[0]
    identity = model_identity()
    fixture = capture_syntax_retokenization_fixture(
        "toy-syntax-retokenization",
        rule,
        identity,
        "The build passed; however, the deploy failed.",
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
    with pytest.raises(SyntaxRetokenizationVerificationError, match="source tokens do not replay"):
        verify_syntax_retokenization_fixture(forged, rule, identity, _tokenizer)


def test_syntax_retokenization_verifier_rejects_rule_identity_drift() -> None:
    rule = development_syntax_rules()[0]
    identity = model_identity()
    fixture = capture_syntax_retokenization_fixture(
        "toy-syntax-retokenization",
        rule,
        identity,
        "The build passed; however, the deploy failed.",
        _tokenizer,
    )
    changed_rule = SyntaxTemplateRule.create(
        "syntax-semicolon-however-split-alt",
        "v1",
        "; however, ",
        ". Nevertheless, ",
        SyntaxConstruction.SEMICOLON_CONJUNCTIVE_ADVERB_SPLIT,
    )
    with pytest.raises(SyntaxRetokenizationVerificationError, match="rule hash"):
        verify_syntax_retokenization_fixture(fixture, changed_rule, identity, _tokenizer)


def test_syntax_retokenization_capture_requires_exactly_one_candidate() -> None:
    rule = development_syntax_rules()[0]
    with pytest.raises(ValueError, match="exactly one syntax candidate"):
        capture_syntax_retokenization_fixture(
            "two-syntax-candidates",
            rule,
            model_identity(),
            "The first build passed; however, the first deploy failed. The second build passed; however, the second deploy failed.",
            _tokenizer,
        )
