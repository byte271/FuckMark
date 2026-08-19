from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .mid_dev_context_survival import SUCCESS, MidDevCondition
from .mid_dev_scoring import MidDevScoredPlanRow


MID_DEV_PRIMARY_INFERENCE_V2 = "mid-dev-primary-realized-cost-v2"
MID_DEV_MINIMUM_MATCHED_RANDOM_REPLICATES = 8
MID_DEV_PRIMARY_BOOTSTRAP_REPLICATES = 10_000


@dataclass(frozen=True, slots=True)
class MidDevPrimarySourceContrast:
    source_group_id: str
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
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        require_sha256("contrast_hash", self.contrast_hash)
        if self.contrast_hash != sha256_json(self.payload()):
            raise ValueError("contrast_hash does not match MidDev source contrast")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
            "source_group_id": self.source_group_id,
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
class MidDevPrimaryInferenceResult:
    detector_identity_hash: str
    threshold_hash: str
    deterministic_condition: MidDevCondition
    budget: int
    planned_source_group_count: int
    eligible_source_group_count: int
    excluded_source_group_ids: tuple[str, ...]
    source_contrasts: tuple[MidDevPrimarySourceContrast, ...]
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
        require_sha256("threshold_hash", self.threshold_hash)
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
        for name in (
            "mean_watermarked_margin_advantage",
            "mean_control_margin_advantage",
            "mean_control_adjusted_margin_advantage",
            "bootstrap_lower",
            "bootstrap_upper",
            "two_sided_sign_p_value",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
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
            "threshold_hash": self.threshold_hash,
            "deterministic_condition": self.deterministic_condition.value,
            "budget": self.budget,
            "planned_source_group_count": self.planned_source_group_count,
            "eligible_source_group_count": self.eligible_source_group_count,
            "excluded_source_group_ids": self.excluded_source_group_ids,
            "source_contrast_hashes": tuple(value.contrast_hash for value in self.source_contrasts),
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
) -> tuple[MidDevScoredPlanRow, ...]:
    return tuple(
        row
        for row in rows
        if row.source_label is label
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
    if wm.realized_edit_cost != control.realized_edit_cost:
        return None
    realized_cost = wm.realized_edit_cost
    wm_random = _matched_random_rows(
        rows,
        label=WatermarkLabel.WATERMARKED,
        budget=budget,
        realized_edit_cost=realized_cost,
    )
    control_random = _matched_random_rows(
        rows,
        label=WatermarkLabel.UNWATERMARKED,
        budget=budget,
        realized_edit_cost=realized_cost,
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


def primary_realized_cost_inference(
    rows: Sequence[MidDevScoredPlanRow],
    *,
    deterministic_condition: MidDevCondition,
    budget: int,
    bootstrap_replicates: int = MID_DEV_PRIMARY_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = 0x4D494444455632,
) -> MidDevPrimaryInferenceResult:
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
    threshold_hashes = {row.threshold_hash for row in relevant}
    if len(detector_hashes) != 1 or len(threshold_hashes) != 1:
        raise ValueError("primary inference cannot mix detector identities or thresholds")
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
    adjusted = tuple(value.control_adjusted_margin_advantage for value in contrasts)
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
    materialized = tuple(contrasts)
    payload = {
        "algorithm_version": MID_DEV_PRIMARY_INFERENCE_V2,
        "detector_identity_hash": next(iter(detector_hashes)),
        "threshold_hash": next(iter(threshold_hashes)),
        "deterministic_condition": deterministic_condition.value,
        "budget": budget,
        "planned_source_group_count": 36,
        "eligible_source_group_count": count,
        "excluded_source_group_ids": tuple(excluded),
        "source_contrast_hashes": tuple(value.contrast_hash for value in materialized),
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
        next(iter(threshold_hashes)),
        deterministic_condition,
        budget,
        36,
        count,
        tuple(excluded),
        materialized,
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
