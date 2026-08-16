from __future__ import annotations

from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from ._validation import normalize_token_sequence, require_int


DEFAULT_MAX_ALIGNMENT_CELLS = 4_500_000
DEFAULT_MAX_ALIGNMENT_STEPS = 100_000
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
                if value < 0:
                    raise ValueError(f"{name} must be non-negative")
        if self.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if self.original_index is None or self.transformed_index is None:
                raise ValueError("Diagonal alignment steps require both indices")
            if self.original_token is None or self.transformed_token is None:
                raise ValueError("Diagonal alignment steps require both tokens")
            if self.op is AlignmentOp.MATCH and self.original_token != self.transformed_token:
                raise ValueError("Match steps require equal token values")
            if self.op is AlignmentOp.SUBSTITUTE and self.original_token == self.transformed_token:
                raise ValueError("Substitution steps require unequal token values")
            return
        if self.op is AlignmentOp.DELETE:
            if self.original_index is None or self.original_token is None:
                raise ValueError("Deletion steps require an original index and token")
            if self.transformed_index is not None or self.transformed_token is not None:
                raise ValueError("Deletion steps cannot contain transformed values")
            return
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
        _validate_result_structure(self)


def _choice(equal: bool, diagonal: int, delete: int, insert: int) -> tuple[int, int, int]:
    best = min(diagonal, delete, insert)
    ties = int(diagonal == best) + int(delete == best) + int(insert == best) - 1
    if diagonal == best:
        parent = _PARENT_MATCH if equal else _PARENT_SUBSTITUTE
    elif delete == best:
        parent = _PARENT_DELETE
    else:
        parent = _PARENT_INSERT
    return best, parent, ties


def _maps_from_steps(
    steps: tuple[AlignmentStep, ...],
    original_count: int,
    transformed_count: int,
) -> tuple[
    tuple[int | None, ...],
    tuple[int | None, ...],
    tuple[int | None, ...],
    tuple[int | None, ...],
    int,
]:
    matched_original: list[int | None] = [None] * original_count
    matched_transformed: list[int | None] = [None] * transformed_count
    aligned_original: list[int | None] = [None] * original_count
    aligned_transformed: list[int | None] = [None] * transformed_count
    i = 0
    j = 0
    edits = 0
    for step in steps:
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if i >= original_count or j >= transformed_count:
                raise ValueError("Diagonal alignment step exceeds alignment map bounds")
            if step.original_index != i or step.transformed_index != j:
                raise ValueError("Diagonal alignment step indices are not sequential")
            aligned_original[i] = j
            aligned_transformed[j] = i
            if step.op is AlignmentOp.MATCH:
                matched_original[i] = j
                matched_transformed[j] = i
            else:
                edits += 1
            i += 1
            j += 1
        elif step.op is AlignmentOp.DELETE:
            if i >= original_count or step.original_index != i:
                raise ValueError("Deletion alignment step index is invalid")
            i += 1
            edits += 1
        else:
            if j >= transformed_count or step.transformed_index != j:
                raise ValueError("Insertion alignment step index is invalid")
            j += 1
            edits += 1
    if i != original_count or j != transformed_count:
        raise ValueError("Alignment steps do not consume the declared map lengths")
    return (
        tuple(matched_original),
        tuple(matched_transformed),
        tuple(aligned_original),
        tuple(aligned_transformed),
        edits,
    )


def _validate_result_structure(alignment: AlignmentResult) -> None:
    original_count = len(alignment.original_to_transformed)
    transformed_count = len(alignment.transformed_to_original)
    if len(alignment.original_to_transformed_aligned) != original_count:
        raise ValueError("Alignment original maps must have equal lengths")
    if len(alignment.transformed_to_original_aligned) != transformed_count:
        raise ValueError("Alignment transformed maps must have equal lengths")
    maps = _maps_from_steps(alignment.steps, original_count, transformed_count)
    expected = (
        alignment.original_to_transformed,
        alignment.transformed_to_original,
        alignment.original_to_transformed_aligned,
        alignment.transformed_to_original_aligned,
    )
    if maps[:4] != expected:
        raise ValueError("Alignment maps are inconsistent with steps")
    if maps[4] != alignment.distance:
        raise ValueError("Alignment step edit count does not match distance")


