from dataclasses import replace

import pytest

from corpus_helpers import generation_tokens, model_identity
from fuckmark.corpus import GenerationTokenRecord, TextOnlyTokenRecord
from fuckmark.hashing import sha256_text


def test_generation_boundary_handles_left_padding_without_prompt_leakage() -> None:
    record = generation_tokens((11, 12, 13))
    assert record.input_token_ids == (0, 0, 5, 6)
    assert record.prompt_length_after_templating == 2
    assert record.continuation_start_index == 4
    assert record.continuation_token_ids == (11, 12, 13)


def test_generation_boundary_rejects_wrong_continuation_start() -> None:
    with pytest.raises(ValueError, match="continuation_start_index"):
        GenerationTokenRecord.create((5, 6), (1, 1), (5, 6, 7), 1, (6, 7), 2, model_identity().identity_hash)


def test_generation_boundary_rejects_changed_input_prefix() -> None:
    with pytest.raises(ValueError, match="exact generation input prefix"):
        GenerationTokenRecord.create((5, 6), (1, 1), (5, 9, 7), 2, (7,), 2, model_identity().identity_hash)


def test_generation_boundary_rejects_wrong_continuation_slice() -> None:
    with pytest.raises(ValueError, match="exact generated continuation slice"):
        GenerationTokenRecord.create((5, 6), (1, 1), (5, 6, 7), 2, (8,), 2, model_identity().identity_hash)


def test_generation_boundary_rejects_nonbinary_attention_mask() -> None:
    with pytest.raises(ValueError, match="binary"):
        GenerationTokenRecord.create((5, 6), (1, 2), (5, 6, 7), 2, (7,), 2, model_identity().identity_hash)


def test_generation_boundary_rejects_wrong_prompt_length() -> None:
    with pytest.raises(ValueError, match="attention-mask population"):
        GenerationTokenRecord.create((0, 5, 6), (0, 1, 1), (0, 5, 6, 7), 3, (7,), 3, model_identity().identity_hash)


def test_generation_record_hash_is_self_validating() -> None:
    record = generation_tokens()
    with pytest.raises(ValueError, match="record_hash"):
        replace(record, record_hash="0" * 64)


def test_text_only_track_binds_exact_source_text_hash() -> None:
    text_hash = sha256_text("Text with trailing space ")
    record = TextOnlyTokenRecord.create(text_hash, (1, 2, 3), model_identity().identity_hash)
    assert record.source_text_sha256 == text_hash
    assert record.token_ids == (1, 2, 3)


def test_text_only_record_rejects_forged_token_hash() -> None:
    record = TextOnlyTokenRecord.create(sha256_text("Text"), (1, 2, 3), model_identity().identity_hash)
    with pytest.raises(ValueError, match="token_hash"):
        replace(record, token_hash="0" * 64)
