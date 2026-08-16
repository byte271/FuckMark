from __future__ import annotations

import hashlib
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .._validation import normalize_token_sequence, require_int
from ..hashing import sha256_json
from ..types import SourcePin
from ._lcg import INT64_MAX, INT64_MIN, accumulate_hash
from .base import AdapterSignals


ADAPTER_ID = "deepmind-synthid-text-reference"
ALGORITHM_VERSION = "deepmind-reference-observation-v1"
SOURCE_PIN = SourcePin(
    source_id="deepmind-synthid-text-reference",
    repository="google-deepmind/synthid-text",
    commit="addb4a158143c7c6851a1308f78b89fceed59683",
    license_id="Apache-2.0",
    critical_files=(
        "src/synthid_text/logits_processing.py",
        "src/synthid_text/hashing_function.py",
        "src/synthid_text/detector_mean.py",
        "src/synthid_text/detector_bayesian.py",
        "src/synthid_text/synthid_mixin.py",
    ),
)
_G_VALUE_HASH_ROUNDS = 12
_G_VALUE_FINAL_SHIFT = 30
_CONFIG_FIELDS = frozenset({"ngram_len", "keys", "context_history_size"})


def _key_bytes(keys: tuple[int, ...]) -> bytes:
    return b"".join(key.to_bytes(8, byteorder=sys.byteorder, signed=True) for key in keys)


def _hash_iv(keys: tuple[int, ...]) -> int:
    digest = hashlib.sha256(_key_bytes(keys)).digest()
    return int.from_bytes(digest, byteorder="big") % INT64_MAX


def _g_value(ngram_key: int) -> int:
    output = ngram_key
    shift = 64 // _G_VALUE_HASH_ROUNDS
    for _ in range(_G_VALUE_HASH_ROUNDS):
        output = accumulate_hash(output, (1,)) >> shift
    return (output >> _G_VALUE_FINAL_SHIFT) % 2


def _observation_count(token_count: int, ngram_len: int) -> int:
    return max(0, token_count - ngram_len + 1)


def _normalize_source_tokens(token_ids: Sequence[int]) -> tuple[int, ...]:
    normalized = normalize_token_sequence("token_ids", token_ids)
    if any(token > INT64_MAX for token in normalized):
        raise ValueError("token_ids must fit signed int64 for DeepMind source conformance")
    return normalized


def _validate_source_eos(eos_token_id: int) -> None:
    require_int("eos_token_id", eos_token_id)
    if eos_token_id < 0:
        raise ValueError("eos_token_id must be non-negative")
    if eos_token_id > INT64_MAX:
        raise ValueError("eos_token_id must fit signed int64 for DeepMind source conformance")


@dataclass(frozen=True, slots=True)
class DeepMindReferenceConfig:
    ngram_len: int
    keys: tuple[int, ...]
    context_history_size: int

    def __post_init__(self) -> None:
        require_int("ngram_len", self.ngram_len)
        require_int("context_history_size", self.context_history_size)
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.context_history_size <= 0:
            raise ValueError("context_history_size must be positive")
        if not isinstance(self.keys, (tuple, list)):
            raise TypeError("keys must be a tuple or list of integers")
        normalized_keys = tuple(self.keys)
        if not normalized_keys:
            raise ValueError("keys must not be empty")
        for key in normalized_keys:
            require_int("watermark key", key)
            if key < INT64_MIN or key > INT64_MAX:
                raise ValueError("watermark keys must fit signed int64")
        if len(set(normalized_keys)) != len(normalized_keys):
            raise ValueError("keys must be unique")
        object.__setattr__(self, "keys", normalized_keys)

    @classmethod
    def from_mapping(cls, config: Mapping[str, object]) -> DeepMindReferenceConfig:
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        if any(not isinstance(key, str) for key in config):
            raise TypeError("config keys must be strings")
        fields = frozenset(config)
        if fields != _CONFIG_FIELDS:
            missing = sorted(_CONFIG_FIELDS - fields)
            extra = sorted(fields - _CONFIG_FIELDS)
            raise ValueError(f"DeepMind reference config fields do not match schema: missing={missing}, extra={extra}")
        keys = config["keys"]
        if not isinstance(keys, (tuple, list)):
            raise TypeError("keys must be a tuple or list of integers")
        return cls(
            ngram_len=config["ngram_len"],
            keys=tuple(keys),
            context_history_size=config["context_history_size"],
        )


