from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..alignment import AlignmentResult
from ..hashing import sha256_json
from ..native_observations import NativeObservationBatch
from ..observations import structural_observation_diff
from .e20_bundle import E20ResultBundle
from .e20_row_verification import E20_ROW_REPLAY_ALGORITHM_VERSION
from .e20_rows import E20OutcomeRow


E20_GVALUE_DEPTH_ALGORITHM_VERSION = "e20-gvalue-depth-v1"


class E20GValueDepthError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E20PerDepthGValueRecord:
    outcome_row_hash: str
    depth: int
    matched_observation_count: int
    per_depth_hamming_difference_count: tuple[int, ...]
    per_depth_summary_hash: str
    record_hash: str

    def __post_init__(self) -> None:
        require_sha256("outcome_row_hash", self.outcome_row_hash)
        require_int("depth", self.depth)
        require_int("matched_observation_count", self.matched_observation_count)
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if self.matched_observation_count < 0:
            raise ValueError("matched_observation_count must be non-negative")
        if not isinstance(self.per_depth_hamming_difference_count, tuple):
            raise TypeError("per_depth_hamming_difference_count must be a tuple")
        if len(self.per_depth_hamming_difference_count) != self.depth:
            raise ValueError("per-depth hamming vector length must equal depth")
        for value in self.per_depth_hamming_difference_count:
            require_int("per-depth hamming difference count", value)
            if value < 0 or value > self.matched_observation_count:
                raise ValueError("per-depth hamming difference count must be within matched observation count")
        require_sha256("per_depth_summary_hash", self.per_depth_summary_hash)
        expected_summary = sha256_json(
            {
                "algorithm_version": E20_ROW_REPLAY_ALGORITHM_VERSION,
                "matched_observation_count": self.matched_observation_count,
                "per_depth_hamming_difference_count": self.per_depth_hamming_difference_count,
            }
        )
        if self.per_depth_summary_hash != expected_summary:
            raise ValueError("per_depth_summary_hash does not match per-depth g-value vector")
        require_sha256("record_hash", self.record_hash)
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match per-depth g-value record")

    @property
    def hamming_difference_count(self) -> int:
        return sum(self.per_depth_hamming_difference_count)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": E20_GVALUE_DEPTH_ALGORITHM_VERSION,
            "outcome_row_hash": self.outcome_row_hash,
            "depth": self.depth,
            "matched_observation_count": self.matched_observation_count,
            "per_depth_hamming_difference_count": self.per_depth_hamming_difference_count,
            "per_depth_summary_hash": self.per_depth_summary_hash,
        }


@dataclass(frozen=True, slots=True)
class E20GValueDepthBundle:
    algorithm_version: str
    execution_id: str
    result_bundle_hash: str
    records: tuple[E20PerDepthGValueRecord, ...]
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_GVALUE_DEPTH_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 g-value depth algorithm version")
        require_sha256("execution_id", self.execution_id)
        require_sha256("result_bundle_hash", self.result_bundle_hash)
        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple")
        if any(not isinstance(value, E20PerDepthGValueRecord) for value in self.records):
            raise TypeError("records must contain E20PerDepthGValueRecord values")
        expected = tuple(sorted(self.records, key=lambda value: (value.outcome_row_hash, value.record_hash)))
        if self.records != expected:
            raise ValueError("per-depth g-value records must be canonically ordered")
        if len({value.outcome_row_hash for value in self.records}) != len(self.records):
            raise ValueError("per-depth g-value records must be unique by outcome row hash")
        require_sha256("bundle_hash", self.bundle_hash)
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match E20 g-value depth bundle")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "result_bundle_hash": self.result_bundle_hash,
            "records": self.records,
        }


def _per_depth_counts(
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    alignment: AlignmentResult,
) -> tuple[int, tuple[int, ...]]:
    if not isinstance(original_batch, NativeObservationBatch):
        raise TypeError("original_batch must be a NativeObservationBatch")
    if not isinstance(transformed_batch, NativeObservationBatch):
        raise TypeError("transformed_batch must be a NativeObservationBatch")
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    if original_batch.ngram_len != transformed_batch.ngram_len:
        raise E20GValueDepthError("observation batches use different n-gram lengths")
    if original_batch.depth != transformed_batch.depth:
        raise E20GValueDepthError("observation batches use different watermark depths")
    diffs = structural_observation_diff(
        original_batch.token_ids,
        transformed_batch.token_ids,
        original_batch.ngram_len,
        alignment,
    )
    per_depth = [0] * original_batch.depth
    matched = 0
    for diff in diffs:
        original_record = original_batch.records[diff.original_index]
        if not original_record.valid or diff.transformed_index is None:
            continue
        transformed_record = transformed_batch.records[diff.transformed_index]
        if not transformed_record.valid:
            continue
        matched += 1
        for depth, (before, after) in enumerate(zip(original_record.g_values, transformed_record.g_values)):
            per_depth[depth] += int(before != after)
    return matched, tuple(per_depth)


