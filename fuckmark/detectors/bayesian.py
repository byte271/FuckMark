from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .._validation import require_clean_string, require_int, require_sha256
from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from ..hashing import sha256_json
from .types import ZeroValidObservationsError


BAYESIAN_CHECKPOINT_ALGORITHM_VERSION = "deepmind-bayesian-checkpoint-v1"
BAYESIAN_CHECKPOINT_JSON_MAX_BYTES = 64 * 1024 * 1024
BAYESIAN_SCORER_ALGORITHM_VERSION = "deepmind-bayesian-posterior-v1"


@dataclass(frozen=True, slots=True)
class BayesianCheckpoint:
    checkpoint_algorithm_version: str
    source_id: str
    source_commit: str
    watermarking_depth: int
    base_rate: float
    beta: tuple[float, ...]
    delta: tuple[tuple[float, ...], ...]
    fixture_kind: str
    checkpoint_hash: str

    def __post_init__(self) -> None:
        require_clean_string("checkpoint_algorithm_version", self.checkpoint_algorithm_version)
        if self.checkpoint_algorithm_version != BAYESIAN_CHECKPOINT_ALGORITHM_VERSION:
            raise ValueError("unsupported Bayesian checkpoint algorithm version")
        require_clean_string("source_id", self.source_id)
        require_clean_string("source_commit", self.source_commit)
        if self.source_id != DEEPMIND_REFERENCE_SOURCE_PIN.source_id:
            raise ValueError("Bayesian checkpoint source_id does not match the pinned DeepMind reference")
        if self.source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit:
            raise ValueError("Bayesian checkpoint source_commit does not match the pinned DeepMind reference")
        require_int("watermarking_depth", self.watermarking_depth)
        if self.watermarking_depth <= 0:
            raise ValueError("watermarking_depth must be positive")
        if isinstance(self.base_rate, bool) or not isinstance(self.base_rate, (int, float)):
            raise TypeError("base_rate must be a real number")
        base_rate = float(self.base_rate)
        if not math.isfinite(base_rate) or base_rate <= 0.0 or base_rate >= 1.0:
            raise ValueError("base_rate must be finite and strictly between 0 and 1")
        object.__setattr__(self, "base_rate", base_rate)
        if not isinstance(self.beta, tuple):
            raise TypeError("beta must be a tuple")
        if len(self.beta) != self.watermarking_depth:
            raise ValueError("beta length must match watermarking_depth")
        beta = tuple(_finite_float("beta value", value) for value in self.beta)
        object.__setattr__(self, "beta", beta)
        if not isinstance(self.delta, tuple):
            raise TypeError("delta must be a tuple")
        if len(self.delta) != self.watermarking_depth:
            raise ValueError("delta row count must match watermarking_depth")
        normalized_rows: list[tuple[float, ...]] = []
        for row_index, row in enumerate(self.delta):
            if not isinstance(row, tuple):
                raise TypeError("delta rows must be tuples")
            if len(row) != self.watermarking_depth:
                raise ValueError("delta rows must match watermarking_depth")
            normalized = tuple(_finite_float("delta value", value) for value in row)
            if any(normalized[column] != 0.0 for column in range(row_index, self.watermarking_depth)):
                raise ValueError("delta must be strictly lower triangular under source semantics")
            normalized_rows.append(normalized)
        object.__setattr__(self, "delta", tuple(normalized_rows))
        require_clean_string("fixture_kind", self.fixture_kind)
        require_sha256("checkpoint_hash", self.checkpoint_hash)
        if self.checkpoint_hash != sha256_json(self._payload()):
            raise ValueError("checkpoint_hash does not match Bayesian checkpoint")

    def _payload(self) -> dict[str, object]:
        return {
            "checkpoint_algorithm_version": self.checkpoint_algorithm_version,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "watermarking_depth": self.watermarking_depth,
            "base_rate": self.base_rate,
            "beta": self.beta,
            "delta": self.delta,
            "fixture_kind": self.fixture_kind,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> BayesianCheckpoint:
        if not isinstance(value, Mapping):
            raise TypeError("checkpoint must be a mapping")
        snapshot = dict(value)
        required = {
            "checkpoint_algorithm_version",
            "source_id",
            "source_commit",
            "watermarking_depth",
            "base_rate",
            "beta",
            "delta",
            "fixture_kind",
            "checkpoint_hash",
        }
        if set(snapshot) != required:
            raise ValueError("Bayesian checkpoint fields do not match schema")
        beta = snapshot["beta"]
        delta = snapshot["delta"]
        if not isinstance(beta, (tuple, list)):
            raise TypeError("beta must be a tuple or list")
        if not isinstance(delta, (tuple, list)):
            raise TypeError("delta must be a tuple or list")
        rows: list[tuple[object, ...]] = []
        for row in delta:
            if not isinstance(row, (tuple, list)):
                raise TypeError("delta rows must be tuples or lists")
            rows.append(tuple(row))
        return cls(
            checkpoint_algorithm_version=snapshot["checkpoint_algorithm_version"],
            source_id=snapshot["source_id"],
            source_commit=snapshot["source_commit"],
            watermarking_depth=snapshot["watermarking_depth"],
            base_rate=snapshot["base_rate"],
            beta=tuple(beta),
            delta=tuple(rows),
            fixture_kind=snapshot["fixture_kind"],
            checkpoint_hash=snapshot["checkpoint_hash"],
        )


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def load_bayesian_checkpoint(path: str | Path) -> BayesianCheckpoint:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > BAYESIAN_CHECKPOINT_JSON_MAX_BYTES:
        raise ValueError("Bayesian checkpoint JSON exceeds the size limit")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Bayesian checkpoint JSON must contain an object")
    return BayesianCheckpoint.from_mapping(data)


def _normalize_g_values(
    g_values: Sequence[Sequence[int]],
    depth: int,
) -> tuple[tuple[int, ...], ...]:
    if not isinstance(g_values, Sequence) or isinstance(g_values, (str, bytes, bytearray)):
        raise TypeError("g_values must be a sequence of rows")
    rows: list[tuple[int, ...]] = []
    for row in g_values:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)):
            raise TypeError("g-value rows must be sequences")
        normalized = tuple(row)
        if len(normalized) != depth:
            raise ValueError("g-value row depth does not match checkpoint")
        for value in normalized:
            require_int("g-value", value)
            if value not in (0, 1):
                raise ValueError("g-values must be binary integers")
        rows.append(normalized)
    return tuple(rows)


