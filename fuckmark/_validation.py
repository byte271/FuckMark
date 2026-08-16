from __future__ import annotations

from collections.abc import Sequence


def require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")


def validate_token_sequence(name: str, tokens: Sequence[int]) -> None:
    if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of integer token IDs")
    for token in tokens:
        if isinstance(token, bool) or not isinstance(token, int):
            raise TypeError(f"{name} must contain only integer token IDs")
        if token < 0:
            raise ValueError(f"{name} must contain only non-negative token IDs")
