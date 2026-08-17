from dataclasses import replace
import inspect

import pytest

from fuckmark.adapters.huggingface_synthid import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from fuckmark.hashing import sha256_text
from fuckmark.public_eligibility import build_huggingface_public_eligibility


def test_public_eligibility_matches_huggingface_context_and_eos_masks() -> None:
    tokens = (1, 2, 9, 1, 2, 8, 99, 1, 2)
    config = HuggingFaceSynthIDConfig(
        ngram_len=3,
        keys=(7,),
        context_history_size=4,
        sampling_table_size=8,
    )
    adapter = HuggingFaceSynthIDAdapter(config, bytes((0, 1, 0, 1, 0, 1, 0, 1)), "test")
    public = build_huggingface_public_eligibility(
        tokens,
        99,
        3,
        context_history_size=4,
    )
    assert public.context_mask == adapter.compute_context_repetition_mask(tokens)
    assert public.eos_mask == adapter.compute_eos_mask(tokens, 99)
    assert public.valid_mask == tuple(
        left and right
        for left, right in zip(public.context_mask, public.eos_mask)
    )
    assert public.repeated_count == 1
    assert public.post_eos_count == 3
    assert public.valid_count == 3


def test_public_eligibility_interface_has_no_watermark_secret_inputs() -> None:
    parameters = inspect.signature(build_huggingface_public_eligibility).parameters
    assert tuple(parameters) == (
        "token_ids",
        "eos_token_id",
        "ngram_len",
        "context_history_size",
    )
    assert "keys" not in parameters
    assert "g_values" not in parameters


def test_public_eligibility_is_content_addressed() -> None:
    public = build_huggingface_public_eligibility((1, 2, 3, 4, 5), 99, 3)
    with pytest.raises(ValueError, match="mask_hash"):
        replace(public, token_hash=sha256_text("tampered"))


def test_public_eligibility_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="ngram_len"):
        build_huggingface_public_eligibility((1, 2, 3), 99, 1)
    with pytest.raises(ValueError, match="context_history_size"):
        build_huggingface_public_eligibility((1, 2, 3), 99, 2, context_history_size=0)
    with pytest.raises(ValueError, match="signed int64"):
        build_huggingface_public_eligibility((1, 2, 1 << 63), 99, 2)
