from __future__ import annotations

from array import array
from dataclasses import dataclass
from enum import Enum
from collections.abc import Sequence

from ._validation import require_int, validate_token_sequence


DEFAULT_MAX_ALIGNMENT_CELLS = 4_500_000
_PARENT_MATCH = 1
_PARENT_SUBSTITUTE = 2
_PARENT_DELETE = 3
_PARENT_INSERT = 4


class AlignmentOp(str, Enum):
    MATCH = "match"
    SUBSTITUTE = "substitute"
    DELETE = "delete"
    INSERT = "insert"


@dataclass(frozen=True, slots=True)
class AlignmentStep:
    op: AlignmentOp
    original_index: int | None
    transformed_index: int | None
    original_token: int | None
    transformed_token: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.op, AlignmentOp):
            raise TypeError("op must be an AlignmentOp")
        for name, value in (
            ("original_index", self.original_index),
            ("transformed_index", self.transformed_index),
            ("original_token", self.original_token),
            ("transformed_token", self.transformed_token),
        ):
            if value is not None:
                require_int(name, value)
        if self.original_index is not None and self.original_index < 0:
            raise ValueError("original_index must be non-negative")
        if self.transformed_index is not None and self.transformed_index < 0:
            raise ValueError("transformed_index must be non-negative")
        if self.original_token is not None and self.original_token < 0:
            raise ValueError("original_token must be non-negative")
        if self.transformed_token is not None and self.transformed_token < 0:
            raise ValueError("transformed_token must be non-negative")
        if self.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if self.original_index is None or self.transformed_index is None:
                raise ValueError("Diagonal alignment steps require both indices")
            if self.original_token is None or self.transformed_token is None:
                raise ValueError("Diagonal alignment steps require both tokens")
            if self.op is AlignmentOp.MATCH and self.original_token != self.transformed_token:
                raise ValueError("Match steps require equal token values")
            if self.op is AlignmentOp.SUBSTITUTE and self.original_token == self.transformed_token:
                raise ValueError("Substitution steps require unequal token values")
        elif self.op is AlignmentOp.DELETE:
            if self.original_index is None or self.original_token is None:
                raise ValueError("Deletion steps require an original index and token")
            if self.transformed_index is not None or self.transformed_token is not None:
                raise ValueError("Deletion steps cannot contain transformed values")
        elif self.op is AlignmentOp.INSERT:
            if self.transformed_index is None or self.transformed_token is None:
                raise ValueError("Insertion steps require a transformed index and token")
            if self.original_index is not None or self.original_token is not None:
                raise ValueError("Insertion steps cannot contain original values")


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    distance: int
    steps: tuple[AlignmentStep, ...]
    original_to_transformed: tuple[int | None, ...]
    transformed_to_original: tuple[int | None, ...]
    original_to_transformed_aligned: tuple[int | None, ...]
    transformed_to_original_aligned: tuple[int | None, ...]
    ambiguous_ties: int

    def __post_init__(self) -> None:
        require_int("distance", self.distance)
        require_int("ambiguous_ties", self.ambiguous_ties)
        if self.distance < 0:
            raise ValueError("distance must be non-negative")
        if self.ambiguous_ties < 0:
            raise ValueError("ambiguous_ties must be non-negative")
        if not isinstance(self.steps, tuple) or any(not isinstance(step, AlignmentStep) for step in self.steps):
            raise TypeError("steps must be a tuple of AlignmentStep values")
        for name, values in (
            ("original_to_transformed", self.original_to_transformed),
            ("transformed_to_original", self.transformed_to_original),
            ("original_to_transformed_aligned", self.original_to_transformed_aligned),
            ("transformed_to_original_aligned", self.transformed_to_original_aligned),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            for value in values:
                if value is not None:
                    require_int(name, value)
                    if value < 0:
                        raise ValueError(f"{name} cannot contain negative indices")
        _validate_alignment_result_structure(self)


def _validate_alignment_result_structure(alignment: AlignmentResult) -> None:
    original_count = len(alignment.original_to_transformed)
    transformed_count = len(alignment.transformed_to_original)
    if len(alignment.original_to_transformed_aligned) != original_count:
        raise ValueError("Alignment original maps must have equal lengths")
    if len(alignment.transformed_to_original_aligned) != transformed_count:
        raise ValueError("Alignment transformed maps must have equal lengths")

    next_original = 0
    next_transformed = 0
    edits = 0
    match_original: list[int | None] = [None] * original_count
    match_transformed: list[int | None] = [None] * transformed_count
    aligned_original: list[int | None] = [None] * original_count
    aligned_transformed: list[int | None] = [None] * transformed_count

    for step in alignment.steps:
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if step.original_index != next_original or step.transformed_index != next_transformed:
                raise ValueError("Diagonal alignment step indices are not sequential")
            if next_original >= original_count or next_transformed >= transformed_count:
                raise ValueError("Diagonal alignment step exceeds alignment map bounds")
            aligned_original[next_original] = next_transformed
            aligned_transformed[next_transformed] = next_original
            if step.op is AlignmentOp.MATCH:
                match_original[next_original] = next_transformed
                match_transformed[next_transformed] = next_original
            else:
                edits += 1
            next_original += 1
            next_transformed += 1
        elif step.op is AlignmentOp.DELETE:
            if step.original_index != next_original:
                raise ValueError("Deletion alignment step index is not sequential")
            if next_original >= original_count:
                raise ValueError("Deletion alignment step exceeds original map bounds")
            next_original += 1
            edits += 1
        elif step.op is AlignmentOp.INSERT:
            if step.transformed_index != next_transformed:
                raise ValueError("Insertion alignment step index is not sequential")
            if next_transformed >= transformed_count:
                raise ValueError("Insertion alignment step exceeds transformed map bounds")
            next_transformed += 1
            edits += 1

    if next_original != original_count or next_transformed != transformed_count:
        raise ValueError("Alignment steps do not consume the declared map lengths")
    if edits != alignment.distance:
        raise ValueError("Alignment step edit count does not match distance")
    if tuple(match_original) != alignment.original_to_transformed:
        raise ValueError("Alignment original match map is inconsistent with steps")
    if tuple(match_transformed) != alignment.transformed_to_original:
        raise ValueError("Alignment transformed match map is inconsistent with steps")
    if tuple(aligned_original) != alignment.original_to_transformed_aligned:
        raise ValueError("Alignment original positional map is inconsistent with steps")
    if tuple(aligned_transformed) != alignment.transformed_to_original_aligned:
        raise ValueError("Alignment transformed positional map is inconsistent with steps")


def align_tokens(
    original: Sequence[int],
    transformed: Sequence[int],
    max_cells: int = DEFAULT_MAX_ALIGNMENT_CELLS,
) -> AlignmentResult:
    require_int("max_cells", max_cells)
    if max_cells <= 0:
        raise ValueError("max_cells must be a positive integer")
    validate_token_sequence("original", original)
    validate_token_sequence("transformed", transformed)

    n = len(original)
    m = len(transformed)
    columns = m + 1
    cell_count = (n + 1) * columns
    if cell_count > max_cells:
        raise ValueError(
            f"Alignment requires {cell_count} dynamic-programming cells, exceeding max_cells={max_cells}"
        )

    parent = bytearray(cell_count)
    ties = bytearray(cell_count)
    for i in range(1, n + 1):
        parent[i * columns] = _PARENT_DELETE
    for j in range(1, m + 1):
        parent[j] = _PARENT_INSERT

    previous = array("I", range(columns))
    current = array("I", [0]) * columns

    for i in range(1, n + 1):
        current[0] = i
        original_token = original[i - 1]
        row_offset = i * columns
        for j in range(1, m + 1):
            equal = original_token == transformed[j - 1]
            diagonal_cost = previous[j - 1] + (0 if equal else 1)
            delete_cost = previous[j] + 1
            insert_cost = current[j - 1] + 1
            best_cost = min(diagonal_cost, delete_cost, insert_cost)
            current[j] = best_cost
            ties[row_offset + j] = (
                int(diagonal_cost == best_cost)
                + int(delete_cost == best_cost)
                + int(insert_cost == best_cost)
                - 1
            )
            if diagonal_cost == best_cost:
                parent[row_offset + j] = _PARENT_MATCH if equal else _PARENT_SUBSTITUTE
            elif delete_cost == best_cost:
                parent[row_offset + j] = _PARENT_DELETE
            else:
                parent[row_offset + j] = _PARENT_INSERT
        previous, current = current, previous

    final_distance = previous[m]
    i = n
    j = m
    reversed_steps: list[AlignmentStep] = []
    ambiguous_ties = 0

    while i > 0 or j > 0:
        position = i * columns + j
        code = parent[position]
        ambiguous_ties += ties[position]
        if code == _PARENT_MATCH:
            reversed_steps.append(
                AlignmentStep(AlignmentOp.MATCH, i - 1, j - 1, original[i - 1], transformed[j - 1])
            )
            i -= 1
            j -= 1
        elif code == _PARENT_SUBSTITUTE:
            reversed_steps.append(
                AlignmentStep(AlignmentOp.SUBSTITUTE, i - 1, j - 1, original[i - 1], transformed[j - 1])
            )
            i -= 1
            j -= 1
        elif code == _PARENT_DELETE:
            reversed_steps.append(AlignmentStep(AlignmentOp.DELETE, i - 1, None, original[i - 1], None))
            i -= 1
        elif code == _PARENT_INSERT:
            reversed_steps.append(AlignmentStep(AlignmentOp.INSERT, None, j - 1, None, transformed[j - 1]))
            j -= 1
        else:
            raise RuntimeError("Alignment traceback reached an invalid state")

    steps = tuple(reversed(reversed_steps))
    original_to_transformed: list[int | None] = [None] * n
    transformed_to_original: list[int | None] = [None] * m
    original_to_transformed_aligned: list[int | None] = [None] * n
    transformed_to_original_aligned: list[int | None] = [None] * m

    for step in steps:
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if step.original_index is None or step.transformed_index is None:
                raise RuntimeError("Diagonal alignment step must have two indices")
            original_to_transformed_aligned[step.original_index] = step.transformed_index
            transformed_to_original_aligned[step.transformed_index] = step.original_index
        if step.op is AlignmentOp.MATCH:
            if step.original_index is None or step.transformed_index is None:
                raise RuntimeError("Match step must have two indices")
            original_to_transformed[step.original_index] = step.transformed_index
            transformed_to_original[step.transformed_index] = step.original_index

    result = AlignmentResult(
        distance=int(final_distance),
        steps=steps,
        original_to_transformed=tuple(original_to_transformed),
        transformed_to_original=tuple(transformed_to_original),
        original_to_transformed_aligned=tuple(original_to_transformed_aligned),
        transformed_to_original_aligned=tuple(transformed_to_original_aligned),
        ambiguous_ties=ambiguous_ties,
    )
    validate_alignment(original, transformed, result)
    return result


def validate_alignment(
    original: Sequence[int],
    transformed: Sequence[int],
    alignment: AlignmentResult,
) -> None:
    validate_token_sequence("original", original)
    validate_token_sequence("transformed", transformed)
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    if len(alignment.original_to_transformed) != len(original):
        raise ValueError("Alignment original match map length does not match original sequence")
    if len(alignment.transformed_to_original) != len(transformed):
        raise ValueError("Alignment transformed match map length does not match transformed sequence")
    if len(alignment.original_to_transformed_aligned) != len(original):
        raise ValueError("Alignment original positional map length does not match original sequence")
    if len(alignment.transformed_to_original_aligned) != len(transformed):
        raise ValueError("Alignment transformed positional map length does not match transformed sequence")

    next_original = 0
    next_transformed = 0
    edits = 0
    match_original: list[int | None] = [None] * len(original)
    match_transformed: list[int | None] = [None] * len(transformed)
    aligned_original: list[int | None] = [None] * len(original)
    aligned_transformed: list[int | None] = [None] * len(transformed)

    for step in alignment.steps:
        if step.op is AlignmentOp.MATCH:
            if next_original >= len(original) or next_transformed >= len(transformed):
                raise ValueError("Alignment match exceeds input sequence bounds")
            if step.original_index != next_original or step.transformed_index != next_transformed:
                raise ValueError("Alignment match indices are not sequential")
            if step.original_token != original[next_original] or step.transformed_token != transformed[next_transformed]:
                raise ValueError("Alignment match token payload does not match input sequences")
            if original[next_original] != transformed[next_transformed]:
                raise ValueError("Alignment match contains unequal tokens")
            match_original[next_original] = next_transformed
            match_transformed[next_transformed] = next_original
            aligned_original[next_original] = next_transformed
            aligned_transformed[next_transformed] = next_original
            next_original += 1
            next_transformed += 1
        elif step.op is AlignmentOp.SUBSTITUTE:
            if next_original >= len(original) or next_transformed >= len(transformed):
                raise ValueError("Alignment substitution exceeds input sequence bounds")
            if step.original_index != next_original or step.transformed_index != next_transformed:
                raise ValueError("Alignment substitution indices are not sequential")
            if step.original_token != original[next_original] or step.transformed_token != transformed[next_transformed]:
                raise ValueError("Alignment substitution token payload does not match input sequences")
            if original[next_original] == transformed[next_transformed]:
                raise ValueError("Alignment substitution contains equal tokens")
            aligned_original[next_original] = next_transformed
            aligned_transformed[next_transformed] = next_original
            next_original += 1
            next_transformed += 1
            edits += 1
        elif step.op is AlignmentOp.DELETE:
            if next_original >= len(original):
                raise ValueError("Alignment deletion exceeds original sequence bounds")
            if step.original_index != next_original or step.transformed_index is not None:
                raise ValueError("Alignment deletion indices are invalid")
            if step.original_token != original[next_original] or step.transformed_token is not None:
                raise ValueError("Alignment deletion token payload is invalid")
            next_original += 1
            edits += 1
        elif step.op is AlignmentOp.INSERT:
            if next_transformed >= len(transformed):
                raise ValueError("Alignment insertion exceeds transformed sequence bounds")
            if step.original_index is not None or step.transformed_index != next_transformed:
                raise ValueError("Alignment insertion indices are invalid")
            if step.original_token is not None or step.transformed_token != transformed[next_transformed]:
                raise ValueError("Alignment insertion token payload is invalid")
            next_transformed += 1
            edits += 1
        else:
            raise ValueError("Alignment contains an unknown operation")

    if next_original != len(original) or next_transformed != len(transformed):
        raise ValueError("Alignment does not consume both input sequences")
    if edits != alignment.distance:
        raise ValueError("Alignment edit count does not match distance")
    if tuple(match_original) != alignment.original_to_transformed:
        raise ValueError("Alignment original match map is inconsistent with steps")
    if tuple(match_transformed) != alignment.transformed_to_original:
        raise ValueError("Alignment transformed match map is inconsistent with steps")
    if tuple(aligned_original) != alignment.original_to_transformed_aligned:
        raise ValueError("Alignment original positional map is inconsistent with steps")
    if tuple(aligned_transformed) != alignment.transformed_to_original_aligned:
        raise ValueError("Alignment transformed positional map is inconsistent with steps")


def conserved_runs(alignment: AlignmentResult) -> tuple[tuple[int, int, int, int], ...]:
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    runs: list[tuple[int, int, int, int]] = []
    run_original_start: int | None = None
    run_transformed_start: int | None = None
    previous_original: int | None = None
    previous_transformed: int | None = None

    def close_run() -> None:
        nonlocal run_original_start, run_transformed_start, previous_original, previous_transformed
        if run_original_start is not None and run_transformed_start is not None:
            if previous_original is None or previous_transformed is None:
                raise RuntimeError("Conserved run state is inconsistent")
            runs.append(
                (
                    run_original_start,
                    previous_original + 1,
                    run_transformed_start,
                    previous_transformed + 1,
                )
            )
        run_original_start = None
        run_transformed_start = None
        previous_original = None
        previous_transformed = None

    for step in alignment.steps:
        if step.op is not AlignmentOp.MATCH:
            close_run()
            continue
        if step.original_index is None or step.transformed_index is None:
            raise RuntimeError("Match step must have two indices")
        contiguous = (
            previous_original is not None
            and previous_transformed is not None
            and step.original_index == previous_original + 1
            and step.transformed_index == previous_transformed + 1
        )
        if run_original_start is None or not contiguous:
            close_run()
            run_original_start = step.original_index
            run_transformed_start = step.transformed_index
        previous_original = step.original_index
        previous_transformed = step.transformed_index

    close_run()
    return tuple(runs)
