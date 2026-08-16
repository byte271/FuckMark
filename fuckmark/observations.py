from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections.abc import Sequence

from ._validation import require_int, validate_token_sequence
from .alignment import AlignmentResult, validate_alignment


@dataclass(frozen=True, slots=True)
class TokenNgram:
    index: int
    start: int
    end_exclusive: int
    tokens: tuple[int, ...]

    def __post_init__(self) -> None:
        require_int("index", self.index)
        require_int("start", self.start)
        require_int("end_exclusive", self.end_exclusive)
        if self.index < 0 or self.start < 0:
            raise ValueError("Token n-gram indices must be non-negative")
        if self.end_exclusive <= self.start:
            raise ValueError("Token n-gram must contain at least one token")
        if not isinstance(self.tokens, tuple):
            raise TypeError("Token n-gram tokens must be a tuple")
        if len(self.tokens) != self.end_exclusive - self.start:
            raise ValueError("Token n-gram span length does not match token tuple length")
        if any(isinstance(token, bool) or not isinstance(token, int) for token in self.tokens):
            raise TypeError("Token n-gram must contain only integer token IDs")
        if any(token < 0 for token in self.tokens):
            raise ValueError("Token n-gram must contain only non-negative token IDs")


class StructuralObservationState(str, Enum):
    PRESERVED = "preserved"
    REPLACED = "replaced"
    UNMAPPED = "unmapped"


@dataclass(frozen=True, slots=True)
class StructuralObservationDiff:
    original_index: int
    transformed_index: int | None
    state: StructuralObservationState

    def __post_init__(self) -> None:
        require_int("original_index", self.original_index)
        if self.transformed_index is not None:
            require_int("transformed_index", self.transformed_index)
        if not isinstance(self.state, StructuralObservationState):
            raise TypeError("state must be a StructuralObservationState")
        if self.original_index < 0:
            raise ValueError("Original observation index must be non-negative")
        if self.transformed_index is not None and self.transformed_index < 0:
            raise ValueError("Transformed observation index must be non-negative")
        if self.state in (StructuralObservationState.PRESERVED, StructuralObservationState.REPLACED):
            if self.transformed_index is None:
                raise ValueError("Mapped observations require a transformed index")
        if self.state is StructuralObservationState.UNMAPPED and self.transformed_index is not None:
            raise ValueError("Unmapped observations cannot have a transformed index")


