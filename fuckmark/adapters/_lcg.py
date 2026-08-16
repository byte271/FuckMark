from __future__ import annotations

from collections import Counter, deque
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


class BoundedHashHistory:
    __slots__ = ("_size", "_inserted", "_values", "_counts")

    def __init__(self, size: int) -> None:
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size must be an integer")
        if size <= 0:
            raise ValueError("size must be positive")
        self._size = size
        self._inserted = 0
        self._values: deque[int] = deque()
        self._counts: Counter[int] = Counter()

    def contains(self, value: int) -> bool:
        return (value == 0 and self._inserted < self._size) or self._counts[value] > 0

    def push(self, value: int) -> None:
        if len(self._values) == self._size:
            removed = self._values.popleft()
            self._counts[removed] -= 1
            if self._counts[removed] == 0:
                del self._counts[removed]
        self._values.append(value)
        self._counts[value] += 1
        self._inserted += 1