class DeepMindReferenceAdapter:
    __slots__ = ("_config", "_fingerprint", "_hash_iv")

    def __init__(self, config: DeepMindReferenceConfig) -> None:
        if not isinstance(config, DeepMindReferenceConfig):
            raise TypeError("config must be a DeepMindReferenceConfig")
        self._config = config
        self._hash_iv = _hash_iv(config.keys)
        self._fingerprint = sha256_json(
            {
                "adapter_id": ADAPTER_ID,
                "algorithm_version": ALGORITHM_VERSION,
                "source_commit": SOURCE_PIN.commit,
                "source_byteorder": sys.byteorder,
                "config": {
                    "ngram_len": config.ngram_len,
                    "keys": config.keys,
                    "context_history_size": config.context_history_size,
                },
            }
        )

    @property
    def adapter_id(self) -> str:
        return ADAPTER_ID

    @property
    def algorithm_version(self) -> str:
        return ALGORITHM_VERSION

    @property
    def source_pin(self) -> SourcePin:
        return SOURCE_PIN

    @property
    def config(self) -> DeepMindReferenceConfig:
        return self._config

    @property
    def ngram_len(self) -> int:
        return self._config.ngram_len

    @property
    def depth(self) -> int:
        return len(self._config.keys)

    @property
    def hash_iv(self) -> int:
        return self._hash_iv

    def configuration_fingerprint(self) -> str:
        return self._fingerprint

    def _ngram_keys(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        count = _observation_count(len(token_ids), self.ngram_len)
        rows: list[tuple[int, ...]] = []
        for start in range(count):
            ngram = token_ids[start : start + self.ngram_len]
            ngram_hash = accumulate_hash(self._hash_iv, ngram)
            rows.append(tuple(accumulate_hash(ngram_hash, (key,)) for key in self._config.keys))
        return tuple(rows)

    def compute_ngram_keys(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        normalized = _normalize_source_tokens(token_ids)
        return self._ngram_keys(normalized)

    def _g_values(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        return tuple(tuple(_g_value(value) for value in row) for row in self._ngram_keys(token_ids))

    def compute_g_values(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        normalized = _normalize_source_tokens(token_ids)
        return self._g_values(normalized)

    def _context_repetition_mask(self, token_ids: Sequence[int]) -> tuple[bool, ...]:
        count = _observation_count(len(token_ids), self.ngram_len)
        history = [0] * self._config.context_history_size
        output: list[bool] = []
        context_len = self.ngram_len - 1
        for start in range(count):
            context = token_ids[start : start + context_len]
            context_hash = accumulate_hash(self._hash_iv, context)
            output.append(context_hash not in history)
            history = [context_hash, *history[:-1]]
        return tuple(output)

    def compute_context_repetition_mask(self, token_ids: Sequence[int]) -> tuple[bool, ...]:
        normalized = _normalize_source_tokens(token_ids)
        return self._context_repetition_mask(normalized)

    def _eos_mask(self, token_ids: Sequence[int], eos_token_id: int) -> tuple[bool, ...]:
        count = _observation_count(len(token_ids), self.ngram_len)
        try:
            first_eos = token_ids.index(eos_token_id)
        except (AttributeError, ValueError):
            first_eos = len(token_ids)
        current_offset = self.ngram_len - 1
        return tuple(start + current_offset < first_eos for start in range(count))

    def compute_eos_mask(self, token_ids: Sequence[int], eos_token_id: int) -> tuple[bool, ...]:
        normalized = _normalize_source_tokens(token_ids)
        _validate_source_eos(eos_token_id)
        return self._eos_mask(normalized, eos_token_id)

    def signals(self, token_ids: Sequence[int], eos_token_id: int) -> AdapterSignals:
        normalized = _normalize_source_tokens(token_ids)
        _validate_source_eos(eos_token_id)
        return AdapterSignals(
            depth=self.depth,
            g_values=self._g_values(normalized),
            context_mask=self._context_repetition_mask(normalized),
            eos_mask=self._eos_mask(normalized, eos_token_id),
        )


def create_deepmind_reference_adapter(config: Mapping[str, object]) -> DeepMindReferenceAdapter:
    return DeepMindReferenceAdapter(DeepMindReferenceConfig.from_mapping(config))
