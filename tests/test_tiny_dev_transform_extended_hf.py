import pytest

from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.tiny_dev_transform_extended_hf import (
    EXTENDED_TINY_DEV_BUDGETS,
    runtime_tokenizer_identity,
)


_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"


class FakeTokenizer:
    def __init__(self) -> None:
        self.eos_token_id = 50256
        self.pad_token_id = 50256
        self.bos_token_id = 50256
        self.eos_token = "<|endoftext|>"
        self.pad_token = "<|endoftext|>"
        self.chat_template = None
        self.padding_side = "left"
        self.add_bos_token = False
        self.add_eos_token = False
        self.special_tokens_map = {
            "bos_token": "<|endoftext|>",
            "eos_token": "<|endoftext|>",
            "unk_token": "<|endoftext|>",
            "pad_token": "<|endoftext|>",
        }


def test_extended_budget_profile_adds_moderate_six_edit_cell() -> None:
    assert EXTENDED_TINY_DEV_BUDGETS == (1, 2, 4, 6)
    assert EXTENDED_TINY_DEV_BUDGETS == tuple(sorted(set(EXTENDED_TINY_DEV_BUDGETS)))


def test_runtime_tokenizer_identity_is_full_frozen_identity() -> None:
    tokenizer = FakeTokenizer()
    identity = runtime_tokenizer_identity(tokenizer, "openai-community/gpt2", _REVISION)
    assert identity.model_revision == _REVISION
    assert identity.tokenizer_revision == _REVISION
    assert identity.chat_template_hash == sha256_text("")
    assert identity.special_token_map_hash == sha256_json(tokenizer.special_tokens_map)
    assert identity.padding_side.value == "left"
    assert identity.eos_token_id == 50256
    assert identity.pad_token_id == 50256


def test_runtime_tokenizer_identity_rejects_wrong_padding_side() -> None:
    tokenizer = FakeTokenizer()
    tokenizer.padding_side = "right"
    with pytest.raises(RuntimeError, match="left padding"):
        runtime_tokenizer_identity(tokenizer, "openai-community/gpt2", _REVISION)


def test_runtime_tokenizer_identity_requires_eos() -> None:
    tokenizer = FakeTokenizer()
    tokenizer.eos_token_id = None
    with pytest.raises(RuntimeError, match="eos_token_id"):
        runtime_tokenizer_identity(tokenizer, "openai-community/gpt2", _REVISION)