@dataclass(frozen=True, slots=True)
class StructuralObservationSummary:
    original_count: int
    transformed_count: int
    preserved_count: int
    replaced_count: int
    unmapped_count: int

    def __post_init__(self) -> None:
        values = (
            ("original_count", self.original_count),
            ("transformed_count", self.transformed_count),
            ("preserved_count", self.preserved_count),
            ("replaced_count", self.replaced_count),
            ("unmapped_count", self.unmapped_count),
        )
        for name, value in values:
            require_int(name, value)
            if value < 0:
                raise ValueError("Structural observation counts must be non-negative")
        if self.preserved_count + self.replaced_count + self.unmapped_count != self.original_count:
            raise ValueError("Structural observation state counts must sum to original_count")
        if self.preserved_count + self.replaced_count > self.transformed_count:
            raise ValueError("Mapped structural observation counts cannot exceed transformed_count")

    @property
    def preservation_ratio(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.preserved_count / self.original_count

    @property
    def replacement_ratio(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.replaced_count / self.original_count

    @property
    def unmapped_ratio(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.unmapped_count / self.original_count


def build_token_ngrams(tokens: Sequence[int], ngram_len: int) -> tuple[TokenNgram, ...]:
    validate_token_sequence("tokens", tokens)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if len(tokens) < ngram_len:
        return ()
    return tuple(
        TokenNgram(
            index=start,
            start=start,
            end_exclusive=start + ngram_len,
            tokens=tuple(tokens[start : start + ngram_len]),
        )
        for start in range(len(tokens) - ngram_len + 1)
    )


def structural_observation_diff(
    original: Sequence[int],
    transformed: Sequence[int],
    ngram_len: int,
    alignment: AlignmentResult,
) -> tuple[StructuralObservationDiff, ...]:
    validate_alignment(original, transformed, alignment)
    original_ngrams = build_token_ngrams(original, ngram_len)
    transformed_ngrams = build_token_ngrams(transformed, ngram_len)
    transformed_lookup = {ngram.start: ngram for ngram in transformed_ngrams}
    output: list[StructuralObservationDiff] = []

    for ngram in original_ngrams:
        matched = alignment.original_to_transformed[ngram.start : ngram.end_exclusive]
        if all(index is not None for index in matched):
            matched_indices = tuple(int(index) for index in matched)
            matched_start = matched_indices[0]
            matched_contiguous = all(
                matched_indices[offset] == matched_start + offset
                for offset in range(len(matched_indices))
            )
            if matched_contiguous:
                transformed_ngram = transformed_lookup.get(matched_start)
                if transformed_ngram is not None and transformed_ngram.tokens == ngram.tokens:
                    output.append(
                        StructuralObservationDiff(
                            original_index=ngram.index,
                            transformed_index=transformed_ngram.index,
                            state=StructuralObservationState.PRESERVED,
                        )
                    )
                    continue

        aligned = alignment.original_to_transformed_aligned[ngram.start : ngram.end_exclusive]
        if all(index is not None for index in aligned):
            aligned_indices = tuple(int(index) for index in aligned)
            aligned_start = aligned_indices[0]
            aligned_contiguous = all(
                aligned_indices[offset] == aligned_start + offset
                for offset in range(len(aligned_indices))
            )
            if aligned_contiguous:
                transformed_ngram = transformed_lookup.get(aligned_start)
                if transformed_ngram is not None:
                    output.append(
                        StructuralObservationDiff(
                            original_index=ngram.index,
                            transformed_index=transformed_ngram.index,
                            state=StructuralObservationState.REPLACED,
                        )
                    )
                    continue

        output.append(
            StructuralObservationDiff(
                original_index=ngram.index,
                transformed_index=None,
                state=StructuralObservationState.UNMAPPED,
            )
        )

    return tuple(output)


def summarize_structural_observations(
    original: Sequence[int],
    transformed: Sequence[int],
    ngram_len: int,
    diffs: Sequence[StructuralObservationDiff],
) -> StructuralObservationSummary:
    validate_token_sequence("original", original)
    validate_token_sequence("transformed", transformed)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    if not isinstance(diffs, Sequence) or isinstance(diffs, (str, bytes, bytearray)):
        raise TypeError("diffs must be a sequence of StructuralObservationDiff values")
    if any(not isinstance(diff, StructuralObservationDiff) for diff in diffs):
        raise TypeError("diffs must contain only StructuralObservationDiff values")
    original_count = max(0, len(original) - ngram_len + 1)
    transformed_count = max(0, len(transformed) - ngram_len + 1)
    if len(diffs) != original_count:
        raise ValueError("Structural observation diff count does not match original observation count")
    expected_indices = tuple(range(original_count))
    actual_indices = tuple(diff.original_index for diff in diffs)
    if actual_indices != expected_indices:
        raise ValueError("Structural observation diffs must contain every original index exactly once in order")
    original_ngrams = build_token_ngrams(original, ngram_len)
    transformed_ngrams = build_token_ngrams(transformed, ngram_len)
    mapped_indices: list[int] = []
    for diff in diffs:
        if diff.transformed_index is None:
            continue
        if diff.transformed_index >= transformed_count:
            raise ValueError("Structural observation diff references an out-of-range transformed index")
        mapped_indices.append(diff.transformed_index)
        original_tokens = original_ngrams[diff.original_index].tokens
        transformed_tokens = transformed_ngrams[diff.transformed_index].tokens
        if diff.state is StructuralObservationState.PRESERVED and original_tokens != transformed_tokens:
            raise ValueError("Preserved structural observations must contain identical token n-grams")
        if diff.state is StructuralObservationState.REPLACED and original_tokens == transformed_tokens:
            raise ValueError("Replaced structural observations must contain different token n-grams")
    if mapped_indices != sorted(set(mapped_indices)):
        raise ValueError("Mapped transformed observation indices must be unique and strictly increasing")
    preserved_count = sum(diff.state is StructuralObservationState.PRESERVED for diff in diffs)
    replaced_count = sum(diff.state is StructuralObservationState.REPLACED for diff in diffs)
    unmapped_count = sum(diff.state is StructuralObservationState.UNMAPPED for diff in diffs)
    return StructuralObservationSummary(
        original_count=original_count,
        transformed_count=transformed_count,
        preserved_count=preserved_count,
        replaced_count=replaced_count,
        unmapped_count=unmapped_count,
    )
