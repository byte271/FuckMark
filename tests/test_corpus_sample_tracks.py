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




def test_sample_binds_text_only_track_to_exact_text() -> None:
    p = prompt()
    text = "Exact response."
    text_only = TextOnlyTokenRecord.create(sha256_text(text), (10, 11, 12), model_identity().identity_hash)
    record = CorpusSample.create(
        "sample-1",
        "match-1",
        p.prompt_id,
        p.prompt_family_id,
        p.domain,
        p.split,
        WatermarkLabel.WATERMARKED,
        text,
        model_identity(),
        generation(),
        watermark(),
        64,
        generation_tokens(),
        text_only_tokens=text_only,
    )
    assert record.token_hash_for(TokenTrack.TEXT_ONLY) == text_only.token_hash
    assert record.realized_length_for(TokenTrack.TEXT_ONLY) == 3
    assert record.realized_length_for(TokenTrack.GENERATION) == len(record.generation_tokens.continuation_token_ids)


def test_sample_rejects_text_only_track_from_different_text() -> None:
    p = prompt()
    text_only = TextOnlyTokenRecord.create(sha256_text("Other response"), (10, 11), model_identity().identity_hash)
    with pytest.raises(ValueError, match="exact sample text"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            "Exact response",
            model_identity(),
            generation(),
            watermark(),
            64,
            generation_tokens(),
            text_only_tokens=text_only,
        )


def test_sample_rejects_prompt_included_primary_boundary() -> None:
    p = prompt()
    with pytest.raises(ValueError, match="continuation-only"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            "Response",
            model_identity(),
            generation(),
            watermark(),
            64,
            generation_tokens(),
            prompt_boundary_mode=PromptBoundaryMode.PROMPT_INCLUDED_DIAGNOSTIC,
        )


def test_sample_requires_captured_generation_tokens_even_with_text_only_view() -> None:
    p = prompt()
    text = "Exact response."
    text_only = TextOnlyTokenRecord.create(sha256_text(text), (10, 11, 12), model_identity().identity_hash)
    with pytest.raises(TypeError, match="generation_tokens"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            text,
            model_identity(),
            generation(),
            watermark(),
            64,
            None,
            text_only_tokens=text_only,
        )


def test_missing_text_only_track_fails_explicitly() -> None:
    p = prompt()
    record = sample("sample-1", "match-1", WatermarkLabel.WATERMARKED, p, "Response", 1)
    with pytest.raises(KeyError, match="text-only"):
        record.token_ids_for(TokenTrack.TEXT_ONLY)


def test_sample_rejects_generation_tokens_from_different_model_tokenizer_identity() -> None:
    p = prompt()
    base = model_identity(PaddingSide.LEFT)
    other = base.__class__.create(
        model_id="other/model",
        model_revision="d" * 40,
        tokenizer_id=base.tokenizer_id,
        tokenizer_revision=base.tokenizer_revision,
        chat_template_present=base.chat_template_present,
        chat_template_hash=base.chat_template_hash,
        special_token_map_hash=base.special_token_map_hash,
        padding_side=base.padding_side,
        bos_token_id=base.bos_token_id,
        eos_token_id=base.eos_token_id,
        pad_token_id=base.pad_token_id,
        add_bos_token=base.add_bos_token,
        add_eos_token=base.add_eos_token,
    )
    tokens = generation_tokens(identity=base)
    with pytest.raises(ValueError, match="generation token record"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            "Response",
            other,
            generation(),
            watermark(),
            64,
            tokens,
        )


def test_sample_rejects_text_only_tokens_from_different_tokenizer_identity() -> None:
    p = prompt()
    identity = model_identity()
    text = "Response"
    text_only = TextOnlyTokenRecord.create(sha256_text(text), (10, 11), "d" * 64)
    with pytest.raises(ValueError, match="text-only token record"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            text,
            identity,
            generation(),
            watermark(),
            64,
            generation_tokens(identity=identity),
            text_only_tokens=text_only,
        )
