from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import normalize_token_sequence, require_bool, require_clean_string, require_int, require_sha256
from ..adapters import WatermarkAdapter
from ..alignment import AlignmentOp, AlignmentResult, align_tokens, conserved_runs, validate_alignment
from ..coverage import substitution_observation_interval
from ..hashing import sha256_json
from ..observations import (
    StructuralObservationDiff,
    StructuralObservationState,
    StructuralObservationSummary,
    structural_observation_diff,
    summarize_structural_observations,
)
from .registry import DevelopmentExperimentId, default_development_experiment_registry


E03_ALGORITHM_VERSION = "e03-repetition-sensitivity-v1"
OBSERVATION_MECHANISM_ALGORITHM_VERSION = "e04-e06-observation-mechanisms-v1"


class MechanismStatus(str, Enum):
    PASS = "PASS"
    MISMATCH = "MISMATCH"


class MechanismInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E03RepetitionFixture:
    case_id: str
    adapter_id: str
    adapter_algorithm_version: str
    source_id: str
    source_commit: str
    adapter_config_hash: str
    ngram_len: int
    token_ids: tuple[int, ...]
    expected_context_mask: tuple[bool, ...]
    fixture_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("case_id", self.case_id),
            ("adapter_id", self.adapter_id),
            ("adapter_algorithm_version", self.adapter_algorithm_version),
            ("source_id", self.source_id),
        ):
            require_clean_string(name, value)
        require_sha256("source_commit", self.source_commit)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_int("ngram_len", self.ngram_len)
        if self.ngram_len <= 1:
            raise ValueError("ngram_len must be greater than one")
        tokens = normalize_token_sequence("token_ids", self.token_ids)
        if tokens != self.token_ids:
            raise ValueError("token_ids must be a canonical tuple")
        if not isinstance(self.expected_context_mask, tuple):
            raise TypeError("expected_context_mask must be a tuple")
        for value in self.expected_context_mask:
            require_bool("expected_context_mask value", value)
        expected_count = max(0, len(tokens) - self.ngram_len + 1)
        if len(self.expected_context_mask) != expected_count:
            raise ValueError("expected_context_mask length does not match fixture n-gram geometry")
        require_sha256("fixture_hash", self.fixture_hash)
        if self.fixture_hash != sha256_json(self._payload()):
            raise ValueError("fixture_hash does not match E03 repetition fixture")

    def _payload(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "adapter_config_hash": self.adapter_config_hash,
            "ngram_len": self.ngram_len,
            "token_ids": self.token_ids,
            "expected_context_mask": self.expected_context_mask,
        }

    @classmethod
    def create(
        cls,
        case_id: str,
        adapter: WatermarkAdapter,
        token_ids: tuple[int, ...],
        expected_context_mask: tuple[bool, ...],
    ) -> E03RepetitionFixture:
        if not isinstance(adapter, WatermarkAdapter):
            raise TypeError("adapter must satisfy WatermarkAdapter")
        tokens = normalize_token_sequence("token_ids", token_ids)
        mask = tuple(expected_context_mask)
        payload = {
            "case_id": case_id,
            "adapter_id": adapter.adapter_id,
            "adapter_algorithm_version": adapter.algorithm_version,
            "source_id": adapter.source_pin.source_id,
            "source_commit": adapter.source_pin.commit,
            "adapter_config_hash": adapter.configuration_fingerprint(),
            "ngram_len": adapter.ngram_len,
            "token_ids": tokens,
            "expected_context_mask": mask,
        }
        return cls(
            case_id,
            adapter.adapter_id,
            adapter.algorithm_version,
            adapter.source_pin.source_id,
            adapter.source_pin.commit,
            adapter.configuration_fingerprint(),
            adapter.ngram_len,
            tokens,
            mask,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E03RepetitionResult:
    algorithm_version: str
    experiment_definition_hash: str
    fixture_hash: str
    adapter_id: str
    adapter_algorithm_version: str
    source_commit: str
    adapter_config_hash: str
    expected_context_mask: tuple[bool, ...]
    actual_context_mask: tuple[bool, ...]
    observation_count: int
    masked_repetition_count: int
    masked_repetition_ratio: float
    status: MechanismStatus
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != E03_ALGORITHM_VERSION:
            raise ValueError("unsupported E03 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("fixture_hash", self.fixture_hash),
            ("source_commit", self.source_commit),
            ("adapter_config_hash", self.adapter_config_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        require_clean_string("adapter_id", self.adapter_id)
        require_clean_string("adapter_algorithm_version", self.adapter_algorithm_version)
        for name, mask in (
            ("expected_context_mask", self.expected_context_mask),
            ("actual_context_mask", self.actual_context_mask),
        ):
            if not isinstance(mask, tuple):
                raise TypeError(f"{name} must be a tuple")
            for value in mask:
                require_bool(f"{name} value", value)
        require_int("observation_count", self.observation_count)
        require_int("masked_repetition_count", self.masked_repetition_count)
        if self.observation_count != len(self.actual_context_mask):
            raise ValueError("observation_count does not match actual context mask")
        expected_masked = sum(not value for value in self.actual_context_mask)
        if self.masked_repetition_count != expected_masked:
            raise ValueError("masked_repetition_count does not match actual context mask")
        expected_ratio = 0.0 if self.observation_count == 0 else expected_masked / self.observation_count
        if isinstance(self.masked_repetition_ratio, bool) or not isinstance(self.masked_repetition_ratio, (int, float)):
            raise TypeError("masked_repetition_ratio must be a real number")
        ratio = float(self.masked_repetition_ratio)
        if not math.isfinite(ratio) or ratio != expected_ratio:
            raise ValueError("masked_repetition_ratio does not match actual context mask")
        object.__setattr__(self, "masked_repetition_ratio", ratio)
        if not isinstance(self.status, MechanismStatus):
            raise TypeError("status must be a MechanismStatus")
        expected_status = MechanismStatus.PASS if self.actual_context_mask == self.expected_context_mask else MechanismStatus.MISMATCH
        if self.status is not expected_status:
            raise ValueError("E03 status does not match expected versus actual context mask")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E03 repetition result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "fixture_hash": self.fixture_hash,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "source_commit": self.source_commit,
            "adapter_config_hash": self.adapter_config_hash,
            "expected_context_mask": self.expected_context_mask,
            "actual_context_mask": self.actual_context_mask,
            "observation_count": self.observation_count,
            "masked_repetition_count": self.masked_repetition_count,
            "masked_repetition_ratio": self.masked_repetition_ratio,
            "status": self.status.value,
        }


def run_e03_repetition_fixture(
    fixture: E03RepetitionFixture,
    adapter: WatermarkAdapter,
) -> E03RepetitionResult:
    if not isinstance(fixture, E03RepetitionFixture):
        raise TypeError("fixture must be an E03RepetitionFixture")
    if not isinstance(adapter, WatermarkAdapter):
        raise TypeError("adapter must satisfy WatermarkAdapter")
    identity = (
        adapter.adapter_id,
        adapter.algorithm_version,
        adapter.source_pin.source_id,
        adapter.source_pin.commit,
        adapter.configuration_fingerprint(),
        adapter.ngram_len,
    )
    expected_identity = (
        fixture.adapter_id,
        fixture.adapter_algorithm_version,
        fixture.source_id,
        fixture.source_commit,
        fixture.adapter_config_hash,
        fixture.ngram_len,
    )
    if identity != expected_identity:
        raise MechanismInputError("adapter identity or configuration does not match E03 fixture")
    actual = adapter.compute_context_repetition_mask(fixture.token_ids)
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E03)
    masked = sum(not value for value in actual)
    ratio = 0.0 if not actual else masked / len(actual)
    status = MechanismStatus.PASS if actual == fixture.expected_context_mask else MechanismStatus.MISMATCH
    payload = {
        "algorithm_version": E03_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "fixture_hash": fixture.fixture_hash,
        "adapter_id": adapter.adapter_id,
        "adapter_algorithm_version": adapter.algorithm_version,
        "source_commit": adapter.source_pin.commit,
        "adapter_config_hash": adapter.configuration_fingerprint(),
        "expected_context_mask": fixture.expected_context_mask,
        "actual_context_mask": actual,
        "observation_count": len(actual),
        "masked_repetition_count": masked,
        "masked_repetition_ratio": ratio,
        "status": status.value,
    }
    return E03RepetitionResult(
        E03_ALGORITHM_VERSION,
        definition.definition_hash,
        fixture.fixture_hash,
        adapter.adapter_id,
        adapter.algorithm_version,
        adapter.source_pin.commit,
        adapter.configuration_fingerprint(),
        fixture.expected_context_mask,
        actual,
        len(actual),
        masked,
        ratio,
        status,
        sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class ObservationMechanismResult:
    algorithm_version: str
    experiment_id: DevelopmentExperimentId
    experiment_definition_hash: str
    original_tokens: tuple[int, ...]
    transformed_tokens: tuple[int, ...]
    ngram_len: int
    edit_original_index: int | None
    edit_transformed_index: int | None
    alignment: AlignmentResult
    conserved_token_runs: tuple[tuple[int, int, int, int], ...]
    observation_diffs: tuple[StructuralObservationDiff, ...]
    observation_summary: StructuralObservationSummary
    expected_non_preserved_indices: tuple[int, ...]
    actual_non_preserved_indices: tuple[int, ...]
    suffix_expected_observation_count: int
    suffix_preserved_observation_count: int
    status: MechanismStatus
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != OBSERVATION_MECHANISM_ALGORITHM_VERSION:
            raise ValueError("unsupported observation mechanism algorithm version")
        if self.experiment_id not in (
            DevelopmentExperimentId.E04,
            DevelopmentExperimentId.E05,
            DevelopmentExperimentId.E06,
        ):
            raise ValueError("observation mechanism result must be E04, E05, or E06")
        require_sha256("experiment_definition_hash", self.experiment_definition_hash)
        original = normalize_token_sequence("original_tokens", self.original_tokens)
        transformed = normalize_token_sequence("transformed_tokens", self.transformed_tokens)
        if original != self.original_tokens or transformed != self.transformed_tokens:
            raise ValueError("mechanism token inputs must be canonical tuples")
        require_int("ngram_len", self.ngram_len)
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        for name, value in (
            ("edit_original_index", self.edit_original_index),
            ("edit_transformed_index", self.edit_transformed_index),
        ):
            if value is not None:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.alignment, AlignmentResult):
            raise TypeError("alignment must be an AlignmentResult")
        validate_alignment(original, transformed, self.alignment)
        expected_runs = conserved_runs(self.alignment)
        if self.conserved_token_runs != expected_runs:
            raise ValueError("conserved_token_runs do not match canonical alignment")
        expected_diffs = structural_observation_diff(original, transformed, self.ngram_len, self.alignment)
        if self.observation_diffs != expected_diffs:
            raise ValueError("observation_diffs do not match canonical observation mapping")
        expected_summary = summarize_structural_observations(
            original,
            transformed,
            self.ngram_len,
            self.observation_diffs,
        )
        if self.observation_summary != expected_summary:
            raise ValueError("observation_summary does not match observation diffs")
        expected_actual = tuple(
            diff.original_index
            for diff in self.observation_diffs
            if diff.state is not StructuralObservationState.PRESERVED
        )
        if self.actual_non_preserved_indices != expected_actual:
            raise ValueError("actual_non_preserved_indices do not match observation diffs")
        if self.expected_non_preserved_indices != tuple(sorted(set(self.expected_non_preserved_indices))):
            raise ValueError("expected_non_preserved_indices must be unique and ordered")
        for value in self.expected_non_preserved_indices:
            require_int("expected non-preserved index", value)
            if value < 0 or value >= self.observation_summary.original_count:
                raise ValueError("expected non-preserved index is outside original observation range")
        require_int("suffix_expected_observation_count", self.suffix_expected_observation_count)
        require_int("suffix_preserved_observation_count", self.suffix_preserved_observation_count)
        if self.suffix_expected_observation_count < 0:
            raise ValueError("suffix_expected_observation_count must be non-negative")
        if not 0 <= self.suffix_preserved_observation_count <= self.suffix_expected_observation_count:
            raise ValueError("suffix_preserved_observation_count is outside expected suffix range")
        expected_status = _mechanism_status(
            self.experiment_id,
            self.expected_non_preserved_indices,
            self.actual_non_preserved_indices,
            self.suffix_expected_observation_count,
            self.suffix_preserved_observation_count,
        )
        if self.status is not expected_status:
            raise ValueError("mechanism status does not match experiment criterion")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match observation mechanism result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_id": self.experiment_id.value,
            "experiment_definition_hash": self.experiment_definition_hash,
            "original_tokens": self.original_tokens,
            "transformed_tokens": self.transformed_tokens,
            "ngram_len": self.ngram_len,
            "edit_original_index": self.edit_original_index,
            "edit_transformed_index": self.edit_transformed_index,
            "alignment": self.alignment,
            "conserved_token_runs": self.conserved_token_runs,
            "observation_diffs": self.observation_diffs,
            "observation_summary": self.observation_summary,
            "expected_non_preserved_indices": self.expected_non_preserved_indices,
            "actual_non_preserved_indices": self.actual_non_preserved_indices,
            "suffix_expected_observation_count": self.suffix_expected_observation_count,
            "suffix_preserved_observation_count": self.suffix_preserved_observation_count,
            "status": self.status.value,
        }


