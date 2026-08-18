from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..coverage import Interval, merge_intervals, substitution_observation_interval
from ..hashing import sha256_json, sha256_text
from .candidate_artifacts import CandidateEnumeration, TransformCandidate


TOKENIZER_GEOMETRY_ALGORITHM_VERSION = "public-tokenizer-candidate-geometry-v1"


class TokenizerGeometryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TokenOffset:
    token_index: int
    token_id: int
    start: int
    end: int

    def __post_init__(self) -> None:
        for name, value in (
            ("token_index", self.token_index),
            ("token_id", self.token_id),
            ("start", self.start),
            ("end", self.end),
        ):
            require_int(name, value)
        if self.token_index < 0 or self.token_id < 0 or self.start < 0 or self.end < self.start:
            raise ValueError("token offset values must be non-negative and ordered")


@dataclass(frozen=True, slots=True)
class CandidateTokenizerGeometry:
    algorithm_version: str
    input_hash: str
    enumeration_hash: str
    tokenizer_identity_hash: str
    ngram_len: int
    token_count: int
    token_offsets: tuple[TokenOffset, ...]
    candidate_coverage: tuple[tuple[str, tuple[Interval, ...]], ...]
    geometry_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TOKENIZER_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported tokenizer geometry algorithm version")
        for name, value in (
            ("input_hash", self.input_hash),
            ("enumeration_hash", self.enumeration_hash),
            ("tokenizer_identity_hash", self.tokenizer_identity_hash),
            ("geometry_hash", self.geometry_hash),
        ):
            require_sha256(name, value)
        require_int("ngram_len", self.ngram_len)
        require_int("token_count", self.token_count)
        if self.ngram_len <= 0 or self.token_count <= 0:
            raise ValueError("ngram_len and token_count must be positive")
        if not isinstance(self.token_offsets, tuple) or any(
            not isinstance(value, TokenOffset) for value in self.token_offsets
        ):
            raise TypeError("token_offsets must contain TokenOffset values")
        if len(self.token_offsets) != self.token_count:
            raise ValueError("token offset count must equal token_count")
        if tuple(value.token_index for value in self.token_offsets) != tuple(range(self.token_count)):
            raise ValueError("token offsets must contain every token index in order")
        previous_start = -1
        previous_end = -1
        for offset in self.token_offsets:
            if offset.start < previous_start:
                raise ValueError("token offsets must be monotonically ordered")
            if offset.end < previous_end and offset.start == previous_start:
                raise ValueError("equal-start token offsets must not move backward")
            previous_start = offset.start
            previous_end = offset.end
        if not isinstance(self.candidate_coverage, tuple):
            raise TypeError("candidate_coverage must be a tuple")
        candidate_ids = tuple(value[0] for value in self.candidate_coverage)
        if candidate_ids != tuple(sorted(candidate_ids)) or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate coverage IDs must be unique and sorted")
        for candidate_id, intervals in self.candidate_coverage:
            require_sha256("candidate_id", candidate_id)
            if not isinstance(intervals, tuple) or any(not isinstance(value, Interval) for value in intervals):
                raise TypeError("candidate coverage intervals must contain Interval values")
            if intervals != merge_intervals(intervals):
                raise ValueError("candidate coverage intervals must be merged and canonical")
        if self.geometry_hash != sha256_json(self._payload()):
            raise ValueError("geometry_hash does not match tokenizer candidate geometry")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "input_hash": self.input_hash,
            "enumeration_hash": self.enumeration_hash,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "ngram_len": self.ngram_len,
            "token_count": self.token_count,
            "token_offsets": self.token_offsets,
            "candidate_coverage": self.candidate_coverage,
        }

    def coverage_mapping(self) -> dict[str, tuple[Interval, ...]]:
        return dict(self.candidate_coverage)


def _validate_offsets(text: str, token_ids: tuple[int, ...], offsets: tuple[tuple[int, int], ...]) -> tuple[TokenOffset, ...]:
    if len(token_ids) != len(offsets):
        raise TokenizerGeometryError("token IDs and offset mapping must have equal lengths")
    if not token_ids:
        raise TokenizerGeometryError("tokenizer geometry requires at least one token")
    output: list[TokenOffset] = []
    for index, (token_id, raw_offset) in enumerate(zip(token_ids, offsets)):
        require_int("token_id", token_id)
        if token_id < 0:
            raise TokenizerGeometryError("token IDs must be non-negative")
        if not isinstance(raw_offset, tuple) or len(raw_offset) != 2:
            raise TypeError("offset mapping values must be two-item tuples")
        start, end = raw_offset
        require_int("offset start", start)
        require_int("offset end", end)
        if start < 0 or end < start or end > len(text):
            raise TokenizerGeometryError("tokenizer offset is outside source text")
        if start == end:
            raise TokenizerGeometryError(
                "zero-width tokenizer offsets are not allowed in candidate geometry; remove special tokens"
            )
        output.append(TokenOffset(index, token_id, start, end))
    return tuple(output)


def _candidate_coverage(
    candidate: TransformCandidate,
    token_offsets: tuple[TokenOffset, ...],
    token_count: int,
    ngram_len: int,
) -> tuple[Interval, ...]:
    overlapping = tuple(
        value.token_index
        for value in token_offsets
        if value.start < candidate.end and candidate.start < value.end
    )
    if not overlapping:
        raise TokenizerGeometryError(
            f"candidate {candidate.candidate_id} does not overlap any public tokenizer token"
        )
    return merge_intervals(
        substitution_observation_interval(index, token_count, ngram_len)
        for index in overlapping
    )


def build_candidate_tokenizer_geometry(
    text: str,
    enumeration: CandidateEnumeration,
    token_ids: Sequence[int],
    offset_mapping: Sequence[tuple[int, int]],
    *,
    tokenizer_identity_hash: str,
    ngram_len: int,
) -> CandidateTokenizerGeometry:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(enumeration, CandidateEnumeration):
        raise TypeError("enumeration must be a CandidateEnumeration")
    if enumeration.input_text != text or enumeration.input_hash != sha256_text(text):
        raise TokenizerGeometryError("candidate enumeration does not bind the supplied source text")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if not isinstance(token_ids, Sequence) or isinstance(token_ids, (str, bytes, bytearray)):
        raise TypeError("token_ids must be a sequence")
    if not isinstance(offset_mapping, Sequence) or isinstance(offset_mapping, (str, bytes, bytearray)):
        raise TypeError("offset_mapping must be a sequence")
    ids = tuple(token_ids)
    offsets = tuple(offset_mapping)
    token_offsets = _validate_offsets(text, ids, offsets)
    coverage = tuple(
        sorted(
            (
                candidate.candidate_id,
                _candidate_coverage(candidate, token_offsets, len(ids), ngram_len),
            )
            for candidate in enumeration.candidates
        )
    )
    payload = {
        "algorithm_version": TOKENIZER_GEOMETRY_ALGORITHM_VERSION,
        "input_hash": enumeration.input_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "ngram_len": ngram_len,
        "token_count": len(ids),
        "token_offsets": token_offsets,
        "candidate_coverage": coverage,
    }
    return CandidateTokenizerGeometry(
        algorithm_version=TOKENIZER_GEOMETRY_ALGORITHM_VERSION,
        input_hash=enumeration.input_hash,
        enumeration_hash=enumeration.enumeration_hash,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        token_count=len(ids),
        token_offsets=token_offsets,
        candidate_coverage=coverage,
        geometry_hash=sha256_json(payload),
    )
