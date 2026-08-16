from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .schema import KeySplit, MAX_GENERATION_SEED, float_for_hash


@dataclass(frozen=True, slots=True)
class GenerationParameters:
    seed: int
    seed_policy_id: str
    temperature: float
    top_k: int
    top_p: float
    max_new_tokens: int
    do_sample: bool
    dtype: str
    device: str
    backend_id: str
    backend_version: str
    config_hash: str
    matching_signature_hash: str

    def __post_init__(self) -> None:
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed > MAX_GENERATION_SEED:
            raise ValueError("seed must be between 0 and 2^64-1")
        for name, value in (
            ("seed_policy_id", self.seed_policy_id),
            ("dtype", self.dtype),
            ("device", self.device),
            ("backend_id", self.backend_id),
            ("backend_version", self.backend_version),
        ):
            require_clean_string(name, value)
        require_bool("do_sample", self.do_sample)
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)):
            raise TypeError("temperature must be a real number")
        try:
            temperature = float(self.temperature)
        except OverflowError as error:
            raise ValueError("temperature must be representable as a finite float") from error
        if not math.isfinite(temperature) or temperature < 0.0:
            raise ValueError("temperature must be finite and non-negative")
        if self.do_sample and temperature <= 0.0:
            raise ValueError("sampled generation requires positive temperature")
        require_int("top_k", self.top_k)
        if self.top_k < 0:
            raise ValueError("top_k must be non-negative")
        if isinstance(self.top_p, bool) or not isinstance(self.top_p, (int, float)):
            raise TypeError("top_p must be a real number")
        try:
            top_p = float(self.top_p)
        except OverflowError as error:
            raise ValueError("top_p must be representable as a finite float") from error
        if not math.isfinite(top_p) or top_p <= 0.0 or top_p > 1.0:
            raise ValueError("top_p must be in (0, 1]")
        require_int("max_new_tokens", self.max_new_tokens)
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")
        object.__setattr__(self, "temperature", temperature)
        object.__setattr__(self, "top_p", top_p)
        require_sha256("config_hash", self.config_hash)
        require_sha256("matching_signature_hash", self.matching_signature_hash)
        if self.config_hash != sha256_json(self._payload(include_seed=True)):
            raise ValueError("config_hash does not match generation parameters")
        if self.matching_signature_hash != sha256_json(self._payload(include_seed=False)):
            raise ValueError("matching_signature_hash does not match generation matching parameters")

    def _payload(self, include_seed: bool) -> dict[str, object]:
        payload = {
            "seed_policy_id": self.seed_policy_id,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.do_sample,
            "dtype": self.dtype,
            "device": self.device,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
        }
        if include_seed:
            payload["seed"] = self.seed
        return payload

    @classmethod
    def create(
        cls,
        seed: int,
        seed_policy_id: str,
        temperature: float,
        top_k: int,
        top_p: float,
        max_new_tokens: int,
        do_sample: bool,
        dtype: str,
        device: str,
        backend_id: str,
        backend_version: str,
    ) -> GenerationParameters:
        base = {
            "seed_policy_id": seed_policy_id,
            "temperature": float_for_hash("temperature", temperature),
            "top_k": top_k,
            "top_p": float_for_hash("top_p", top_p),
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "dtype": dtype,
            "device": device,
            "backend_id": backend_id,
            "backend_version": backend_version,
        }
        full = dict(base)
        full["seed"] = seed
        return cls(
            seed=seed,
            seed_policy_id=seed_policy_id,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            dtype=dtype,
            device=device,
            backend_id=backend_id,
            backend_version=backend_version,
            config_hash=sha256_json(full),
            matching_signature_hash=sha256_json(base),
        )


@dataclass(frozen=True, slots=True)
class WatermarkCondition:
    watermark_config_hash: str
    key_split: KeySplit
    key_id: str
    condition_hash: str

    def __post_init__(self) -> None:
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        if not isinstance(self.key_split, KeySplit):
            raise TypeError("key_split must be a KeySplit")
        require_clean_string("key_id", self.key_id)
        require_sha256("condition_hash", self.condition_hash)
        if self.condition_hash != sha256_json(self._payload()):
            raise ValueError("condition_hash does not match watermark condition")

    def _payload(self) -> dict[str, object]:
        return {
            "watermark_config_hash": self.watermark_config_hash,
            "key_split": self.key_split.value,
            "key_id": self.key_id,
        }

    @classmethod
    def create(cls, watermark_config_hash: str, key_split: KeySplit, key_id: str) -> WatermarkCondition:
        payload = {
            "watermark_config_hash": watermark_config_hash,
            "key_split": key_split.value if isinstance(key_split, KeySplit) else key_split,
            "key_id": key_id,
        }
        return cls(
            watermark_config_hash=watermark_config_hash,
            key_split=key_split,
            key_id=key_id,
            condition_hash=sha256_json(payload),
        )