def _mechanism_status(
    experiment_id: DevelopmentExperimentId,
    expected_non_preserved_indices: tuple[int, ...],
    actual_non_preserved_indices: tuple[int, ...],
    suffix_expected_count: int,
    suffix_preserved_count: int,
) -> MechanismStatus:
    if experiment_id is DevelopmentExperimentId.E04:
        return (
            MechanismStatus.PASS
            if actual_non_preserved_indices == expected_non_preserved_indices
            else MechanismStatus.MISMATCH
        )
    return (
        MechanismStatus.PASS
        if suffix_expected_count > 0 and suffix_preserved_count == suffix_expected_count
        else MechanismStatus.MISMATCH
    )


def _single_edit_step(
    alignment: AlignmentResult,
    expected_op: AlignmentOp,
) -> tuple[int, object]:
    edits = tuple(
        (index, step)
        for index, step in enumerate(alignment.steps)
        if step.op is not AlignmentOp.MATCH
    )
    if alignment.distance != 1 or len(edits) != 1 or edits[0][1].op is not expected_op:
        raise MechanismInputError(f"fixture must contain exactly one {expected_op.value} edit")
    return edits[0]


def _prefix_consumption(alignment: AlignmentResult, edit_step_index: int) -> tuple[int, int]:
    original_count = 0
    transformed_count = 0
    for step in alignment.steps[:edit_step_index]:
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE, AlignmentOp.DELETE):
            original_count += 1
        if step.op in (AlignmentOp.MATCH, AlignmentOp.SUBSTITUTE, AlignmentOp.INSERT):
            transformed_count += 1
    return original_count, transformed_count


