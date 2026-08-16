from __future__ import annotations

import math
from collections.abc import Sequence

from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from .._validation import require_int
from ..hashing import sha256_json
from ..native_observations import NativeObservationBatch
from .compatibility import require_supported_detector
from .types import (
    DetectorFamily,
    ScoreDirection,
    UncalibratedDetectorEvidence,
    ZeroValidObservationsError,
)


MEAN_ALGORITHM_VERSION = "deepmind-mean-score-v2"
WEIGHTED_MEAN_ALGORITHM_VERSION = "deepmind-weighted-mean-score-v2"


def _normalize_g_values(g_values: Sequence[Sequence[int]]) -> tuple[tuple[tuple[int, ...], ...], int]:
    if not isinstance(g_values, Sequence) or isinstance(g_values, (str, bytes, bytearray)):
        raise TypeError("g_values must be a sequence of g-value rows")
    rows: list[tuple[int, ...]] = []
    depth: int | None = None
    for row in g_values:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)):
            raise TypeError("g-value rows must be sequences of binary integers")
        snapshot = tuple(row)
        if depth is None:
            depth = len(snapshot)
            if depth <= 0:
                raise ValueError("g-value depth must be positive")
        elif len(snapshot) != depth:
            raise ValueError("all g-value rows must have the same depth")
        for value in snapshot:
            require_int("g-value", value)
            if value not in (0, 1):
                raise ValueError("g-values must be binary integers")
        rows.append(snapshot)
    if depth is None:
        raise ZeroValidObservationsError("g_values contain no observations")
    return tuple(rows), depth


def _normalize_mask(mask: Sequence[bool | int], expected_count: int) -> tuple[bool, ...]:
    if not isinstance(mask, Sequence) or isinstance(mask, (str, bytes, bytearray)):
        raise TypeError("mask must be a sequence of binary values")
    snapshot = tuple(mask)
    if len(snapshot) != expected_count:
        raise ValueError("mask length must match g-value observation count")
    output: list[bool] = []
    for value in snapshot:
        if isinstance(value, bool):
            output.append(value)
            continue
        require_int("mask value", value)
        if value not in (0, 1):
            raise ValueError("mask values must be booleans or binary integers")
        output.append(bool(value))
    return tuple(output)


def _normalize_weights(weights: Sequence[float | int] | None, depth: int) -> tuple[float, ...]:
    require_int("depth", depth)
    if depth <= 0:
        raise ValueError("depth must be positive")
    if weights is None:
        if depth == 1:
            raw = (10.0,)
        else:
            step = 9.0 / (depth - 1)
            raw = tuple(10.0 - step * index for index in range(depth))
    else:
        if not isinstance(weights, Sequence) or isinstance(weights, (str, bytes, bytearray)):
            raise TypeError("weights must be a sequence of real numbers")
        raw = tuple(weights)
        if len(raw) != depth:
            raise ValueError("weights length must match g-value depth")
    normalized_input: list[float] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("weights must contain real numbers")
        try:
            number = float(value)
        except OverflowError as error:
            raise ValueError("weights must be representable as finite floats") from error
        if not math.isfinite(number):
            raise ValueError("weights must be finite")
        if number < 0.0:
            raise ValueError("weights must be non-negative")
        normalized_input.append(number)
    peak = max(normalized_input)
    if peak <= 0.0:
        raise ValueError("weights must contain positive total mass")
    scaled = tuple(value / peak for value in normalized_input)
    total = math.fsum(scaled)
    scale = depth / total
    output = [value * scale for value in scaled]
    correction = float(depth) - math.fsum(output)
    largest_index = max(range(depth), key=output.__getitem__)
    output[largest_index] += correction
    return tuple(output)


def _score(
    rows: tuple[tuple[int, ...], ...],
    mask: tuple[bool, ...],
    normalized_weights: tuple[float, ...],
) -> tuple[float, int]:
    valid_count = sum(mask)
    if valid_count == 0:
        raise ZeroValidObservationsError("detector mask contains zero valid observations")
    depth = len(normalized_weights)
    row_scores = (
        math.fsum(normalized_weights[layer] * row[layer] for layer in range(depth)) / depth
        for row, valid in zip(rows, mask)
        if valid
    )
    score = math.fsum(row_scores) / valid_count
    tolerance = 1e-12
    if score < -tolerance or score > 1.0 + tolerance:
        raise ArithmeticError("detector score escaped its mathematical [0, 1] range")
    return min(1.0, max(0.0, score)), valid_count


def mean_score(
    g_values: Sequence[Sequence[int]],
    mask: Sequence[bool | int],
) -> float:
    rows, depth = _normalize_g_values(g_values)
    normalized_mask = _normalize_mask(mask, len(rows))
    score, _ = _score(rows, normalized_mask, (1.0,) * depth)
    return score


def weighted_mean_score(
    g_values: Sequence[Sequence[int]],
    mask: Sequence[bool | int],
    weights: Sequence[float | int] | None = None,
) -> float:
    rows, depth = _normalize_g_values(g_values)
    normalized_mask = _normalize_mask(mask, len(rows))
    normalized_weights = _normalize_weights(weights, depth)
    score, _ = _score(rows, normalized_mask, normalized_weights)
    return score


def _evidence(
    batch: NativeObservationBatch,
    detector_family: DetectorFamily,
    algorithm_version: str,
    normalized_weights: tuple[float, ...],
) -> UncalibratedDetectorEvidence:
    compatibility = require_supported_detector(batch, detector_family)
    rows = batch.g_values
    mask = batch.valid_mask
    score, valid_count = _score(rows, mask, normalized_weights)
    config_hash = sha256_json(
        {
            "detector_family": detector_family.value,
            "algorithm_version": algorithm_version,
            "detector_source_commit": DEEPMIND_REFERENCE_SOURCE_PIN.commit,
            "normalized_weights": normalized_weights,
        }
    )
    return UncalibratedDetectorEvidence(
        sample_id=batch.sample_id,
        detector_family=detector_family,
        detector_algorithm_version=algorithm_version,
        detector_config_hash=config_hash,
        observation_batch_hash=sha256_json(batch),
        detector_source_id=DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
        detector_source_commit=DEEPMIND_REFERENCE_SOURCE_PIN.commit,
        adapter_id=batch.adapter_id,
        adapter_algorithm_version=batch.adapter_algorithm_version,
        adapter_config_hash=batch.adapter_config_hash,
        source_id=batch.source_id,
        source_commit=batch.source_commit,
        direction=ScoreDirection.HIGHER_IS_MORE_WATERMARKED,
        total_observation_count=len(batch.records),
        valid_observation_count=valid_count,
        depth=batch.depth,
        raw_score=score,
        normalized_weights=normalized_weights,
        compatibility=compatibility,
    )


def mean_evidence(batch: NativeObservationBatch) -> UncalibratedDetectorEvidence:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    return _evidence(
        batch,
        DetectorFamily.MEAN,
        MEAN_ALGORITHM_VERSION,
        (1.0,) * batch.depth,
    )


def weighted_mean_evidence(
    batch: NativeObservationBatch,
    weights: Sequence[float | int] | None = None,
) -> UncalibratedDetectorEvidence:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    normalized_weights = _normalize_weights(weights, batch.depth)
    return _evidence(
        batch,
        DetectorFamily.WEIGHTED_MEAN,
        WEIGHTED_MEAN_ALGORITHM_VERSION,
        normalized_weights,
    )
