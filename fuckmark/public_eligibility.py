from __future__ import annotations

from dataclasses import dataclass

from ._validation import normalize_token_sequence, require_int, require_sha256
from .adapters._lcg import BoundedHashHistory, INT64_MAX, accumulate_hash
from .adapters.huggingface_synthid import SOURCE_PIN
from .hashing import sha256_json


PUBLIC_ELIGIBILITY_ALGORITHM_VERSION = "huggingface-synthid-public-eligibility-v1"


@dataclass(frozen=True, slots=True)
class PublicEligibilityMask:
    algorithm_version: str
    source_commit: str
    token_hash: str
    token_count: int
    ngram_len: int
    context_history_size: int
    eos_token_id: int
    context_mask: tuple[bool, ...]
    eos_mask: tuple[bool, ...]
    valid_mask: tuple[bool, ...]
    mask_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != PUBLIC_ELIGIBILITY_ALGORITHM_VERSION:
            raise ValueError("unsupported public eligibility algorithm version")
        if self.source_commit != SOURCE_PIN.commit:
            raise ValueError("public eligibility source commit does not match the pinned Hugging Face adapter")
        require_sha256("token_hash", self.token_hash)
        for name in ("token_count", "ngram_len", "context_history_size", "eos_token_id"):
            require_int(name, getattr(self, name))
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.context_history_size <= 0:
            raise ValueError("context_history_size must be positive")
        if self.eos_token_id < 0 or self.eos_token_id > INT64_MAX:
            raise ValueError("eos_token_id must fit non-negative signed int64")
        expected = max(0, self.token_count - self.ngram_len + 1)
        for name, values in (
            ("context_mask", self.context_mask),
            ("eos_mask", self.eos_mask),
            ("valid_mask", self.valid_mask),
        ):
            if not isinstance(values, tuple) or len(values) != expected:
                raise ValueError(f"{name} length does not match observation geometry")
            if any(not isinstance(value, bool) for value in values):
                raise TypeError(f"{name} must contain bool values")
        if self.valid_mask != tuple(left and right for left, right in zip(self.context_mask, self.eos_mask)):
            raise ValueError("valid_mask must equal context_mask AND eos_mask")
        require_sha256("mask_hash", self.mask_hash)
        if self.mask_hash != sha256_json(self.payload()):
            raise ValueError("mask_hash does not match public eligibility mask")

    @property
    def observation_count(self) -> int:
        return len(self.valid_mask)

    @property
    def valid_count(self) -> int:
        return sum(self.valid_mask)

    @property
    def repeated_count(self) -> int:
        return sum(not value for value in self.context_mask)

    @property
    def post_eos_count(self) -> int:
        return sum(not value for value in self.eos_mask)

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_commit": self.source_commit,
            "token_hash": self.token_hash,
            "token_count": self.token_count,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "eos_token_id": self.eos_token_id,
            "context_mask": self.context_mask,
            "eos_mask": self.eos_mask,
            "valid_mask": self.valid_mask,
        }


def build_huggingface_public_eligibility(
    token_ids,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int = 1024,
) -> PublicEligibilityMask:
    normalized = normalize_token_sequence("token_ids", token_ids)
    if any(token > INT64_MAX for token in normalized):
        raise ValueError("token_ids must fit signed int64 for Hugging Face source conformance")
    require_int("eos_token_id", eos_token_id)
    require_int("ngram_len", ngram_len)
    require_int("context_history_size", context_history_size)
    if eos_token_id < 0 or eos_token_id > INT64_MAX:
        raise ValueError("eos_token_id must fit non-negative signed int64")
    if ngram_len < 2:
        raise ValueError("ngram_len must be at least 2")
    if context_history_size <= 0:
        raise ValueError("context_history_size must be positive")
    observation_count = max(0, len(normalized) - ngram_len + 1)
    history = BoundedHashHistory(context_history_size)
    context_len = ngram_len - 1
    context_mask = []
    for start in range(observation_count):
        context_hash = accumulate_hash(1, normalized[start : start + context_len])
        context_mask.append(not history.contains(context_hash))
        history.push(context_hash)
    try:
        first_eos = normalized.index(eos_token_id)
    except ValueError:
        first_eos = len(normalized)
    current_offset = ngram_len - 1
    eos_mask = tuple(start + current_offset < first_eos for start in range(observation_count))
    context_tuple = tuple(context_mask)
    valid_mask = tuple(left and right for left, right in zip(context_tuple, eos_mask))
    payload = {
        "algorithm_version": PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        "source_commit": SOURCE_PIN.commit,
        "token_hash": sha256_json(normalized),
        "token_count": len(normalized),
        "ngram_len": ngram_len,
        "context_history_size": context_history_size,
        "eos_token_id": eos_token_id,
        "context_mask": context_tuple,
        "eos_mask": eos_mask,
        "valid_mask": valid_mask,
    }
    return PublicEligibilityMask(
        PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        SOURCE_PIN.commit,
        payload["token_hash"],
        len(normalized),
        ngram_len,
        context_history_size,
        eos_token_id,
        context_tuple,
        eos_mask,
        valid_mask,
        sha256_json(payload),
    )
