from __future__ import annotations

import math
import random
from typing import Sequence

from .._validation import require_int
from ..hashing import sha256_json
from .mid_dev_primary_inference_safe import (
    MID_DEV_PRIMARY_BOOTSTRAP_REPLICATES,
    MID_DEV_PRIMARY_INFERENCE_V2,
    MID_DEV_PRIMARY_TARGET_LENGTHS,
    MidDevPrimaryInferenceResult,
    _length_summary,
    _mean,
    _normalize_condition,
    _source_contrast,
)
from .mid_dev_scored_schema import MidDevScoredPlanRow
from .mid_dev_scoring_contracts import MidDevCondition


def _calibration_registry_hash(rows: Sequence[MidDevScoredPlanRow]) -> str:
    entries = tuple(
        sorted(
            {
                (row.target_length, row.length_calibration_binding_hash)
                for row in rows
            }
        )
    )
    if {value[0] for value in entries} != set(MID_DEV_PRIMARY_TARGET_LENGTHS):
        raise ValueError("primary inference requires calibration bindings for 128 and 256")
    if len(entries) != 2:
        raise ValueError("primary inference found multiple calibration bindings within a length stratum")
    return sha256_json(entries)


def primary_realized_cost_inference(
    rows: Sequence[MidDevScoredPlanRow],
    *,
    deterministic_condition,
    budget: int,
    bootstrap_replicates: int = MID_DEV_PRIMARY_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = 0x4D494444455632,
) -> MidDevPrimaryInferenceResult:
    deterministic_condition = _normalize_condition(deterministic_condition)
    if deterministic_condition in {MidDevCondition.RANDOM_SAFE, MidDevCondition.NO_OP}:
        raise ValueError("primary inference requires a deterministic edit condition")
    require_int("budget", budget)
    require_int("bootstrap_replicates", bootstrap_replicates)
    require_int("bootstrap_seed", bootstrap_seed)
    if bootstrap_replicates <= 0 or bootstrap_seed < 0:
        raise ValueError("invalid bootstrap configuration")
    relevant = tuple(
        row
        for row in rows
        if row.budget == budget
        and row.condition in {deterministic_condition, MidDevCondition.RANDOM_SAFE}
    )
    detector_hashes = {row.detector_identity_hash for row in relevant}
    if len(detector_hashes) != 1:
        raise ValueError("primary inference cannot mix detector identities")
    calibration_registry_hash = _calibration_registry_hash(relevant)
    grouped: dict[str, list[MidDevScoredPlanRow]] = {}
    for row in relevant:
        grouped.setdefault(row.source_group_id, []).append(row)
    if len(grouped) != 36:
        raise ValueError("primary inference requires all 36 planned MidDev source groups")
    contrasts = []
    excluded = []
    for source_group_id in sorted(grouped):
        contrast = _source_contrast(
            source_group_id,
            grouped[source_group_id],
            deterministic_condition=deterministic_condition,
            budget=budget,
        )
        if contrast is None:
            excluded.append(source_group_id)
        else:
            contrasts.append(contrast)
    if len(contrasts) < 32:
        raise ValueError("fewer than 32 MidDev source groups have realized-cost-matched primary evidence")
    materialized = tuple(contrasts)
    length_summaries = tuple(
        _length_summary(target_length, materialized)
        for target_length in MID_DEV_PRIMARY_TARGET_LENGTHS
    )
    adjusted = tuple(value.control_adjusted_margin_advantage for value in materialized)
    rng = random.Random(bootstrap_seed)
    count = len(adjusted)
    bootstrap = sorted(
        sum(adjusted[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(bootstrap_replicates)
    )
    lower_index = max(0, math.floor(0.025 * (bootstrap_replicates - 1)))
    upper_index = min(bootstrap_replicates - 1, math.ceil(0.975 * (bootstrap_replicates - 1)))
    positive = sum(value > 0 for value in adjusted)
    negative = sum(value < 0 for value in adjusted)
    zero = count - positive - negative
    nonzero = positive + negative
    if nonzero == 0:
        sign_p = 1.0
    else:
        tail = min(positive, negative)
        cumulative = sum(math.comb(nonzero, value) for value in range(tail + 1)) / (2**nonzero)
        sign_p = min(1.0, 2.0 * cumulative)
    payload = {
        "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
        "detector_identity_hash": next(iter(detector_hashes)),
        "threshold_registry_hash": calibration_registry_hash,
        "deterministic_condition": deterministic_condition.value,
        "budget": budget,
        "planned_source_group_count": 36,
        "eligible_source_group_count": count,
        "excluded_source_group_ids": tuple(excluded),
        "source_contrast_hashes": tuple(value.contrast_hash for value in materialized),
        "length_summary_hashes": tuple(value.summary_hash for value in length_summaries),
        "mean_watermarked_margin_advantage": _mean(tuple(value.watermarked_margin_advantage for value in materialized)),
        "mean_control_margin_advantage": _mean(tuple(value.control_margin_advantage for value in materialized)),
        "mean_control_adjusted_margin_advantage": _mean(adjusted),
        "bootstrap_lower": bootstrap[lower_index],
        "bootstrap_upper": bootstrap[upper_index],
        "positive_adjusted_count": positive,
        "negative_adjusted_count": negative,
        "zero_adjusted_count": zero,
        "two_sided_sign_p_value": sign_p,
        "bootstrap_replicates": bootstrap_replicates,
    }
    return MidDevPrimaryInferenceResult(
        next(iter(detector_hashes)),
        calibration_registry_hash,
        deterministic_condition,
        budget,
        36,
        count,
        tuple(excluded),
        materialized,
        length_summaries,
        payload["mean_watermarked_margin_advantage"],
        payload["mean_control_margin_advantage"],
        payload["mean_control_adjusted_margin_advantage"],
        payload["bootstrap_lower"],
        payload["bootstrap_upper"],
        positive,
        negative,
        zero,
        sign_p,
        bootstrap_replicates,
        sha256_json(payload),
    )
