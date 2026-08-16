from dataclasses import replace

import pytest

from corpus_helpers import generation, generation_tokens, model_identity, prompt, sample, watermark
from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    GenerationParameters,
    KeySplit,
    PaddingSide,
    PromptBoundaryMode,
    PromptRecord,
    TextOnlyTokenRecord,
    TokenTrack,
    WatermarkLabel,
)
from fuckmark.hashing import sha256_text




def test_prompt_hash_preserves_leading_and_trailing_whitespace() -> None:
    first = prompt(text=" Text ")
    second = prompt(prompt_id="prompt-002", family_id="family-002", text="Text")
    assert first.text == " Text "
    assert first.text_sha256 != second.text_sha256


def test_prompt_hash_does_not_unicode_normalize() -> None:
    composed = prompt(text="caf\u00e9")
    decomposed = prompt(prompt_id="prompt-002", family_id="family-002", text="cafe\u0301")
    assert composed.text_sha256 != decomposed.text_sha256


def test_prompt_requires_english_v1_scope() -> None:
    with pytest.raises(ValueError, match="language"):
        PromptRecord.create(
            "p",
            "f",
            CorpusDomain.GENERAL_EXPLANATORY,
            CorpusSplit.ATTACK_DEVELOPMENT,
            "source",
            "c" * 64,
            "CC0",
            "fixture",
            "Bonjour",
            language="fr",
        )


def test_model_identity_requires_immutable_revisions() -> None:
    base = model_identity()
    with pytest.raises(ValueError, match="model_revision"):
        replace(base, model_revision="main")


def test_absent_chat_template_is_explicitly_hashed() -> None:
    base = model_identity()
    with pytest.raises(ValueError, match="absent chat templates"):
        replace(base, chat_template_hash="0" * 64)


def test_model_identity_hash_rejects_field_tampering() -> None:
    base = model_identity()
    with pytest.raises(ValueError, match="identity_hash"):
        replace(base, padding_side=PaddingSide.RIGHT)
