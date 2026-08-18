from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .._validation import normalize_token_sequence, require_int, require_sha256
from ..hashing import sha256_json
from .observations import GeometryConfig, window_count


PUBLIC_REPETITION_GEOMETRY_ALGORITHM_VERSION = "public-context-repetition-v1"


@dataclass(frozen=True, slots=True)
class RepetitionMaskReport:
    algorithm_version: str
    ngram_len: int
    context_history_size: int
    token_hash: str
    token_count: int
    context_count: int
    eligible_windows: tuple[bool, ...]
    repeated_context_indices: tuple[int, ...]
    eligible_count: int
    repeated_count: int
    mask_hash: str
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != PUBLIC_REPETITION_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported repetition geometry algorithm version")
        for name in (
            "ngram_len",
            "context_history_size",
            "token_count",
            "context_count",
            "eligible_count",
            "repeated_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.context_count != window_count(self.token_count, self.ngram_len):
            raise ValueError("context_count does not match token geometry")
        if not isinstance(self.eligible_windows, tuple) or any(
            not isinstance(value, bool) for value in self.eligible_windows
        ):
            raise TypeError("eligible_windows must be a tuple of booleans")
        if len(self.eligible_windows) != self.context_count:
            raise ValueError("eligible_windows length does not match context_count")
        if not isinstance(self.repeated_context_indices, tuple):
            raise TypeError("repeated_context_indices must be a tuple")
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in self.repeated_context_indices
        ):
            raise TypeError("repeated_context_indices must contain integers")
        expected_repeated = tuple(
            index for index, eligible in enumerate(self.eligible_windows) if not eligible
        )
        if self.repeated_context_indices != expected_repeated:
            raise ValueError("repeated_context_indices do not match eligible_windows")
        if self.eligible_count != sum(self.eligible_windows):
            raise ValueError("eligible_count does not match eligible_windows")
        if self.repeated_count != self.context_count - self.eligible_count:
            raise ValueError("repeated_count does not partition context_count")
        require_sha256("token_hash", self.token_hash)
        require_sha256("mask_hash", self.mask_hash)
        require_sha256("report_hash", self.report_hash)
        if self.mask_hash != sha256_json(self.eligible_windows):
            raise ValueError("mask_hash does not match eligible_windows")
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match RepetitionMaskReport payload")

    @property
    def repeated_ratio(self) -> float:
        if self.context_count == 0:
            return 0.0
        return self.repeated_count / self.context_count

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "token_hash": self.token_hash,
            "token_count": self.token_count,
            "context_count": self.context_count,
            "eligible_windows": self.eligible_windows,
            "repeated_context_indices": self.repeated_context_indices,
            "eligible_count": self.eligible_count,
            "repeated_count": self.repeated_count,
            "mask_hash": self.mask_hash,
        }


@dataclass(frozen=True, slots=True)
class PublicRepetitionGeometry:
    algorithm_version: str
    ngram_len: int
    context_history_size: int
    policy_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != PUBLIC_REPETITION_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported repetition geometry algorithm version")
        require_int("ngram_len", self.ngram_len)
        require_int("context_history_size", self.context_history_size)
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.context_history_size < 0:
            raise ValueError("context_history_size must be non-negative")
        require_sha256("policy_hash", self.policy_hash)
        if self.policy_hash != sha256_json(self.payload()):
            raise ValueError("policy_hash does not match PublicRepetitionGeometry payload")

    @classmethod
    def create(
        cls,
        *,
        ngram_len: int,
        context_history_size: int,
    ) -> PublicRepetitionGeometry:
        payload = {
            "algorithm_version": PUBLIC_REPETITION_GEOMETRY_ALGORITHM_VERSION,
            "ngram_len": ngram_len,
            "context_history_size": context_history_size,
        }
        return cls(
            algorithm_version=PUBLIC_REPETITION_GEOMETRY_ALGORITHM_VERSION,
            ngram_len=ngram_len,
            context_history_size=context_history_size,
            policy_hash=sha256_json(payload),
        )

    @property
    def policy_id(self) -> str:
        return f"{self.algorithm_version}:{self.policy_hash}"

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def secret_access_observed(self) -> bool:
        return False

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
        }

    def evaluate(self, tokens: Sequence[int]) -> RepetitionMaskReport:
        normalized = normalize_token_sequence("tokens", tokens)
        context_count = window_count(len(normalized), self.ngram_len)
        history: list[tuple[int, ...]] = []
        eligible: list[bool] = []
        for index in range(context_count):
            context = normalized[index : index + self.ngram_len - 1]
            repeated = context in history
            eligible.append(not repeated)
            if self.context_history_size > 0:
                history.insert(0, context)
                del history[self.context_history_size :]
        eligible_windows = tuple(eligible)
        repeated_indices = tuple(
            index for index, value in enumerate(eligible_windows) if not value
        )
        payload = {
            "algorithm_version": self.algorithm_version,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "token_hash": sha256_json(normalized),
            "token_count": len(normalized),
            "context_count": context_count,
            "eligible_windows": eligible_windows,
            "repeated_context_indices": repeated_indices,
            "eligible_count": sum(eligible_windows),
            "repeated_count": len(repeated_indices),
            "mask_hash": sha256_json(eligible_windows),
        }
        return RepetitionMaskReport(
            algorithm_version=self.algorithm_version,
            ngram_len=self.ngram_len,
            context_history_size=self.context_history_size,
            token_hash=payload["token_hash"],
            token_count=len(normalized),
            context_count=context_count,
            eligible_windows=eligible_windows,
            repeated_context_indices=repeated_indices,
            eligible_count=payload["eligible_count"],
            repeated_count=payload["repeated_count"],
            mask_hash=payload["mask_hash"],
            report_hash=sha256_json(payload),
        )

    def eligibility_policy(
        self,
        tokens: tuple[int, ...],
        config: GeometryConfig,
    ) -> tuple[bool, ...]:
        if not isinstance(config, GeometryConfig):
            raise TypeError("config must be a GeometryConfig")
        if config.ngram_len != self.ngram_len:
            raise ValueError("geometry ngram_len does not match repetition policy")
        if config.repetition_mask_policy_id != self.policy_id:
            raise ValueError("geometry repetition policy identity does not match")
        return self.evaluate(tokens).eligible_windows
