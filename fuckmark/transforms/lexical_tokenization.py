from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .._validation import normalize_token_sequence, require_clean_string, require_sha256
from ..corpus import ModelTokenizerIdentity
from ..hashing import sha256_json, sha256_text
from .lexical_rules import LexicalTemplateRule
from .registry import TransformRegistry


LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION = "lexical-retokenization-fixture-v1"


class LexicalRetokenizationVerificationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LexicalRetokenizationFixture:
    algorithm_version: str
    fixture_id: str
    rule_hash: str
    model_tokenizer_identity_hash: str
    source_text: str
    transformed_text: str
    source_text_hash: str
    transformed_text_hash: str
    source_token_ids: tuple[int, ...]
    transformed_token_ids: tuple[int, ...]
    source_token_hash: str
    transformed_token_hash: str
    fixture_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION:
            raise ValueError("unsupported lexical retokenization fixture algorithm version")
        require_clean_string("fixture_id", self.fixture_id)
        require_sha256("rule_hash", self.rule_hash)
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        if not isinstance(self.source_text, str) or not self.source_text:
            raise ValueError("source_text must be a non-empty string")
        if not isinstance(self.transformed_text, str) or not self.transformed_text:
            raise ValueError("transformed_text must be a non-empty string")
        if self.source_text == self.transformed_text:
            raise ValueError("retokenization fixture must contain a text transformation")
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.source_text_hash != sha256_text(self.source_text):
            raise ValueError("source_text_hash does not match source_text")
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        source_tokens = normalize_token_sequence("source_token_ids", self.source_token_ids)
        transformed_tokens = normalize_token_sequence("transformed_token_ids", self.transformed_token_ids)
        if not source_tokens or not transformed_tokens:
            raise ValueError("retokenization token sequences must not be empty")
        if source_tokens != self.source_token_ids or transformed_tokens != self.transformed_token_ids:
            raise ValueError("retokenization token sequences must be canonical tuples")
        require_sha256("source_token_hash", self.source_token_hash)
        require_sha256("transformed_token_hash", self.transformed_token_hash)
        if self.source_token_hash != sha256_json(source_tokens):
            raise ValueError("source_token_hash does not match source_token_ids")
        if self.transformed_token_hash != sha256_json(transformed_tokens):
            raise ValueError("transformed_token_hash does not match transformed_token_ids")
        require_sha256("fixture_hash", self.fixture_hash)
        if self.fixture_hash != sha256_json(self._payload()):
            raise ValueError("fixture_hash does not match lexical retokenization fixture")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "fixture_id": self.fixture_id,
            "rule_hash": self.rule_hash,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "source_text": self.source_text,
            "transformed_text": self.transformed_text,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "source_token_ids": self.source_token_ids,
            "transformed_token_ids": self.transformed_token_ids,
            "source_token_hash": self.source_token_hash,
            "transformed_token_hash": self.transformed_token_hash,
        }


def _transform_once(rule: LexicalTemplateRule, source_text: str) -> str:
    if not isinstance(rule, LexicalTemplateRule):
        raise TypeError("rule must be a LexicalTemplateRule")
    registry = TransformRegistry((rule,))
    enumeration = registry.enumerate(source_text)
    if len(enumeration.candidates) != 1:
        raise ValueError("retokenization fixture source must produce exactly one lexical candidate")
    return registry.apply(enumeration, (enumeration.candidates[0].candidate_id,)).output_text


def _tokenize(tokenizer: Callable[[str], Sequence[int]], text: str) -> tuple[int, ...]:
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable")
    return normalize_token_sequence("tokenizer output", tokenizer(text))


def capture_lexical_retokenization_fixture(
    fixture_id: str,
    rule: LexicalTemplateRule,
    model_tokenizer_identity: ModelTokenizerIdentity,
    source_text: str,
    tokenizer: Callable[[str], Sequence[int]],
) -> LexicalRetokenizationFixture:
    require_clean_string("fixture_id", fixture_id)
    if not isinstance(model_tokenizer_identity, ModelTokenizerIdentity):
        raise TypeError("model_tokenizer_identity must be a ModelTokenizerIdentity")
    transformed_text = _transform_once(rule, source_text)
    source_tokens = _tokenize(tokenizer, source_text)
    transformed_tokens = _tokenize(tokenizer, transformed_text)
    payload = {
        "algorithm_version": LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION,
        "fixture_id": fixture_id,
        "rule_hash": rule.rule_hash,
        "model_tokenizer_identity_hash": model_tokenizer_identity.identity_hash,
        "source_text": source_text,
        "transformed_text": transformed_text,
        "source_text_hash": sha256_text(source_text),
        "transformed_text_hash": sha256_text(transformed_text),
        "source_token_ids": source_tokens,
        "transformed_token_ids": transformed_tokens,
        "source_token_hash": sha256_json(source_tokens),
        "transformed_token_hash": sha256_json(transformed_tokens),
    }
    return LexicalRetokenizationFixture(
        algorithm_version=LEXICAL_RETOKENIZATION_FIXTURE_ALGORITHM_VERSION,
        fixture_id=fixture_id,
        rule_hash=rule.rule_hash,
        model_tokenizer_identity_hash=model_tokenizer_identity.identity_hash,
        source_text=source_text,
        transformed_text=transformed_text,
        source_text_hash=payload["source_text_hash"],
        transformed_text_hash=payload["transformed_text_hash"],
        source_token_ids=source_tokens,
        transformed_token_ids=transformed_tokens,
        source_token_hash=payload["source_token_hash"],
        transformed_token_hash=payload["transformed_token_hash"],
        fixture_hash=sha256_json(payload),
    )


def verify_lexical_retokenization_fixture(
    fixture: LexicalRetokenizationFixture,
    rule: LexicalTemplateRule,
    model_tokenizer_identity: ModelTokenizerIdentity,
    tokenizer: Callable[[str], Sequence[int]],
) -> None:
    if not isinstance(fixture, LexicalRetokenizationFixture):
        raise TypeError("fixture must be a LexicalRetokenizationFixture")
    if not isinstance(rule, LexicalTemplateRule):
        raise TypeError("rule must be a LexicalTemplateRule")
    if not isinstance(model_tokenizer_identity, ModelTokenizerIdentity):
        raise TypeError("model_tokenizer_identity must be a ModelTokenizerIdentity")
    if fixture.rule_hash != rule.rule_hash:
        raise LexicalRetokenizationVerificationError("retokenization fixture rule hash does not match supplied rule")
    if fixture.model_tokenizer_identity_hash != model_tokenizer_identity.identity_hash:
        raise LexicalRetokenizationVerificationError("retokenization fixture tokenizer identity does not match supplied identity")
    if fixture.transformed_text != _transform_once(rule, fixture.source_text):
        raise LexicalRetokenizationVerificationError("retokenization fixture transformed text does not replay from supplied rule")
    if fixture.source_token_ids != _tokenize(tokenizer, fixture.source_text):
        raise LexicalRetokenizationVerificationError("retokenization fixture source tokens do not replay from supplied tokenizer")
    if fixture.transformed_token_ids != _tokenize(tokenizer, fixture.transformed_text):
        raise LexicalRetokenizationVerificationError("retokenization fixture transformed tokens do not replay from supplied tokenizer")
