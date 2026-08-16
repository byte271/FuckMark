from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def require_clean_string(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty and must not have surrounding whitespace")
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value):
        raise ValueError(f"{name} must not contain control or formatting characters")


def require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")


def require_sha256(name: str, value: str) -> None:
    require_clean_string(name, value)
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hexadecimal digest")


def normalize_token_sequence(name: str, tokens: Sequence[int]) -> tuple[int, ...]:
    if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of integer token IDs")
    materialized = tuple(tokens)
    for token in materialized:
        if isinstance(token, bool) or not isinstance(token, int):
            raise TypeError(f"{name} must contain only integer token IDs")
        if token < 0:
            raise ValueError(f"{name} must contain only non-negative token IDs")
    return materialized


def validate_token_sequence(name: str, tokens: Sequence[int]) -> None:
    normalize_token_sequence(name, tokens)
