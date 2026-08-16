from __future__ import annotations

from collections.abc import Sequence


MULTIPLIER = 6364136223846793005
INCREMENT = 1
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
_INT64_MODULUS = 1 << 64
_INT64_SIGN = 1 << 63


def signed_int64(value: int) -> int:
    value %= _INT64_MODULUS
    if value >= _INT64_SIGN:
        value -= _INT64_MODULUS
    return value


def accumulate_hash(current_hash: int, data: Sequence[int]) -> int:
    output = current_hash
    for value in data:
        output = signed_int64(output + value)
        output = signed_int64(output * MULTIPLIER)
        output = signed_int64(output + INCREMENT)
    return output
