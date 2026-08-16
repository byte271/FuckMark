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




def test_sample_rejects_test_key_outside_final_split() -> None:
    p = prompt(split=CorpusSplit.ATTACK_DEVELOPMENT)
    with pytest.raises(ValueError, match="TEST_KEYS"):
        sample("sample-1", "match-1", WatermarkLabel.WATERMARKED, p, "Response", 1, key_split=KeySplit.TEST)


def test_final_split_requires_test_key() -> None:
    p = prompt(split=CorpusSplit.FINAL_TEST)
    with pytest.raises(ValueError, match="final-test"):
        sample("sample-1", "match-1", WatermarkLabel.WATERMARKED, p, "Response", 1, key_split=KeySplit.DEV)


def test_sample_rejects_nonstandard_target_length() -> None:
    p = prompt()
    with pytest.raises(ValueError, match="target_length"):
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
            100,
            generation_tokens(),
        )


def test_sample_hash_rejects_label_tampering() -> None:
    p = prompt()
    record = sample("sample-1", "match-1", WatermarkLabel.WATERMARKED, p, "Response A", 1)
    with pytest.raises(ValueError, match="record_hash"):
        replace(record, label=WatermarkLabel.UNWATERMARKED)


def test_sample_rejects_target_larger_than_generation_limit() -> None:
    p = prompt()
    with pytest.raises(ValueError, match="max_new_tokens"):
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
            128,
            generation_tokens(),
        )


def test_sample_rejects_attention_mask_incompatible_with_padding_side() -> None:
    p = prompt()
    bad_tokens = generation_tokens()
    bad_tokens = bad_tokens.__class__.create(
        input_token_ids=(5, 0, 6),
        attention_mask=(1, 0, 1),
        generated_sequence_ids=(5, 0, 6, 7),
        continuation_start_index=3,
        continuation_token_ids=(7,),
        prompt_length_after_templating=2,
        model_tokenizer_identity_hash=model_identity(PaddingSide.LEFT).identity_hash,
    )
    with pytest.raises(ValueError, match="left-padding"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            "Response",
            model_identity(PaddingSide.LEFT),
            generation(),
            watermark(),
            64,
            bad_tokens,
        )


def test_sample_rejects_masked_nonpad_input_token() -> None:
    p = prompt()
    bad_tokens = generation_tokens().__class__.create(
        input_token_ids=(99, 0, 5, 6),
        attention_mask=(0, 0, 1, 1),
        generated_sequence_ids=(99, 0, 5, 6, 7),
        continuation_start_index=4,
        continuation_token_ids=(7,),
        prompt_length_after_templating=2,
        model_tokenizer_identity_hash=model_identity(PaddingSide.LEFT).identity_hash,
    )
    with pytest.raises(ValueError, match="pad_token_id"):
        CorpusSample.create(
            "sample-1",
            "match-1",
            p.prompt_id,
            p.prompt_family_id,
            p.domain,
            p.split,
            WatermarkLabel.WATERMARKED,
            "Response",
            model_identity(PaddingSide.LEFT),
            generation(),
            watermark(),
            64,
            bad_tokens,
        )


def test_right_padding_boundary_is_accepted_when_mask_and_pad_tokens_match() -> None:
    p = prompt()
    identity = model_identity(PaddingSide.RIGHT)
    tokens = generation_tokens().__class__.create(
        input_token_ids=(5, 6, 0, 0),
        attention_mask=(1, 1, 0, 0),
        generated_sequence_ids=(5, 6, 0, 0, 7),
        continuation_start_index=4,
        continuation_token_ids=(7,),
        prompt_length_after_templating=2,
        model_tokenizer_identity_hash=identity.identity_hash,
    )
    record = CorpusSample.create(
        "sample-1",
        "match-1",
        p.prompt_id,
        p.prompt_family_id,
        p.domain,
        p.split,
        WatermarkLabel.WATERMARKED,
        "Response",
        identity,
        generation(),
        watermark(),
        64,
        tokens,
    )
    assert record.generation_tokens.attention_mask == (1, 1, 0, 0)