def _validate_tokens(
    original: tuple[int, ...],
    transformed: tuple[int, ...],
    alignment: AlignmentResult,
) -> None:
    if len(alignment.original_to_transformed) != len(original):
        raise ValueError("Alignment original map length does not match original sequence")
    if len(alignment.transformed_to_original) != len(transformed):
        raise ValueError("Alignment transformed map length does not match transformed sequence")
    i = 0
    j = 0
    for step in alignment.steps:
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            if step.original_token != original[i] or step.transformed_token != transformed[j]:
                raise ValueError("Alignment diagonal token payload does not match input sequences")
            if (step.op is AlignmentOp.MATCH) != (original[i] == transformed[j]):
                raise ValueError("Alignment diagonal operation does not match token equality")
            i += 1
            j += 1
        elif step.op is AlignmentOp.DELETE:
            if step.original_token != original[i]:
                raise ValueError("Alignment deletion token payload does not match original sequence")
            i += 1
        else:
            if step.transformed_token != transformed[j]:
                raise ValueError("Alignment insertion token payload does not match transformed sequence")
            j += 1


def _parent_code(step: AlignmentStep) -> int:
    if step.op is AlignmentOp.MATCH:
        return _PARENT_MATCH
    if step.op is AlignmentOp.SUBSTITUTE:
        return _PARENT_SUBSTITUTE
    if step.op is AlignmentOp.DELETE:
        return _PARENT_DELETE
    return _PARENT_INSERT


def _canonical_path_codes(alignment: AlignmentResult, n: int, m: int) -> dict[tuple[int, int], int]:
    path: dict[tuple[int, int], int] = {}
    i = n
    j = m
    for step in reversed(alignment.steps):
        path[(i, j)] = _parent_code(step)
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE):
            i -= 1
            j -= 1
        elif step.op is AlignmentOp.DELETE:
            i -= 1
        else:
            j -= 1
    if i != 0 or j != 0:
        raise ValueError("Alignment traceback does not terminate at the origin")
    return path


def _validate_canonical(
    original: tuple[int, ...],
    transformed: tuple[int, ...],
    alignment: AlignmentResult,
    max_cells: int,
    max_steps: int,
) -> None:
    n = len(original)
    m = len(transformed)
    if len(alignment.steps) > max_steps:
        raise ValueError(f"Alignment traceback exceeds max_steps={max_steps}")
    cells = (n + 1) * (m + 1)
    if cells > max_cells:
        raise ValueError(
            f"Canonical alignment validation requires {cells} cells, exceeding max_cells={max_cells}"
        )
    path = _canonical_path_codes(alignment, n, m)
    for j in range(1, m + 1):
        if path.get((0, j), _PARENT_INSERT) != _PARENT_INSERT:
            raise ValueError("Alignment is not the canonical deterministic alignment")
    for i in range(1, n + 1):
        if path.get((i, 0), _PARENT_DELETE) != _PARENT_DELETE:
            raise ValueError("Alignment is not the canonical deterministic alignment")
    previous = array("I", range(m + 1))
    current = array("I", [0]) * (m + 1)
    ambiguous_ties = 0
    for i in range(1, n + 1):
        current[0] = i
        for j in range(1, m + 1):
            equal = original[i - 1] == transformed[j - 1]
            best, parent, ties = _choice(
                equal,
                previous[j - 1] + (0 if equal else 1),
                previous[j] + 1,
                current[j - 1] + 1,
            )
            current[j] = best
            supplied = path.get((i, j))
            if supplied is not None:
                if supplied != parent:
                    raise ValueError("Alignment is not the canonical deterministic alignment")
                ambiguous_ties += ties
        previous, current = current, previous
    if int(previous[m]) != alignment.distance:
        raise ValueError("Alignment distance is not the minimum edit distance")
    if ambiguous_ties != alignment.ambiguous_ties:
        raise ValueError("Alignment ambiguous_ties does not match the canonical traceback")


