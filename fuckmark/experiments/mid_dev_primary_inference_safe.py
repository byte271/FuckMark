from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .mid_dev_scored_schema import MidDevScoredPlanRow
from .mid_dev_scoring_contracts import SUCCESS, MidDevCondition


MID_DEV_PRIMARY_INFERENCE_V2 = "mid-dev-primary-realized-cost-v3"
MID_DEV_PRIMARY_LENGTH_SUMMARY_VERSION = "mid-dev-primary-length-summary-v1"
MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES = 8
MID_DEV_PRIMARY_BOOTSTRAP_REPLICATES = 10_000
MID_DEV_PRIMARY_TARGET_LENGTHS = (128, 256)


@dataclass(frozen=True, slots=True)
class MidDevPrimarySourceContrast:
    source_group_id: str
    target_length: int
    budget: int
    deterministic_condition: MidDevCondition
    realized_edit_cost: int
    watermarked_random_match_count: int
    control_random_match_count: int
    watermarked_margin_advantage: float
    control_margin_advantage: float
    control_adjusted_margin_advantage: float
    contrast_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_group_id, str) or not self.source_group_id:
            raise ValueError("source_group_id must be non-empty")
        require_int("target_length", self.target_length)
        if self.target_length not in MID_DEV_PRIMARY_TARGET_LENGTHS:
            raise ValueError("primary source contrast target length must be 128 or 256")
        if not isinstance(self.deterministic_condition, MidDevCondition):
            raise TypeError("deterministic_condition must be MidDevCondition")
        require_int("budget", self.budget)
        require_int("realized_edit_cost", self.realized_edit_cost)
        require_int("watermarked_random_match_count", self.watermarked_random_match_count)
        require_int("control_random_match_count", self.control_random_match_count)
        if self.realized_edit_cost <= 0:
            raise ValueError("primary source contrast requires positive realized edit cost")
        if self.watermarked_random_match_count < MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES:
            raise ValueError("watermarked source contrast requires at least eight matched random replicates")
        if self.control_random_match_count < MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES:
            raise ValueError("control source contrast requires at least eight matched random replicates")
        for name in (
            "watermarked_margin_advantage",
            "control_margin_advantage",
            "control_adjusted_margin_advantage",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        require_sha256("contrast_hash", self.contrast_hash)
        if self.contrast_hash != sha256_json(self.payload()):
            raise ValueError("contrast_hash does not match MidDev source contrast")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
            "source_group_id": self.source_group_id,
            "target_length": self.target_length,
            "budget": self.budget,
            "deterministic_condition": self.deterministic_condition.value,
            "realized_edit_cost": self.realized_edit_cost,
            "watermarked_random_match_count": self.watermarked_random_match_count,
            "control_random_match_count": self.control_random_match_count,
            "watermarked_margin_advantage": self.watermarked_margin_advantage,
            "control_margin_advantage": self.control_margin_advantage,
            "control_adjusted_margin_advantage": self.control_adjusted_margin_advantage,
        }


