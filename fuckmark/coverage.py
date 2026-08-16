from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from ._validation import require_int


@dataclass(frozen=True, order=True, slots=True)
class Interval:
    start: int
    end_exclusive: int

    def __post_init__(self) -> None:
        require_int("Interval start", self.start)
        require_int("Interval end_exclusive", self.end_exclusive)
        if self.start < 0:
            raise ValueError("Interval start must be non-negative")
        if self.end_exclusive < self.start:
            raise ValueError("Interval end must not precede start")

    @property
    def size(self) -> int:
        return self.end_exclusive - self.start


def substitution_observation_interval(token_index: int, token_count: int, ngram_len: int) -> Interval:
    require_int("token_index", token_index)
    require_int("token_count", token_count)
    require_int("ngram_len", ngram_len)
    if token_count < 0:
        raise ValueError("token_count must be non-negative")
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if token_index < 0 or token_index >= token_count:
        raise ValueError("token_index is outside the token sequence")
    observation_count = max(0, token_count - ngram_len + 1)
    if observation_count == 0:
        return Interval(0, 0)
    start = max(0, token_index - ngram_len + 1)
    end_exclusive = min(token_index + 1, observation_count)
    return Interval(start, max(start, end_exclusive))


def merge_intervals(intervals: Iterable[Interval]) -> tuple[Interval, ...]:
    materialized = tuple(intervals)
    if any(not isinstance(interval, Interval) for interval in materialized):
        raise TypeError("merge_intervals accepts only Interval values")
    ordered = sorted(
        (interval for interval in materialized if interval.size > 0),
        key=lambda item: (item.start, item.end_exclusive),
    )
    if not ordered:
        return ()
    merged: list[Interval] = []
    current = ordered[0]
    for interval in ordered[1:]:
        if interval.start <= current.end_exclusive:
            current = Interval(current.start, max(current.end_exclusive, interval.end_exclusive))
        else:
            merged.append(current)
            current = interval
    merged.append(current)
    return tuple(merged)


def union_size(intervals: Iterable[Interval]) -> int:
    return sum(interval.size for interval in merge_intervals(intervals))
