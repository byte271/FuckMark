from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, normalize_token_sequence, require_int
from ..hashing import sha256_bytes, sha256_json
from ..types import SourcePin
from ._lcg import INT64_MAX, INT64_MIN, accumulate_hash
from .base import AdapterSignals


ADAPTER_ID = "huggingface-transformers-synthid"
ALGORITHM_VERSION = "huggingface-synthid-observation-v1"
SOURCE_PIN = SourcePin(
    source_id="huggingface-transformers-synthid",
    repository="huggingface/transformers",
    commit="a61d5f9e4fc184cff66938ff6c521cc358b5e024",
    license_id="Apache-2.0",
    critical_files=(
        "src/transformers/generation/configuration_utils.py",
        "src/transformers/generation/logits_process.py",
        "src/transformers/generation/watermarking.py",
    ),
)
_TORCH_SEED_MIN = -(1 << 63)
_TORCH_SEED_MAX = (1 << 64) - 1
_CONFIG_FIELDS = frozenset(
    {
        "ngram_len",
        "keys",
        "context_history_size",
        "sampling_table_seed",
        "sampling_table_size",
        "skip_first_ngram_calls",
        "debug_mode",
    }
)


def _observation_count(token_count: int, ngram_len: int) -> int:
    return max(0, token_count - ngram_len + 1)


def _normalize_source_tokens(token_ids: Sequence[int]) -> tuple[int, ...]:
    normalized = normalize_token_sequence("token_ids", token_ids)
    if any(token > INT64_MAX for token in normalized):
        raise ValueError("token_ids must fit signed int64 for Hugging Face source conformance")
    return normalized


def _validate_source_eos(eos_token_id: int) -> None:
    require_int("eos_token_id", eos_token_id)
    if eos_token_id < 0:
        raise ValueError("eos_token_id must be non-negative")
    if eos_token_id > INT64_MAX:
        raise ValueError("eos_token_id must fit signed int64 for Hugging Face source conformance")


def _normalize_sampling_table(sampling_table: Sequence[int], expected_size: int) -> tuple[int, ...]:
    if not isinstance(sampling_table, Sequence) or isinstance(sampling_table, (str, bytes, bytearray)):
        raise TypeError("sampling_table must be a sequence of binary integers")
    output = tuple(sampling_table)
    if len(output) != expected_size:
        raise ValueError("sampling_table length must match sampling_table_size")
    for value in output:
        require_int("sampling table value", value)
        if value not in (0, 1):
            raise ValueError("sampling_table must contain only binary integers")
    return output


@dataclass(frozen=True, slots=True)
class HuggingFaceSynthIDConfig:
    ngram_len: int
    keys: tuple[int, ...]
    context_history_size: int = 1024
    sampling_table_seed: int = 0
    sampling_table_size: int = 2**16
    skip_first_ngram_calls: bool = False
    debug_mode: bool = False

    def __post_init__(self) -> None:
        require_int("ngram_len", self.ngram_len)
        require_int("context_history_size", self.context_history_size)
        require_int("sampling_table_seed", self.sampling_table_seed)
        require_int("sampling_table_size", self.sampling_table_size)
        require_bool("skip_first_ngram_calls", self.skip_first_ngram_calls)
        require_bool("debug_mode", self.debug_mode)
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.context_history_size <= 0:
            raise ValueError("context_history_size must be positive")
        if self.sampling_table_size <= 0 or self.sampling_table_size > 2**24:
            raise ValueError("sampling_table_size must be between 1 and 2**24")
        if self.sampling_table_seed < _TORCH_SEED_MIN or self.sampling_table_seed > _TORCH_SEED_MAX:
            raise ValueError("sampling_table_seed must fit the Torch generator seed range")
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
    def from_mapping(cls, config: Mapping[str, object]) -> HuggingFaceSynthIDConfig:
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        if any(not isinstance(key, str) for key in config):
            raise TypeError("config keys must be strings")
        fields = frozenset(config)
        required = frozenset({"ngram_len", "keys"})
        if not required <= fields or not fields <= _CONFIG_FIELDS:
            missing = sorted(required - fields)
            extra = sorted(fields - _CONFIG_FIELDS)
            raise ValueError(f"Hugging Face SynthID config fields do not match schema: missing={missing}, extra={extra}")
        keys = config["keys"]
        if not isinstance(keys, (tuple, list)):
            raise TypeError("keys must be a tuple or list of integers")
        return cls(
            ngram_len=config["ngram_len"],
            keys=tuple(keys),
            context_history_size=config.get("context_history_size", 1024),
            sampling_table_seed=config.get("sampling_table_seed", 0),
            sampling_table_size=config.get("sampling_table_size", 2**16),
            skip_first_ngram_calls=config.get("skip_first_ngram_calls", False),
            debug_mode=config.get("debug_mode", False),
        )