@dataclass(frozen=True, slots=True)
class MidDevPrimaryLengthSummary:
    target_length: int
    source_group_count: int
    mean_watermarked_margin_advantage: float
    mean_control_margin_advantage: float
    mean_control_adjusted_margin_advantage: float
    positive_adjusted_count: int
    negative_adjusted_count: int
    zero_adjusted_count: int
    summary_hash: str

    def __post_init__(self) -> None:
        require_int("target_length", self.target_length)
        if self.target_length not in MID_DEV_PRIMARY_TARGET_LENGTHS:
            raise ValueError("length summary target must be 128 or 256")
        require_int("source_group_count", self.source_group_count)
        if not 1 <= self.source_group_count <= 18:
            raise ValueError("length summary must contain between one and 18 source groups")
        for name in (
            "mean_watermarked_margin_advantage",
            "mean_control_margin_advantage",
            "mean_control_adjusted_margin_advantage",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        for name in ("positive_adjusted_count", "negative_adjusted_count", "zero_adjusted_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.positive_adjusted_count + self.negative_adjusted_count + self.zero_adjusted_count != self.source_group_count:
            raise ValueError("length summary sign counts do not partition source groups")
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("summary_hash does not match MidDev length summary")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_PRIMARY_LENGTH_SUMMARY_VERSION,
            "target_length": self.target_length,
            "source_group_count": self.source_group_count,
            "mean_watermarked_margin_advantage": self.mean_watermarked_margin_advantage,
            "mean_control_margin_advantage": self.mean_control_margin_advantage,
            "mean_control_adjusted_margin_advantage": self.mean_control_adjusted_margin_advantage,
            "positive_adjusted_count": self.positive_adjusted_count,
            "negative_adjusted_count": self.negative_adjusted_count,
            "zero_adjusted_count": self.zero_adjusted_count,
        }


@dataclass(frozen=True, slots=True)
class MidDevPrimaryInferenceResult:
    detector_identity_hash: str
    threshold_registry_hash: str
    deterministic_condition: MidDevCondition
    budget: int
    planned_source_group_count: int
    eligible_source_group_count: int
    excluded_source_group_ids: tuple[str, ...]
    source_contrasts: tuple[MidDevPrimarySourceContrast, ...]
    length_summaries: tuple[MidDevPrimaryLengthSummary, ...]
    mean_watermarked_margin_advantage: float
    mean_control_margin_advantage: float
    mean_control_adjusted_margin_advantage: float
    bootstrap_lower: float
    bootstrap_upper: float
    positive_adjusted_count: int
    negative_adjusted_count: int
    zero_adjusted_count: int
    two_sided_sign_p_value: float
    bootstrap_replicates: int
    result_hash: str

    def __post_init__(self) -> None:
        require_sha256("detector_identity_hash", self.detector_identity_hash)
        require_sha256("threshold_registry_hash", self.threshold_registry_hash)
        if not isinstance(self.deterministic_condition, MidDevCondition):
            raise TypeError("deterministic_condition must be MidDevCondition")
        for name in (
            "budget",
            "planned_source_group_count",
            "eligible_source_group_count",
            "positive_adjusted_count",
            "negative_adjusted_count",
            "zero_adjusted_count",
            "bootstrap_replicates",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.planned_source_group_count != 36:
            raise ValueError("MidDev primary inference expects 36 planned source groups")
        if self.eligible_source_group_count < 32:
            raise ValueError("MidDev primary inference requires at least 32 eligible source groups")
        if self.eligible_source_group_count != len(self.source_contrasts):
            raise ValueError("eligible source count does not match source contrasts")
        if self.planned_source_group_count != self.eligible_source_group_count + len(self.excluded_source_group_ids):
            raise ValueError("eligible and excluded source counts do not partition planned sources")
        if len(set(self.excluded_source_group_ids)) != len(self.excluded_source_group_ids):
            raise ValueError("excluded source group IDs must be unique")
        if len({value.source_group_id for value in self.source_contrasts}) != len(self.source_contrasts):
            raise ValueError("source contrasts must contain unique source groups")
        if not isinstance(self.length_summaries, tuple) or len(self.length_summaries) != 2:
            raise ValueError("MidDev primary inference must report 128/256 length summaries")
        if {value.target_length for value in self.length_summaries} != set(MID_DEV_PRIMARY_TARGET_LENGTHS):
            raise ValueError("MidDev primary inference length summaries are incomplete")
        if sum(value.source_group_count for value in self.length_summaries) != self.eligible_source_group_count:
            raise ValueError("length summaries do not partition eligible source groups")
        for name in (
            "mean_watermarked_margin_advantage",
            "mean_control_margin_advantage",
            "mean_control_adjusted_margin_advantage",
            "bootstrap_lower",
            "bootstrap_upper",
            "two_sided_sign_p_value",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.bootstrap_lower > self.bootstrap_upper:
            raise ValueError("bootstrap interval is reversed")
        if not 0.0 <= self.two_sided_sign_p_value <= 1.0:
            raise ValueError("sign p-value must be between zero and one")
        if self.positive_adjusted_count + self.negative_adjusted_count + self.zero_adjusted_count != self.eligible_source_group_count:
            raise ValueError("sign counts do not partition eligible sources")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash does not match MidDev primary inference")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_registry_hash": self.threshold_registry_hash,
            "deterministic_condition": self.deterministic_condition.value,
            "budget": self.budget,
            "planned_source_group_count": self.planned_source_group_count,
            "eligible_source_group_count": self.eligible_source_group_count,
            "excluded_source_group_ids": self.excluded_source_group_ids,
            "source_contrast_hashes": tuple(value.contrast_hash for value in self.source_contrasts),
            "length_summary_hashes": tuple(
                value.summary_hash for value in sorted(self.length_summaries, key=lambda item: item.target_length)
            ),
            "mean_watermarked_margin_advantage": self.mean_watermarked_margin_advantage,
            "mean_control_margin_advantage": self.mean_control_margin_advantage,
            "mean_control_adjusted_margin_advantage": self.mean_control_adjusted_margin_advantage,
            "bootstrap_lower": self.bootstrap_lower,
            "bootstrap_upper": self.bootstrap_upper,
            "positive_adjusted_count": self.positive_adjusted_count,
            "negative_adjusted_count": self.negative_adjusted_count,
            "zero_adjusted_count": self.zero_adjusted_count,
            "two_sided_sign_p_value": self.two_sided_sign_p_value,
            "bootstrap_replicates": self.bootstrap_replicates,
        }


def _normalize_condition(value) -> MidDevCondition:
    if isinstance(value, MidDevCondition):
        return value
    raw = getattr(value, "value", value)
    return MidDevCondition(raw)


def _deterministic_row(
    rows: Sequence[MidDevScoredPlanRow],
    *,
    label: WatermarkLabel,
    condition: MidDevCondition,
    budget: int,
) -> MidDevScoredPlanRow | None:
    selected = tuple(
        row
        for row in rows
        if row.source_label is label
        and row.condition is condition
        and row.budget == budget
        and row.replicate == 0
    )
    if len(selected) != 1:
        return None
    row = selected[0]
    if row.status != SUCCESS or row.realized_edit_cost <= 0:
        return None
    return row


def _matched_random_rows(
    rows: Sequence[MidDevScoredPlanRow],
    *,
    label: WatermarkLabel,
    budget: int,
    realized_edit_cost: int,
    target_length: int,
) -> tuple[MidDevScoredPlanRow, ...]:
    return tuple(
        row
        for row in rows
        if row.source_label is label
        and row.target_length == target_length
        and row.condition is MidDevCondition.RANDOM_SAFE
        and row.budget == budget
        and row.status == SUCCESS
        and row.realized_edit_cost == realized_edit_cost
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty sequence")
    return sum(values) / len(values)


def _source_contrast(
    source_group_id: str,
    rows: Sequence[MidDevScoredPlanRow],
    *,
    deterministic_condition: MidDevCondition,
    budget: int,
) -> MidDevPrimarySourceContrast | None:
    wm = _deterministic_row(
        rows,
        label=WatermarkLabel.WATERMARKED,
        condition=deterministic_condition,
        budget=budget,
    )
    control = _deterministic_row(
        rows,
        label=WatermarkLabel.UNWATERMARKED,
        condition=deterministic_condition,
        budget=budget,
    )
    if wm is None or control is None:
        return None
    if wm.realized_edit_cost != control.realized_edit_cost or wm.target_length != control.target_length:
        return None
    realized_cost = wm.realized_edit_cost
    target_length = wm.target_length
    wm_random = _matched_random_rows(
        rows,
        label=WatermarkLabel.WATERMARKED,
        budget=budget,
        realized_edit_cost=realized_cost,
        target_length=target_length,
    )
    control_random = _matched_random_rows(
        rows,
        label=WatermarkLabel.UNWATERMARKED,
        budget=budget,
        realized_edit_cost=realized_cost,
        target_length=target_length,
    )
    if len(wm_random) < MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES:
        return None
    if len(control_random) < MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES:
        return None
    wm_advantage = wm.margin_drop - _mean(tuple(value.margin_drop for value in wm_random))
    control_advantage = control.margin_drop - _mean(tuple(value.margin_drop for value in control_random))
    adjusted = wm_advantage - control_advantage
    payload = {
        "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
        "source_group_id": source_group_id,
        "target_length": target_length,
        "budget": budget,
        "deterministic_condition": deterministic_condition.value,
        "realized_edit_cost": realized_cost,
        "watermarked_random_match_count": len(wm_random),
        "control_random_match_count": len(control_random),
        "watermarked_margin_advantage": wm_advantage,
        "control_margin_advantage": control_advantage,
        "control_adjusted_margin_advantage": adjusted,
    }
    return MidDevPrimarySourceContrast(
        source_group_id,
        target_length,
        budget,
        deterministic_condition,
        realized_cost,
        len(wm_random),
        len(control_random),
        wm_advantage,
        control_advantage,
        adjusted,
        sha256_json(payload),
    )


def _length_summary(
    target_length: int,
    contrasts: Sequence[MidDevPrimarySourceContrast],
) -> MidDevPrimaryLengthSummary:
    values = tuple(value for value in contrasts if value.target_length == target_length)
    if not values:
        raise ValueError("MidDev primary inference cannot omit a target-length stratum")
    adjusted = tuple(value.control_adjusted_margin_advantage for value in values)
    positive = sum(value > 0 for value in adjusted)
    negative = sum(value < 0 for value in adjusted)
    zero = len(adjusted) - positive - negative
    payload = {
        "algorithm_version": MID_DEV_PRIMARY_LENGTH_SUMMARY_VERSION,
        "target_length": target_length,
        "source_group_count": len(values),
        "mean_watermarked_margin_advantage": _mean(tuple(value.watermarked_margin_advantage for value in values)),
        "mean_control_margin_advantage": _mean(tuple(value.control_margin_advantage for value in values)),
        "mean_control_adjusted_margin_advantage": _mean(adjusted),
        "positive_adjusted_count": positive,
        "negative_adjusted_count": negative,
        "zero_adjusted_count": zero,
    }
    return MidDevPrimaryLengthSummary(
        target_length,
        len(values),
        payload["mean_watermarked_margin_advantage"],
        payload["mean_control_margin_advantage"],
        payload["mean_control_adjusted_margin_advantage"],
        positive,
        negative,
        zero,
        sha256_json(payload),
    )


def _threshold_registry_hash(rows: Sequence[MidDevScoredPlanRow]) -> str:
    entries = tuple(
        sorted(
            {
                (row.target_length, row.threshold_hash, row.threshold_value)
                for row in rows
            }
        )
    )
    if {value[0] for value in entries} != set(MID_DEV_PRIMARY_TARGET_LENGTHS):
        raise ValueError("primary inference requires threshold bindings for 128 and 256")
    if len(entries) != 2:
        raise ValueError("primary inference found multiple thresholds within a length stratum")
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
    threshold_registry_hash = _threshold_registry_hash(relevant)
    grouped: dict[str, list[MidDevScoredPlanRow]] = {}
    for row in relevant:
        grouped.setdefault(row.source_group_id, []).append(row)
    if len(grouped) != 36:
        raise ValueError("primary inference requires all 36 planned MidDev source groups")
    contrasts: list[MidDevPrimarySourceContrast] = []
    excluded: list[str] = []
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
        "threshold_registry_hash": threshold_registry_hash,
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
        threshold_registry_hash,
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
