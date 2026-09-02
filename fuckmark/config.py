from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping
from pathlib import PurePath
from typing import Any


def canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        if isinstance(value, type):
            raise TypeError("Dataclass types cannot be canonicalized without an instance")
        return canonicalize(dataclasses.asdict(value))
    if isinstance(value, PurePath):
        return value.as_posix()
    if isinstance(value, Mapping):
        keys = tuple(value.keys())
        if any(not isinstance(key, str) for key in keys):
            raise TypeError("Canonical JSON object keys must be strings")
        return {key: canonicalize(value[key]) for key in sorted(keys)}
    if isinstance(value, tuple):
        return [canonicalize(item) for item in value]
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [canonicalize(item) for item in value]
        return sorted(normalized, key=canonical_json_text)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical JSON does not allow non-finite floating-point values")
        if value == 0.0:
            return 0.0
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported canonical JSON value type: {type(value).__name__}")


def canonical_json_text(value: Any) -> str:
    normalized = canonicalize(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json_text(value).encode("utf-8", "surrogatepass")