def _suffix_preservation_counts(
    diffs: tuple[StructuralObservationDiff, ...],
    original_suffix_start: int,
    transformed_suffix_start: int,
    original_count: int,
    ngram_len: int,
) -> tuple[int, int]:
    expected_count = max(0, original_count - ngram_len + 1 - original_suffix_start)
    preserved = 0
    for original_index in range(original_suffix_start, original_suffix_start + expected_count):
        expected_transformed_index = transformed_suffix_start + (original_index - original_suffix_start)
        diff = diffs[original_index]
        if (
            diff.state is StructuralObservationState.PRESERVED
            and diff.transformed_index == expected_transformed_index
        ):
            preserved += 1
    return expected_count, preserved


def run_observation_mechanism(
    experiment_id: DevelopmentExperimentId,
    original_tokens: tuple[int, ...],
    transformed_tokens: tuple[int, ...],
    ngram_len: int,
) -> ObservationMechanismResult:
    if experiment_id not in (
        DevelopmentExperimentId.E04,
        DevelopmentExperimentId.E05,
        DevelopmentExperimentId.E06,
    ):
        raise ValueError("experiment_id must be E04, E05, or E06")
    original = normalize_token_sequence("original_tokens", original_tokens)
    transformed = normalize_token_sequence("transformed_tokens", transformed_tokens)
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    alignment = align_tokens(original, transformed)
    expected_non_preserved: tuple[int, ...] = ()
    edit_original_index: int | None = None
    edit_transformed_index: int | None = None
    suffix_expected = 0
    suffix_preserved = 0
    if experiment_id is DevelopmentExperimentId.E04:
        if len(original) != len(transformed):
            raise MechanismInputError("E04 requires equal-length token sequences")
        _, edit = _single_edit_step(alignment, AlignmentOp.SUBSTITUTE)
        edit_original_index = edit.original_index
        edit_transformed_index = edit.transformed_index
        if edit_original_index is None or edit_transformed_index is None:
            raise RuntimeError("substitution edit is missing indices")
        interval = substitution_observation_interval(edit_original_index, len(original), ngram_len)
        expected_non_preserved = tuple(range(interval.start, interval.end_exclusive))
    elif experiment_id is DevelopmentExperimentId.E05:
        if len(transformed) != len(original) + 1:
            raise MechanismInputError("E05 requires exactly one inserted token")
        step_index, edit = _single_edit_step(alignment, AlignmentOp.INSERT)
        edit_transformed_index = edit.transformed_index
        if edit_transformed_index is None:
            raise RuntimeError("insertion edit is missing transformed index")
        original_prefix, transformed_prefix = _prefix_consumption(alignment, step_index)
        if transformed_prefix != edit_transformed_index:
            raise RuntimeError("insertion prefix geometry is inconsistent")
        original_suffix_start = original_prefix
        transformed_suffix_start = edit_transformed_index + 1
        if original[original_suffix_start:] != transformed[transformed_suffix_start:]:
            raise MechanismInputError("E05 suffix is not conserved after the insertion")
    else:
        if len(original) != len(transformed) + 1:
            raise MechanismInputError("E06 requires exactly one deleted token")
        step_index, edit = _single_edit_step(alignment, AlignmentOp.DELETE)
        edit_original_index = edit.original_index
        if edit_original_index is None:
            raise RuntimeError("deletion edit is missing original index")
        original_prefix, transformed_prefix = _prefix_consumption(alignment, step_index)
        if original_prefix != edit_original_index:
            raise RuntimeError("deletion prefix geometry is inconsistent")
        original_suffix_start = edit_original_index + 1
        transformed_suffix_start = transformed_prefix
        if original[original_suffix_start:] != transformed[transformed_suffix_start:]:
            raise MechanismInputError("E06 suffix is not conserved after the deletion")
    diffs = structural_observation_diff(original, transformed, ngram_len, alignment)
    summary = summarize_structural_observations(original, transformed, ngram_len, diffs)
    actual_non_preserved = tuple(
        diff.original_index
        for diff in diffs
        if diff.state is not StructuralObservationState.PRESERVED
    )
    if experiment_id in (DevelopmentExperimentId.E05, DevelopmentExperimentId.E06):
        suffix_expected, suffix_preserved = _suffix_preservation_counts(
            diffs,
            original_suffix_start,
            transformed_suffix_start,
            len(original),
            ngram_len,
        )
        if suffix_expected == 0:
            raise MechanismInputError("E05/E06 fixture must retain at least one full suffix n-gram")
    status = _mechanism_status(
        experiment_id,
        expected_non_preserved,
        actual_non_preserved,
        suffix_expected,
        suffix_preserved,
    )
    definition = default_development_experiment_registry().get(experiment_id)
    runs = conserved_runs(alignment)
    payload = {
        "algorithm_version": OBSERVATION_MECHANISM_ALGORITHM_VERSION,
        "experiment_id": experiment_id.value,
        "experiment_definition_hash": definition.definition_hash,
        "original_tokens": original,
        "transformed_tokens": transformed,
        "ngram_len": ngram_len,
        "edit_original_index": edit_original_index,
        "edit_transformed_index": edit_transformed_index,
        "alignment": alignment,
        "conserved_token_runs": runs,
        "observation_diffs": diffs,
        "observation_summary": summary,
        "expected_non_preserved_indices": expected_non_preserved,
        "actual_non_preserved_indices": actual_non_preserved,
        "suffix_expected_observation_count": suffix_expected,
        "suffix_preserved_observation_count": suffix_preserved,
        "status": status.value,
    }
    return ObservationMechanismResult(
        OBSERVATION_MECHANISM_ALGORITHM_VERSION,
        experiment_id,
        definition.definition_hash,
        original,
        transformed,
        ngram_len,
        edit_original_index,
        edit_transformed_index,
        alignment,
        runs,
        diffs,
        summary,
        expected_non_preserved,
        actual_non_preserved,
        suffix_expected,
        suffix_preserved,
        status,
        sha256_json(payload),
    )
