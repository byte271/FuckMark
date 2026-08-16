from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import normalize_token_sequence, require_int, require_sha256
from ..hashing import sha256_json


class TokenTrack(str, Enum):
    GENERATION = "generation"
    TEXT_ONLY = "text_only"


@dataclass(frozen=True, slots=True)
class GenerationTokenRecord:
    model_tokenizer_identity_hash: str
    input_token_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    generated_sequence_ids: tuple[int, ...]
    continuation_start_index: int
    continuation_token_ids: tuple[int, ...]
    prompt_length_after_templating: int
    input_token_hash: str
    generated_sequence_hash: str
    continuation_token_hash: str
    record_hash: str

    def __post_init__(self) -> None:
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        input_ids = normalize_token_sequence("input_token_ids", self.input_token_ids)
        generated_ids = normalize_token_sequence("generated_sequence_ids", self.generated_sequence_ids)
        continuation_ids = normalize_token_sequence("continuation_token_ids", self.continuation_token_ids)
        if not isinstance(self.attention_mask, tuple):
            raise TypeError("attention_mask must be a tuple")
        mask = tuple(self.attention_mask)
        if len(mask) != len(input_ids):
            raise ValueError("attention_mask length must match input_token_ids")
        for value in mask:
            require_int("attention mask value", value)
            if value not in (0, 1):
                raise ValueError("attention_mask values must be binary integers")
        require_int("continuation_start_index", self.continuation_start_index)
        if self.continuation_start_index != len(input_ids):
            raise ValueError("continuation_start_index must equal the generated input sequence length")
        if len(generated_ids) < self.continuation_start_index:
            raise ValueError("generated_sequence_ids are shorter than the continuation boundary")
        if generated_ids[: self.continuation_start_index] != input_ids:
            raise ValueError("generated_sequence_ids must preserve the exact generation input prefix")
        if generated_ids[self.continuation_start_index :] != continuation_ids:
            raise ValueError("continuation_token_ids do not match the exact generated continuation slice")
        require_int("prompt_length_after_templating", self.prompt_length_after_templating)
        if self.prompt_length_after_templating <= 0:
            raise ValueError("prompt_length_after_templating must be positive")
        if self.prompt_length_after_templating != sum(mask):
            raise ValueError("prompt_length_after_templating must equal the attention-mask population")
        require_sha256("input_token_hash", self.input_token_hash)
        require_sha256("generated_sequence_hash", self.generated_sequence_hash)
        require_sha256("continuation_token_hash", self.continuation_token_hash)
        require_sha256("record_hash", self.record_hash)
        if self.input_token_hash != sha256_json(input_ids):
            raise ValueError("input_token_hash does not match input_token_ids")
        if self.generated_sequence_hash != sha256_json(generated_ids):
            raise ValueError("generated_sequence_hash does not match generated_sequence_ids")
        if self.continuation_token_hash != sha256_json(continuation_ids):
            raise ValueError("continuation_token_hash does not match continuation_token_ids")
        object.__setattr__(self, "input_token_ids", input_ids)
        object.__setattr__(self, "attention_mask", mask)
        object.__setattr__(self, "generated_sequence_ids", generated_ids)
        object.__setattr__(self, "continuation_token_ids", continuation_ids)
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match generation token record")

    def _payload(self) -> dict[str, object]:
        return {
            "track": TokenTrack.GENERATION.value,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "input_token_ids": self.input_token_ids,
            "attention_mask": self.attention_mask,
            "generated_sequence_ids": self.generated_sequence_ids,
            "continuation_start_index": self.continuation_start_index,
            "continuation_token_ids": self.continuation_token_ids,
            "prompt_length_after_templating": self.prompt_length_after_templating,
            "input_token_hash": self.input_token_hash,
            "generated_sequence_hash": self.generated_sequence_hash,
            "continuation_token_hash": self.continuation_token_hash,
        }

    @classmethod
    def create(
        cls,
        input_token_ids: tuple[int, ...] | list[int],
        attention_mask: tuple[int, ...] | list[int],
        generated_sequence_ids: tuple[int, ...] | list[int],
        continuation_start_index: int,
        continuation_token_ids: tuple[int, ...] | list[int],
        prompt_length_after_templating: int,
        model_tokenizer_identity_hash: str,
    ) -> GenerationTokenRecord:
        input_ids = normalize_token_sequence("input_token_ids", input_token_ids)
        generated_ids = normalize_token_sequence("generated_sequence_ids", generated_sequence_ids)
        continuation_ids = normalize_token_sequence("continuation_token_ids", continuation_token_ids)
        mask = tuple(attention_mask)
        payload = {
            "track": TokenTrack.GENERATION.value,
            "model_tokenizer_identity_hash": model_tokenizer_identity_hash,
            "input_token_ids": input_ids,
            "attention_mask": mask,
            "generated_sequence_ids": generated_ids,
            "continuation_start_index": continuation_start_index,
            "continuation_token_ids": continuation_ids,
            "prompt_length_after_templating": prompt_length_after_templating,
            "input_token_hash": sha256_json(input_ids),
            "generated_sequence_hash": sha256_json(generated_ids),
            "continuation_token_hash": sha256_json(continuation_ids),
        }
        return cls(
            model_tokenizer_identity_hash=model_tokenizer_identity_hash,
            input_token_ids=input_ids,
            attention_mask=mask,
            generated_sequence_ids=generated_ids,
            continuation_start_index=continuation_start_index,
            continuation_token_ids=continuation_ids,
            prompt_length_after_templating=prompt_length_after_templating,
            input_token_hash=payload["input_token_hash"],
            generated_sequence_hash=payload["generated_sequence_hash"],
            continuation_token_hash=payload["continuation_token_hash"],
            record_hash=sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class TextOnlyTokenRecord:
    model_tokenizer_identity_hash: str
    source_text_sha256: str
    token_ids: tuple[int, ...]
    token_hash: str
    record_hash: str

    def __post_init__(self) -> None:
        require_sha256("model_tokenizer_identity_hash", self.model_tokenizer_identity_hash)
        require_sha256("source_text_sha256", self.source_text_sha256)
        token_ids = normalize_token_sequence("token_ids", self.token_ids)
        require_sha256("token_hash", self.token_hash)
        require_sha256("record_hash", self.record_hash)
        if self.token_hash != sha256_json(token_ids):
            raise ValueError("token_hash does not match token_ids")
        object.__setattr__(self, "token_ids", token_ids)
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match text-only token record")

    def _payload(self) -> dict[str, object]:
        return {
            "track": TokenTrack.TEXT_ONLY.value,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "source_text_sha256": self.source_text_sha256,
            "token_ids": self.token_ids,
            "token_hash": self.token_hash,
        }

    @classmethod
    def create(
        cls,
        source_text_sha256: str,
        token_ids: tuple[int, ...] | list[int],
        model_tokenizer_identity_hash: str,
    ) -> TextOnlyTokenRecord:
        normalized = normalize_token_sequence("token_ids", token_ids)
        token_hash = sha256_json(normalized)
        payload = {
            "track": TokenTrack.TEXT_ONLY.value,
            "model_tokenizer_identity_hash": model_tokenizer_identity_hash,
            "source_text_sha256": source_text_sha256,
            "token_ids": normalized,
            "token_hash": token_hash,
        }
        return cls(
            model_tokenizer_identity_hash=model_tokenizer_identity_hash,
            source_text_sha256=source_text_sha256,
            token_ids=normalized,
            token_hash=token_hash,
            record_hash=sha256_json(payload),
        )
