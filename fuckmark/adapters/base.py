from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..types import SourcePin


_ADAPTER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class AdapterSignals:
    depth: int
    g_values: tuple[tuple[int, ...], ...]
    context_mask: tuple[bool, ...]
    eos_mask: tuple[bool, ...]

    def __post_init__(self) -> None:
        require_int("depth", self.depth)
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if not isinstance(self.g_values, tuple):
            raise TypeError("g_values must be a tuple")
        if not isinstance(self.context_mask, tuple):
            raise TypeError("context_mask must be a tuple")
        if not isinstance(self.eos_mask, tuple):
            raise TypeError("eos_mask must be a tuple")
        count = len(self.g_values)
        if len(self.context_mask) != count or len(self.eos_mask) != count:
            raise ValueError("g_values, context_mask, and eos_mask must have the same observation count")
        for row in self.g_values:
            if not isinstance(row, tuple):
                raise TypeError("Each g-value row must be a tuple")
            if len(row) != self.depth:
                raise ValueError("Each g-value row must match depth")
            for value in row:
                require_int("g-value", value)
                if value not in (0, 1):
                    raise ValueError("g-values must be binary integers")
        for value in self.context_mask:
            require_bool("context_mask value", value)
        for value in self.eos_mask:
            require_bool("eos_mask value", value)

    @property
    def observation_count(self) -> int:
        return len(self.g_values)

    @property
    def valid_mask(self) -> tuple[bool, ...]:
        return tuple(context_valid and eos_valid for context_valid, eos_valid in zip(self.context_mask, self.eos_mask))


@runtime_checkable
class WatermarkAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...

    @property
    def algorithm_version(self) -> str: ...

    @property
    def source_pin(self) -> SourcePin: ...

    @property
    def ngram_len(self) -> int: ...

    @property
    def depth(self) -> int: ...

    def configuration_fingerprint(self) -> str: ...

    def compute_g_values(self, token_ids: Sequence[int]) -> tuple[tuple[int, ...], ...]: ...

    def compute_context_repetition_mask(self, token_ids: Sequence[int]) -> tuple[bool, ...]: ...

    def compute_eos_mask(self, token_ids: Sequence[int], eos_token_id: int) -> tuple[bool, ...]: ...

    def signals(self, token_ids: Sequence[int], eos_token_id: int) -> AdapterSignals: ...


AdapterFactory = Callable[[Mapping[str, object]], WatermarkAdapter]


class AdapterRegistry:
    __slots__ = ("_factories",)

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    @property
    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def register(self, adapter_id: str, factory: AdapterFactory) -> None:
        require_clean_string("adapter_id", adapter_id)
        if _ADAPTER_ID_RE.fullmatch(adapter_id) is None:
            raise ValueError("adapter_id must use lowercase machine-identifier form")
        if not callable(factory):
            raise TypeError("factory must be callable")
        if adapter_id in self._factories:
            raise ValueError(f"Adapter already registered: {adapter_id}")
        self._factories[adapter_id] = factory

    def create(self, adapter_id: str, config: Mapping[str, object]) -> WatermarkAdapter:
        require_clean_string("adapter_id", adapter_id)
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        snapshot = dict(config)
        if any(not isinstance(key, str) for key in snapshot):
            raise TypeError("config keys must be strings")
        try:
            factory = self._factories[adapter_id]
        except KeyError as error:
            raise KeyError(f"Unknown adapter_id: {adapter_id}") from error
        adapter = factory(snapshot)
        if not isinstance(adapter, WatermarkAdapter):
            raise TypeError("factory did not return a WatermarkAdapter-compatible object")
        if adapter.adapter_id != adapter_id:
            raise ValueError("factory returned an adapter with a mismatched adapter_id")
        require_sha256("adapter configuration fingerprint", adapter.configuration_fingerprint())
        return adapter