def _normalize_mask(mask: Sequence[bool | int], count: int) -> tuple[bool, ...]:
    if not isinstance(mask, Sequence) or isinstance(mask, (str, bytes, bytearray)):
        raise TypeError("mask must be a sequence")
    values = tuple(mask)
    if len(values) != count:
        raise ValueError("mask length must match g-value row count")
    output: list[bool] = []
    for value in values:
        if isinstance(value, bool):
            output.append(value)
            continue
        require_int("mask value", value)
        if value not in (0, 1):
            raise ValueError("mask values must be booleans or binary integers")
        output.append(bool(value))
    if not any(output):
        raise ZeroValidObservationsError("Bayesian detector mask contains zero valid observations")
    return tuple(output)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exponent = math.exp(-value)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def bayesian_posterior(
    g_values: Sequence[Sequence[int]],
    mask: Sequence[bool | int],
    checkpoint: BayesianCheckpoint,
) -> float:
    if not isinstance(checkpoint, BayesianCheckpoint):
        raise TypeError("checkpoint must be a BayesianCheckpoint")
    rows = _normalize_g_values(g_values, checkpoint.watermarking_depth)
    normalized_mask = _normalize_mask(mask, len(rows))
    prior = min(1.0 - 1e-5, max(1e-5, checkpoint.base_rate))
    log_odds = math.log(prior) - math.log1p(-prior)
    for row, valid in zip(rows, normalized_mask):
        if not valid:
            continue
        for layer, g_value in enumerate(row):
            latent_logit = checkpoint.beta[layer] + math.fsum(
                checkpoint.delta[layer][index] * row[index]
                for index in range(layer)
            )
            p_two = _sigmoid(latent_logit)
            p_one = 1.0 - p_two
            watermarked_likelihood = 0.5 * ((g_value + 0.5) * p_two + p_one)
            log_odds += math.log(max(1e-30, watermarked_likelihood)) - math.log(0.5)
    return _sigmoid(log_odds)