class HuggingFaceSynthIDAdapter:
    __slots__ = ("_config", "_fingerprint", "_sampling_table", "_sampling_table_hash", "_sampling_table_provenance")

    def __init__(
        self,
        config: HuggingFaceSynthIDConfig,
        sampling_table: Sequence[int],
        sampling_table_provenance: str,
    ) -> None:
        if not isinstance(config, HuggingFaceSynthIDConfig):
            raise TypeError("config must be a HuggingFaceSynthIDConfig")
        require_clean_string("sampling_table_provenance", sampling_table_provenance)
        table = _normalize_sampling_table(sampling_table, config.sampling_table_size)
        table_hash = sha256_bytes(bytes(table))
        self._config = config
        self._sampling_table = table
        self._sampling_table_hash = table_hash
        self._sampling_table_provenance = sampling_table_provenance
        self._fingerprint = sha256_json(
            {
                "adapter_id": ADAPTER_ID,
                "algorithm_version": ALGORITHM_VERSION,
                "source_commit": SOURCE_PIN.commit,
                "config": config,
                "sampling_table_hash": table_hash,
            }
        )

    @classmethod
    def from_torch(cls, config: HuggingFaceSynthIDConfig, device: str = "cpu") -> HuggingFaceSynthIDAdapter:
        require_clean_string("device", device)
        try:
            import torch
        except ImportError as error:
            raise RuntimeError("Torch is required to reproduce the Hugging Face SynthID sampling table") from error
        generator = torch.Generator(device=device).manual_seed(config.sampling_table_seed)
        table = torch.randint(
            low=0,
            high=2,
            size=(config.sampling_table_size,),
            generator=generator,
            device=device,
        )
        provenance = f"torch={torch.__version__};device={device}"
        return cls(config, tuple(int(value) for value in table.cpu().tolist()), provenance)

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
    def config(self) -> HuggingFaceSynthIDConfig:
        return self._config

    @property
    def ngram_len(self) -> int:
        return self._config.ngram_len

    @property
    def depth(self) -> int:
        return len(self._config.keys)

    @property
    def sampling_table_hash(self) -> str:
        return self._sampling_table_hash

    @property
    def sampling_table_provenance(self) -> str:
        return self._sampling_table_provenance

    def configuration_fingerprint(self) -> str:
        return self._fingerprint

    def _ngram_keys(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        count = _observation_count(len(token_ids), self.ngram_len)
        rows: list[tuple[int, ...]] = []
        for start in range(count):
            ngram_hash = accumulate_hash(1, token_ids[start : start + self.ngram_len])
            rows.append(tuple(accumulate_hash(ngram_hash, (key,)) for key in self._config.keys))
        return tuple(rows)

    def compute_ngram_keys(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        normalized = _normalize_source_tokens(token_ids)
        return self._ngram_keys(normalized)

    def _g_values(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        size = self._config.sampling_table_size
        return tuple(tuple(self._sampling_table[value % size] for value in row) for row in self._ngram_keys(token_ids))

    def compute_g_values(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        normalized = _normalize_source_tokens(token_ids)
        return self._g_values(normalized)

    def _context_repetition_mask(self, token_ids: Sequence[int]) -> tuple[bool, ...]:
        count = _observation_count(len(token_ids), self.ngram_len)
        history = [0] * self._config.context_history_size
        output: list[bool] = []
        context_len = self.ngram_len - 1
        for start in range(count):
            context_hash = accumulate_hash(1, token_ids[start : start + context_len])
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


def create_huggingface_synthid_adapter(config: Mapping[str, object]) -> HuggingFaceSynthIDAdapter:
    return HuggingFaceSynthIDAdapter.from_torch(HuggingFaceSynthIDConfig.from_mapping(config))