def build_e20_per_depth_gvalue_record(
    row: E20OutcomeRow,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    alignment: AlignmentResult,
) -> E20PerDepthGValueRecord:
    if not isinstance(row, E20OutcomeRow):
        raise TypeError("row must be an E20OutcomeRow")
    matched, per_depth = _per_depth_counts(original_batch, transformed_batch, alignment)
    summary_hash = sha256_json(
        {
            "algorithm_version": E20_ROW_REPLAY_ALGORITHM_VERSION,
            "matched_observation_count": matched,
            "per_depth_hamming_difference_count": per_depth,
        }
    )
    if row.gvalues.depth != original_batch.depth:
        raise E20GValueDepthError("outcome row depth does not match observation batches")
    if row.gvalues.matched_observation_count != matched:
        raise E20GValueDepthError("outcome row matched observation count does not replay from observation batches")
    if row.gvalues.hamming_difference_count != sum(per_depth):
        raise E20GValueDepthError("outcome row g-value hamming count does not replay from per-depth vector")
    if row.gvalues.per_depth_summary_hash != summary_hash:
        raise E20GValueDepthError("outcome row per-depth summary hash does not replay from per-depth vector")
    payload = {
        "algorithm_version": E20_GVALUE_DEPTH_ALGORITHM_VERSION,
        "outcome_row_hash": row.row_hash,
        "depth": original_batch.depth,
        "matched_observation_count": matched,
        "per_depth_hamming_difference_count": per_depth,
        "per_depth_summary_hash": summary_hash,
    }
    return E20PerDepthGValueRecord(
        row.row_hash,
        original_batch.depth,
        matched,
        per_depth,
        summary_hash,
        sha256_json(payload),
    )


def verify_e20_per_depth_gvalue_record(
    record: E20PerDepthGValueRecord,
    row: E20OutcomeRow,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    alignment: AlignmentResult,
) -> None:
    if not isinstance(record, E20PerDepthGValueRecord):
        raise TypeError("record must be an E20PerDepthGValueRecord")
    expected = build_e20_per_depth_gvalue_record(
        row,
        original_batch,
        transformed_batch,
        alignment,
    )
    if record != expected:
        raise E20GValueDepthError("per-depth g-value record does not replay exactly from outcome and observation artifacts")


def _verify_record_against_row(record: E20PerDepthGValueRecord, row: E20OutcomeRow) -> None:
    if record.outcome_row_hash != row.row_hash:
        raise E20GValueDepthError("per-depth g-value record does not bind to outcome row")
    if record.depth != row.gvalues.depth:
        raise E20GValueDepthError("per-depth g-value depth does not match outcome row")
    if record.matched_observation_count != row.gvalues.matched_observation_count:
        raise E20GValueDepthError("per-depth matched observation count does not match outcome row")
    if record.hamming_difference_count != row.gvalues.hamming_difference_count:
        raise E20GValueDepthError("per-depth hamming total does not match outcome row")
    if record.per_depth_summary_hash != row.gvalues.per_depth_summary_hash:
        raise E20GValueDepthError("per-depth summary hash does not match outcome row")


def build_e20_gvalue_depth_bundle(
    result_bundle: E20ResultBundle,
    records: Sequence[E20PerDepthGValueRecord],
) -> E20GValueDepthBundle:
    if not isinstance(result_bundle, E20ResultBundle):
        raise TypeError("result_bundle must be an E20ResultBundle")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        raise TypeError("records must be a sequence")
    values = tuple(records)
    if any(not isinstance(value, E20PerDepthGValueRecord) for value in values):
        raise TypeError("records must contain E20PerDepthGValueRecord values")
    row_by_hash = {value.row_hash: value for value in result_bundle.outcome_rows}
    if set(value.outcome_row_hash for value in values) != set(row_by_hash):
        raise E20GValueDepthError("per-depth g-value bundle must contain exactly one record per E20 outcome row")
    if len(values) != len(row_by_hash):
        raise E20GValueDepthError("per-depth g-value bundle contains duplicate outcome-row bindings")
    for value in values:
        _verify_record_against_row(value, row_by_hash[value.outcome_row_hash])
    ordered = tuple(sorted(values, key=lambda value: (value.outcome_row_hash, value.record_hash)))
    payload = {
        "algorithm_version": E20_GVALUE_DEPTH_ALGORITHM_VERSION,
        "execution_id": result_bundle.execution_id,
        "result_bundle_hash": result_bundle.bundle_hash,
        "records": ordered,
    }
    return E20GValueDepthBundle(
        E20_GVALUE_DEPTH_ALGORITHM_VERSION,
        result_bundle.execution_id,
        result_bundle.bundle_hash,
        ordered,
        sha256_json(payload),
    )


def verify_e20_gvalue_depth_bundle(
    bundle: E20GValueDepthBundle,
    result_bundle: E20ResultBundle,
) -> None:
    if not isinstance(bundle, E20GValueDepthBundle):
        raise TypeError("bundle must be an E20GValueDepthBundle")
    expected = build_e20_gvalue_depth_bundle(result_bundle, bundle.records)
    if bundle != expected:
        raise E20GValueDepthError("E20 g-value depth bundle does not replay exactly from result rows")