def align_tokens(
    original: Sequence[int],
    transformed: Sequence[int],
    max_cells: int = DEFAULT_MAX_ALIGNMENT_CELLS,
    max_steps: int = DEFAULT_MAX_ALIGNMENT_STEPS,
) -> AlignmentResult:
    require_int("max_cells", max_cells)
    require_int("max_steps", max_steps)
    if max_cells <= 0:
        raise ValueError("max_cells must be a positive integer")
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    original_tokens = normalize_token_sequence("original", original)
    transformed_tokens = normalize_token_sequence("transformed", transformed)
    n = len(original_tokens)
    m = len(transformed_tokens)
    if max(n, m) > max_steps:
        raise ValueError(
            f"Alignment requires at least {max(n, m)} traceback steps, exceeding max_steps={max_steps}"
        )
    columns = m + 1
    cells = (n + 1) * columns
    if cells > max_cells:
        raise ValueError(f"Alignment requires {cells} dynamic-programming cells, exceeding max_cells={max_cells}")
    parent = bytearray(cells)
    ties = bytearray(cells)
    for i in range(1, n + 1):
        parent[i * columns] = _PARENT_DELETE
    for j in range(1, m + 1):
        parent[j] = _PARENT_INSERT
    previous = array("I", range(columns))
    current = array("I", [0]) * columns
    for i in range(1, n + 1):
        current[0] = i
        row = i * columns
        for j in range(1, m + 1):
            equal = original_tokens[i - 1] == transformed_tokens[j - 1]
            best, code, tie_count = _choice(
                equal,
                previous[j - 1] + (0 if equal else 1),
                previous[j] + 1,
                current[j - 1] + 1,
            )
            current[j] = best
            parent[row + j] = code
            ties[row + j] = tie_count
        previous, current = current, previous
    distance = int(previous[m])
    i = n
    j = m
    step_count = 0
    ambiguous_ties = 0
    while i or j:
        position = i * columns + j
        code = parent[position]
        step_count += 1
        if step_count > max_steps:
            raise ValueError(f"Alignment traceback exceeds max_steps={max_steps}")
        ambiguous_ties += ties[position]
        if code in (_PARENT_MATCH, _PARENT_SUBSTITUTE):
            i -= 1
            j -= 1
        elif code == _PARENT_DELETE:
            i -= 1
        elif code == _PARENT_INSERT:
            j -= 1
        else:
            raise RuntimeError("Alignment traceback reached an invalid state")
    reversed_steps: list[AlignmentStep] = []
    i = n
    j = m
    while i or j:
        code = parent[i * columns + j]
        if code == _PARENT_MATCH:
            reversed_steps.append(AlignmentStep(AlignmentOp.MATCH, i - 1, j - 1, original_tokens[i - 1], transformed_tokens[j - 1]))
            i -= 1
            j -= 1
        elif code == _PARENT_SUBSTITUTE:
            reversed_steps.append(AlignmentStep(AlignmentOp.SUBSTITUTE, i - 1, j - 1, original_tokens[i - 1], transformed_tokens[j - 1]))
            i -= 1
            j -= 1
        elif code == _PARENT_DELETE:
            reversed_steps.append(AlignmentStep(AlignmentOp.DELETE, i - 1, None, original_tokens[i - 1], None))
            i -= 1
        elif code == _PARENT_INSERT:
            reversed_steps.append(AlignmentStep(AlignmentOp.INSERT, None, j - 1, None, transformed_tokens[j - 1]))
            j -= 1
        else:
            raise RuntimeError("Alignment traceback reached an invalid state")
    steps = tuple(reversed(reversed_steps))
    maps = _maps_from_steps(steps, n, m)
    return AlignmentResult(distance, steps, maps[0], maps[1], maps[2], maps[3], ambiguous_ties)


def validate_alignment(
    original: Sequence[int],
    transformed: Sequence[int],
    alignment: AlignmentResult,
    max_cells: int = DEFAULT_MAX_ALIGNMENT_CELLS,
    max_steps: int = DEFAULT_MAX_ALIGNMENT_STEPS,
) -> None:
    require_int("max_cells", max_cells)
    require_int("max_steps", max_steps)
    if max_cells <= 0:
        raise ValueError("max_cells must be a positive integer")
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    original_tokens = normalize_token_sequence("original", original)
    transformed_tokens = normalize_token_sequence("transformed", transformed)
    _validate_tokens(original_tokens, transformed_tokens, alignment)
    _validate_canonical(original_tokens, transformed_tokens, alignment, max_cells, max_steps)


def conserved_runs(alignment: AlignmentResult) -> tuple[tuple[int, int, int, int], ...]:
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    runs: list[tuple[int, int, int, int]] = []
    start_original: int | None = None
    start_transformed: int | None = None
    previous_original: int | None = None
    previous_transformed: int | None = None
    for step in (*alignment.steps, None):
        if step is not None and step.op is AlignmentOp.MATCH:
            if step.original_index is None or step.transformed_index is None:
                raise RuntimeError("Match step must have two indices")
            contiguous = (
                previous_original is not None
                and previous_transformed is not None
                and step.original_index == previous_original + 1
                and step.transformed_index == previous_transformed + 1
            )
            if start_original is None or not contiguous:
                if start_original is not None:
                    runs.append((start_original, previous_original + 1, start_transformed, previous_transformed + 1))
                start_original = step.original_index
                start_transformed = step.transformed_index
            previous_original = step.original_index
            previous_transformed = step.transformed_index
            continue
        if start_original is not None:
            if previous_original is None or previous_transformed is None or start_transformed is None:
                raise RuntimeError("Conserved run state is inconsistent")
            runs.append((start_original, previous_original + 1, start_transformed, previous_transformed + 1))
        start_original = None
        start_transformed = None
        previous_original = None
        previous_transformed = None
    return tuple(runs)
