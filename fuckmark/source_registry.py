from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .types import SourcePin


_SOURCE_PIN_FIELDS = frozenset({"source_id", "repository", "commit", "license_id", "critical_files"})


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"Duplicate JSON object key: {key}")
        output[key] = value
    return output


def load_source_pin(path: str | Path) -> SourcePin:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except UnicodeDecodeError as error:
        raise ValueError(f"Source pin file is not valid UTF-8: {file_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Source pin file is not valid JSON: {file_path}") from error
    if not isinstance(payload, dict):
        raise TypeError("Source pin JSON root must be an object")
    fields = frozenset(payload)
    if fields != _SOURCE_PIN_FIELDS:
        missing = sorted(_SOURCE_PIN_FIELDS - fields)
        extra = sorted(fields - _SOURCE_PIN_FIELDS)
        raise ValueError(f"Source pin fields do not match schema: missing={missing}, extra={extra}")
    return SourcePin(**payload)


class SourcePinRegistry:
    __slots__ = ("_pins", "_source_ids")

    def __init__(self, pins: Iterable[SourcePin]) -> None:
        if isinstance(pins, (str, bytes, bytearray)):
            raise TypeError("pins must be an iterable of SourcePin values")
        materialized = tuple(pins)
        if not materialized:
            raise ValueError("Source pin registry must contain at least one source pin")
        if any(not isinstance(pin, SourcePin) for pin in materialized):
            raise TypeError("pins must contain only SourcePin values")
        by_id: dict[str, SourcePin] = {}
        repository_commits: set[tuple[str, str]] = set()
        for pin in materialized:
            if pin.source_id in by_id:
                raise ValueError(f"Duplicate source_id: {pin.source_id}")
            identity = (pin.repository, pin.commit)
            if identity in repository_commits:
                raise ValueError(f"Duplicate repository revision: {pin.repository}@{pin.commit}")
            by_id[pin.source_id] = pin
            repository_commits.add(identity)
        self._pins = MappingProxyType(by_id)
        self._source_ids = tuple(sorted(by_id))

    @classmethod
    def from_directory(cls, directory: str | Path) -> SourcePinRegistry:
        root = Path(directory)
        if not root.is_dir():
            raise NotADirectoryError(root)
        paths = tuple(sorted(root.glob("*.json")))
        if not paths:
            raise ValueError("Source pin directory contains no JSON source pins")
        return cls(load_source_pin(path) for path in paths)

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self._source_ids

    def get(self, source_id: str) -> SourcePin:
        try:
            return self._pins[source_id]
        except KeyError as error:
            raise KeyError(f"Unknown source_id: {source_id}") from error
