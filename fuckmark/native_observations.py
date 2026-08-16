from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ._validation import normalize_token_sequence, require_bool, require_clean_string, require_int, require_sha256, validate_token_sequence
from .adapters.base import AdapterSignals, WatermarkAdapter


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class NativeObservationRecord:
    sample_id: str
    adapter_id: str
    adapter_algorithm_version: str
    adapter_config_hash: str
    source_id: str
    source_commit: str
    eos_token_id: int
    index: int
    token_start: int
    token_end_exclusive: int
    ngram: tuple[int, ...]
    context: tuple[int, ...]
    current_token: int
    repeated: bool
    context_valid: bool
    eos_valid: bool
    valid: bool
    g_values: tuple[int, ...]

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_clean_string("source_id", self.source_id)
        require_clean_string("source_commit", self.source_commit)
        if _GIT_SHA_RE.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be a full lowercase 40-character Git revision")
        for name, value in (
            ("eos_token_id", self.eos_token_id),
            ("index", self.index),
            ("token_start", self.token_start),
            ("token_end_exclusive", self.token_end_exclusive),
            ("current_token", self.current_token),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name, value in (
            ("repeated", self.repeated),
            ("context_valid", self.context_valid),
            ("eos_valid", self.eos_valid),
            ("valid", self.valid),
        ):
            require_bool(name, value)
        if not isinstance(self.ngram, tuple):
            raise TypeError("ngram must be a tuple")
        if not isinstance(self.context, tuple):
            raise TypeError("context must be a tuple")
        if not isinstance(self.g_values, tuple):
            raise TypeError("g_values must be a tuple")
        validate_token_sequence("ngram", self.ngram)
        validate_token_sequence("context", self.context)
        if len(self.ngram) < 2:
            raise ValueError("ngram must contain at least two token IDs")
        if self.context != self.ngram[:-1]:
            raise ValueError("context must equal the n-gram without its current token")
        if self.current_token != self.ngram[-1]:
            raise ValueError("current_token must equal the final n-gram token")
        if self.index != self.token_start:
            raise ValueError("index must equal token_start for unit-step token n-grams")
        if self.token_end_exclusive != self.token_start + len(self.ngram):
            raise ValueError("token span must match n-gram length")
        if self.repeated != (not self.context_valid):
            raise ValueError("repeated must be the inverse of context_valid")
        if self.valid != (self.context_valid and self.eos_valid):
            raise ValueError("valid must equal context_valid AND eos_valid")
        if not self.g_values:
            raise ValueError("g_values must contain at least one watermark depth")
        for value in self.g_values:
            require_int("g-value", value)
            if value not in (0, 1):
                raise ValueError("g-values must be binary integers")

    @property
    def depth(self) -> int:
        return len(self.g_values)

    @property
    def current_token_index(self) -> int:
        return self.token_end_exclusive - 1


@dataclass(frozen=True, slots=True)
class NativeObservationBatch:
    sample_id: str
    adapter_id: str
    adapter_algorithm_version: str
    adapter_config_hash: str
    source_id: str
    source_commit: str
    ngram_len: int
    depth: int
    token_ids: tuple[int, ...]
    eos_token_id: int
    records: tuple[NativeObservationRecord, ...]

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_clean_string("source_id", self.source_id)
        require_clean_string("source_commit", self.source_commit)
        if _GIT_SHA_RE.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be a full lowercase 40-character Git revision")
        for name, value in (
            ("ngram_len", self.ngram_len),
            ("depth", self.depth),
            ("eos_token_id", self.eos_token_id),
        ):
            require_int(name, value)
        if self.ngram_len < 2:
            raise ValueError("ngram_len must be at least 2")
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if self.eos_token_id < 0:
            raise ValueError("eos_token_id must be non-negative")
        if not isinstance(self.token_ids, tuple):
            raise TypeError("token_ids must be a tuple")
        validate_token_sequence("token_ids", self.token_ids)
        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple")
        expected_count = max(0, len(self.token_ids) - self.ngram_len + 1)
        if len(self.records) != expected_count:
            raise ValueError("record count does not match token_count and ngram_len")
        for expected_index, record in enumerate(self.records):
            if not isinstance(record, NativeObservationRecord):
                raise TypeError("records must contain only NativeObservationRecord values")
            if record.sample_id != self.sample_id:
                raise ValueError("record sample_id does not match batch")
            if record.adapter_id != self.adapter_id:
                raise ValueError("record adapter_id does not match batch")
            if record.adapter_algorithm_version != self.adapter_algorithm_version:
                raise ValueError("record adapter_algorithm_version does not match batch")
            if record.adapter_config_hash != self.adapter_config_hash:
                raise ValueError("record adapter_config_hash does not match batch")
            if record.source_id != self.source_id or record.source_commit != self.source_commit:
                raise ValueError("record source identity does not match batch")
            if record.eos_token_id != self.eos_token_id:
                raise ValueError("record eos_token_id does not match batch")
            if record.index != expected_index:
                raise ValueError("records must be complete and ordered by observation index")
            if len(record.ngram) != self.ngram_len:
                raise ValueError("record n-gram length does not match batch")
            if record.depth != self.depth:
                raise ValueError("record g-value depth does not match batch")
            expected_ngram = self.token_ids[expected_index : expected_index + self.ngram_len]
            if record.ngram != expected_ngram:
                raise ValueError("record n-gram does not match batch token_ids")

    @property
    def token_count(self) -> int:
        return len(self.token_ids)

    @property
    def valid_mask(self) -> tuple[bool, ...]:
        return tuple(record.valid for record in self.records)

    @property
    def repeated_mask(self) -> tuple[bool, ...]:
        return tuple(record.repeated for record in self.records)

    @property
    def g_values(self) -> tuple[tuple[int, ...], ...]:
        return tuple(record.g_values for record in self.records)


def build_native_observations(
    sample_id: str,
    token_ids: Sequence[int],
    eos_token_id: int,
    adapter: WatermarkAdapter,
) -> NativeObservationBatch:
    require_clean_string("sample_id", sample_id)
    normalized_token_ids = normalize_token_sequence("token_ids", token_ids)
    require_int("eos_token_id", eos_token_id)
    if eos_token_id < 0:
        raise ValueError("eos_token_id must be non-negative")
    if not isinstance(adapter, WatermarkAdapter):
        raise TypeError("adapter must satisfy the WatermarkAdapter protocol")
    require_clean_string("adapter_id", adapter.adapter_id)
    require_clean_string("adapter_algorithm_version", adapter.algorithm_version)
    require_int("adapter ngram_len", adapter.ngram_len)
    require_int("adapter depth", adapter.depth)
    if adapter.ngram_len < 2:
        raise ValueError("adapter ngram_len must be at least 2")
    if adapter.depth <= 0:
        raise ValueError("adapter depth must be positive")
    fingerprint = adapter.configuration_fingerprint()
    require_sha256("adapter configuration fingerprint", fingerprint)
    signals = adapter.signals(normalized_token_ids, eos_token_id)
    if not isinstance(signals, AdapterSignals):
        raise TypeError("adapter signals() must return AdapterSignals")
    if signals.depth != adapter.depth:
        raise ValueError("adapter signals depth does not match adapter depth")
    expected_count = max(0, len(normalized_token_ids) - adapter.ngram_len + 1)
    if signals.observation_count != expected_count:
        raise ValueError("adapter signals observation count does not match token geometry")
    source_pin = adapter.source_pin
    records = tuple(
        NativeObservationRecord(
            sample_id=sample_id,
            adapter_id=adapter.adapter_id,
            adapter_algorithm_version=adapter.algorithm_version,
            adapter_config_hash=fingerprint,
            source_id=source_pin.source_id,
            source_commit=source_pin.commit,
            eos_token_id=eos_token_id,
            index=index,
            token_start=index,
            token_end_exclusive=index + adapter.ngram_len,
            ngram=normalized_token_ids[index : index + adapter.ngram_len],
            context=normalized_token_ids[index : index + adapter.ngram_len - 1],
            current_token=normalized_token_ids[index + adapter.ngram_len - 1],
            repeated=not signals.context_mask[index],
            context_valid=signals.context_mask[index],
            eos_valid=signals.eos_mask[index],
            valid=signals.valid_mask[index],
            g_values=signals.g_values[index],
        )
        for index in range(expected_count)
    )
    return NativeObservationBatch(
        sample_id=sample_id,
        adapter_id=adapter.adapter_id,
        adapter_algorithm_version=adapter.algorithm_version,
        adapter_config_hash=fingerprint,
        source_id=source_pin.source_id,
        source_commit=source_pin.commit,
        ngram_len=adapter.ngram_len,
        depth=adapter.depth,
        token_ids=normalized_token_ids,
        eos_token_id=eos_token_id,
        records=records,
    )
