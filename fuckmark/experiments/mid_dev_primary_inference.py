from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .._validation import require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .mid_dev_context_survival import (
    MID_DEV_BUDGETS,
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
    MidDevScoredRow,
    SourceGroupedControlAdjustedComparison,
    source_grouped_control_adjusted_comparison,
)


MID_DEV_PRIMARY_RANDOM_COMPARISON_VERSION = "mid-dev-primary-random-control-adjusted-v1"


@dataclass(frozen=True, slots=True)
class PrimaryRandomControlAdjustedComparison:
    algorithm_version: str
    detector_identity_hash: str
    threshold_hash: str
    comparison_condition: MidDevCondition
    budget: int
    random_replicates_per_source_label: int
    source_group_count: int
    core_comparison_hash: str
    primary_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_PRIMARY_RANDOM_COMPARISON_VERSION:
            raise ValueError("unsupported MidDev primary comparison version")
        require_sha256("detector_identity_hash", self.detector_identity_hash)
        require_sha256("threshold_hash", self.threshold_hash)
        if not isinstance(self.comparison_condition, MidDevCondition):
            raise TypeError("comparison_condition must be a MidDevCondition")
        if self.comparison_condition in {
            MidDevCondition.RANDOM_SAFE,
            MidDevCondition.NO_OP,
        }:
            raise ValueError("primary comparison condition must be a deterministic edit policy")
        require_int("budget", self.budget)
        if self.budget not in MID_DEV_BUDGETS:
            raise ValueError("primary comparison budget is not frozen")
        require_int(
            "random_replicates_per_source_label",
            self.random_replicates_per_source_label,
        )
        if self.random_replicates_per_source_label != MID_DEV_RANDOM_REPLICATES:
            raise ValueError("primary comparison requires all sixteen random replicates")
        require_int("source_group_count", self.source_group_count)
        if self.source_group_count < 32:
            raise ValueError("primary comparison requires at least 32 independent sources")
        require_sha256("core_comparison_hash", self.core_comparison_hash)
        require_sha256("primary_hash", self.primary_hash)
        if self.primary_hash != sha256_json(self.payload()):
            raise ValueError("primary_hash does not match primary comparison payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "comparison_condition": self.comparison_condition.value,
            "budget": self.budget,
            "random_replicates_per_source_label": self.random_replicates_per_source_label,
            "source_group_count": self.source_group_count,
            "core_comparison_hash": self.core_comparison_hash,
        }


def _validate_primary_rows(
    rows: Sequence[MidDevScoredRow],
    *,
    comparison_condition: MidDevCondition,
    budget: int,
) -> tuple[str, str, int]:
    if comparison_condition in {MidDevCondition.RANDOM_SAFE, MidDevCondition.NO_OP}:
        raise ValueError("primary comparison requires a deterministic comparison policy")
    relevant = tuple(
        row
        for row in rows
        if row.budget == budget
        and row.condition in {MidDevCondition.RANDOM_SAFE, comparison_condition}
    )
    detector_hashes = {row.detector_identity_hash for row in relevant}
    threshold_hashes = {row.threshold_hash for row in relevant}
    if len(detector_hashes) != 1 or len(threshold_hashes) != 1:
        raise ValueError("primary MidDev comparison cannot mix detector identities or thresholds")

    grouped: dict[tuple[str, WatermarkLabel], list[MidDevScoredRow]] = {}
    for row in relevant:
        grouped.setdefault((row.source_group_id, row.source_label), []).append(row)
    source_groups = {source_group_id for source_group_id, _ in grouped}
    if len(source_groups) < 32:
        raise ValueError("primary comparison requires at least 32 independent source groups")
    for source_group_id in source_groups:
        if (source_group_id, WatermarkLabel.WATERMARKED) not in grouped:
            raise ValueError("primary comparison is missing a watermarked source row set")
        if (source_group_id, WatermarkLabel.UNWATERMARKED) not in grouped:
            raise ValueError("primary comparison is missing a matched control row set")

    for values in grouped.values():
        random_rows = tuple(
            row for row in values if row.condition is MidDevCondition.RANDOM_SAFE
        )
        comparison_rows = tuple(
            row for row in values if row.condition is comparison_condition
        )
        if len(random_rows) != MID_DEV_RANDOM_REPLICATES:
            raise ValueError("primary comparison requires sixteen random replicates per source/label")
        if {row.replicate for row in random_rows} != set(range(MID_DEV_RANDOM_REPLICATES)):
            raise ValueError("primary comparison random replicate IDs are incomplete or duplicated")
        if len(comparison_rows) != 1 or comparison_rows[0].replicate != 0:
            raise ValueError("primary deterministic comparison must have one row per source/label")

    return next(iter(detector_hashes)), next(iter(threshold_hashes)), len(source_groups)


def primary_random_control_adjusted_comparison(
    rows: Sequence[MidDevScoredRow],
    *,
    comparison_condition: MidDevCondition,
    budget: int,
    bootstrap_replicates: int = 10_000,
    bootstrap_seed: int = 0x4D4944444556,
) -> tuple[
    PrimaryRandomControlAdjustedComparison,
    SourceGroupedControlAdjustedComparison,
]:
    detector_identity_hash, threshold_hash, source_group_count = _validate_primary_rows(
        rows,
        comparison_condition=comparison_condition,
        budget=budget,
    )
    core = source_grouped_control_adjusted_comparison(
        rows,
        comparison_condition=comparison_condition,
        baseline_condition=MidDevCondition.RANDOM_SAFE,
        budget=budget,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )
    payload = {
        "algorithm_version": MID_DEV_PRIMARY_RANDOM_COMPARISON_VERSION,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold_hash,
        "comparison_condition": comparison_condition.value,
        "budget": budget,
        "random_replicates_per_source_label": MID_DEV_RANDOM_REPLICATES,
        "source_group_count": source_group_count,
        "core_comparison_hash": core.comparison_hash,
    }
    return (
        PrimaryRandomControlAdjustedComparison(
            MID_DEV_PRIMARY_RANDOM_COMPARISON_VERSION,
            detector_identity_hash,
            threshold_hash,
            comparison_condition,
            budget,
            MID_DEV_RANDOM_REPLICATES,
            source_group_count,
            core.comparison_hash,
            sha256_json(payload),
        ),
        core,
    )
