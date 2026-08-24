from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .._validation import normalize_token_sequence, require_sha256
from ..hashing import sha256_json
from .observations import RootObservationSet


TUPLE_CLOSURE_ALGORITHM_VERSION = "root-tuple-recreation-closure-v1"


@dataclass(frozen=True, slots=True)
class TupleClosureReport:
    algorithm_version: str
    root_token_hash: str
    transformed_token_hash: str
    ngram_len: int
    transformed_token_count: int
    root_window_count: int
    root_eligible_window_count: int
    leaked_window_count: int
    leaked_distinct_tuple_count: int
    leaked_occurrence_count: int
    closure_free: bool
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TUPLE_CLOSURE_ALGORITHM_VERSION:
            raise ValueError("unsupported tuple closure algorithm version")
        require_sha256("root_token_hash", self.root_token_hash)
        require_sha256("transformed_token_hash", self.transformed_token_hash)
        for name in (
            "ngram_len",
            "transformed_token_count",
            "root_window_count",
            "root_eligible_window_count",
            "leaked_window_count",
            "leaked_distinct_tuple_count",
            "leaked_occurrence_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.leaked_window_count > self.root_eligible_window_count:
            raise ValueError("leaked windows cannot exceed root eligible windows")
        if self.leaked_distinct_tuple_count > self.leaked_window_count:
            raise ValueError("distinct leaked tuples cannot exceed leaked windows")
        if type(self.closure_free) is not bool:
            raise TypeError("closure_free must be a boolean")
        expected = self.root_eligible_window_count > 0 and self.leaked_window_count == 0
        if self.closure_free != expected:
            raise ValueError("closure_free does not match counts")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match tuple closure payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "root_token_hash": self.root_token_hash,
            "transformed_token_hash": self.transformed_token_hash,
            "ngram_len": self.ngram_len,
            "transformed_token_count": self.transformed_token_count,
            "root_window_count": self.root_window_count,
            "root_eligible_window_count": self.root_eligible_window_count,
            "leaked_window_count": self.leaked_window_count,
            "leaked_distinct_tuple_count": self.leaked_distinct_tuple_count,
            "leaked_occurrence_count": self.leaked_occurrence_count,
            "closure_free": self.closure_free,
        }


def compute_tuple_closure(
    *,
    root: RootObservationSet,
    transformed_tokens: Sequence[int],
    expected_output_token_hash: str | None = None,
) -> TupleClosureReport:
    if not isinstance(root, RootObservationSet):
        raise TypeError("root must be a RootObservationSet")
    transformed = normalize_token_sequence("transformed_tokens", transformed_tokens)
    transformed_token_hash = sha256_json(transformed)
    if expected_output_token_hash is not None:
        require_sha256("expected_output_token_hash", expected_output_token_hash)
        if transformed_token_hash != expected_output_token_hash:
            raise ValueError(
                "tokenizer path inconsistency: closure tokens do not match geometry output tokens"
            )
    ngram_len = root.ngram_len
    output_window_count = max(0, len(transformed) - ngram_len + 1)
    output_counts: Counter[tuple[int, ...]] = Counter(
        tuple(transformed[index : index + ngram_len]) for index in range(output_window_count)
    )
    leaked_windows = 0
    leaked_occurrences = 0
    counted_tuples: set[tuple[int, ...]] = set()
    for observation in root.observations:
        if not observation.eligible:
            continue
        occurrence = tuple(observation.token_ids)
        count = output_counts.get(occurrence, 0)
        if count <= 0:
            continue
        leaked_windows += 1
        if occurrence not in counted_tuples:
            counted_tuples.add(occurrence)
            leaked_occurrences += count
    fields = {
        "algorithm_version": TUPLE_CLOSURE_ALGORITHM_VERSION,
        "root_token_hash": root.root_token_hash,
        "transformed_token_hash": transformed_token_hash,
        "ngram_len": ngram_len,
        "transformed_token_count": len(transformed),
        "root_window_count": len(root.observations),
        "root_eligible_window_count": root.eligible_count,
        "leaked_window_count": leaked_windows,
        "leaked_distinct_tuple_count": len(counted_tuples),
        "leaked_occurrence_count": leaked_occurrences,
        "closure_free": root.eligible_count > 0 and leaked_windows == 0,
    }
    return TupleClosureReport(**fields, report_hash=sha256_json(dict(fields)))
