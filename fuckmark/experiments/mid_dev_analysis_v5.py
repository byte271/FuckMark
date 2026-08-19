from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Sequence

from .._validation import require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from ..search.normalized_random_safe import MATCHED_COST_SUCCESS
from ..search.visible_cost_budget import VisibleCostTier, policy_for_tier
from .mid_dev_analysis import MID_DEV_FROZEN_PRIMARY_CELLS, MID_DEV_FROZEN_PRIMARY_CELLS_HASH
from .mid_dev_analysis_contract_v5 import (
    FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT,
    MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS,
    source_level_bootstrap_mean,
)
from .mid_dev_plan_v5 import MidDevDevelopmentPlanV5, MidDevNormalizedPlanner
from .mid_dev_pre_run_lock import (
    PRE_RUN_BOOTSTRAP_SEED_BASE,
    PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE,
)
from .mid_dev_scoring_contracts import MidDevCondition, SUCCESS
from .mid_dev_v5_builder import MidDevNormalizedTraceArtifact
from .mid_dev_v5_geometry_audit import (
    MID_DEV_V5_REPETITION_MASK_GROWTH_CAP,
    MidDevV5GeometryAuditArtifact,
)
from .mid_dev_v5_rule_usage import MidDevV5RuleUsageArtifact
from .mid_dev_v5_scoring import (
    MidDevV5ScoredRow,
    MidDevV5ScoredRowKind,
    MidDevV5ScoringArtifact,
)


MID_DEV_V5_ANALYSIS_VERSION = "mid-dev-v5-source-level-analysis-v1"
MID_DEV_V5_CELL_SUMMARY_VERSION = "mid-dev-v5-cell-summary-v1"
MID_DEV_V5_SOURCE_EFFECT_VERSION = "mid-dev-v5-source-effect-v1"
MID_DEV_V5_MATCHED_COMPARISON_VERSION = "mid-dev-v5-matched-comparison-v1"
MID_DEV_V5_SATURATION_VERSION = "mid-dev-v5-saturation-v1"
MID_DEV_V5_HUMAN_AUDIT_PENDING = "PENDING"
MID_DEV_V5_CELL_ELIGIBLE = "ELIGIBLE"
MID_DEV_V5_CELL_INELIGIBLE = "INELIGIBLE"


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty sequence")
    return sum(values) / len(values)


def _margin_drop(row: MidDevV5ScoredRow) -> float:
    return row.pristine_score.margin - row.transformed_score.margin


def _cell_status(count: int) -> str:
    return (
        MID_DEV_V5_CELL_ELIGIBLE
        if count >= MID_DEV_V5_MINIMUM_ELIGIBLE_SOURCE_GROUPS
        else MID_DEV_V5_CELL_INELIGIBLE
    )


@dataclass(frozen=True, slots=True)
class MidDevV5SourceEffect:
    source_group_id: str
    cell_id: str
    target_length: int
    watermarked_random_count: int
    control_random_count: int
    watermarked_margin_advantage: float
    control_margin_advantage: float
    control_adjusted_margin_advantage: float
    watermarked_rif_advantage: float
    control_rif_advantage: float
    control_adjusted_rif_advantage: float
    effect_hash: str

    def __post_init__(self) -> None:
        if not self.source_group_id or not self.cell_id:
            raise ValueError("source_group_id/cell_id must be non-empty")
        require_int("target_length", self.target_length)
        if self.target_length not in (128, 256):
            raise ValueError("target_length must be 128 or 256")
        for name in ("watermarked_random_count", "control_random_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 8 or value > 16:
                raise ValueError("matched source effect requires 8..16 random replicates per label")
        for name in (
            "watermarked_margin_advantage",
            "control_margin_advantage",
            "control_adjusted_margin_advantage",
            "watermarked_rif_advantage",
            "control_rif_advantage",
            "control_adjusted_rif_advantage",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        require_sha256("effect_hash", self.effect_hash)
        if self.effect_hash != sha256_json(self.payload()):
            raise ValueError("source effect hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevV5SourceEffect":
        payload = {"algorithm_version": MID_DEV_V5_SOURCE_EFFECT_VERSION, **values}
        return cls(**values, effect_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_SOURCE_EFFECT_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "effect_hash"},
        }


@dataclass(frozen=True, slots=True)
class MidDevV5CellSummary:
    cell_id: str
    status: str
    planned_source_group_count: int
    eligible_source_group_count: int
    excluded_source_group_ids: tuple[str, ...]
    mean_watermarked_margin_drop: float | None
    mean_control_margin_drop: float | None
    mean_control_adjusted_margin_drop: float | None
    mean_watermarked_rif: float | None
    mean_control_rif: float | None
    mean_watermarked_ncf: float | None
    mean_control_ncf: float | None
    mean_watermarked_vdr: float | None
    mean_control_vdr: float | None
    pristine_watermarked_tpr: float | None
    transformed_watermarked_tpr: float | None
    transformed_control_positive_rate: float | None
    summary_hash: str

    def __post_init__(self) -> None:
        if not self.cell_id:
            raise ValueError("cell_id must be non-empty")
        if self.status not in {MID_DEV_V5_CELL_ELIGIBLE, MID_DEV_V5_CELL_INELIGIBLE}:
            raise ValueError("unsupported cell status")
        if self.planned_source_group_count != 36:
            raise ValueError("cell summary must start from 36 planned source groups")
        if not 0 <= self.eligible_source_group_count <= 36:
            raise ValueError("eligible source count out of range")
        if len(self.excluded_source_group_ids) != 36 - self.eligible_source_group_count:
            raise ValueError("cell source partition mismatch")
        if len(set(self.excluded_source_group_ids)) != len(self.excluded_source_group_ids):
            raise ValueError("excluded source IDs must be unique")
        if self.status != _cell_status(self.eligible_source_group_count):
            raise ValueError("cell status does not match eligible source count")
        metric_names = (
            "mean_watermarked_margin_drop",
            "mean_control_margin_drop",
            "mean_control_adjusted_margin_drop",
            "mean_watermarked_rif",
            "mean_control_rif",
            "mean_watermarked_ncf",
            "mean_control_ncf",
            "mean_watermarked_vdr",
            "mean_control_vdr",
            "pristine_watermarked_tpr",
            "transformed_watermarked_tpr",
            "transformed_control_positive_rate",
        )
        if self.eligible_source_group_count == 0:
            if any(getattr(self, name) is not None for name in metric_names):
                raise ValueError("empty cell cannot report metrics")
        else:
            for name in metric_names:
                value = getattr(self, name)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise TypeError(f"{name} must be finite when groups are available")
            for name in (
                "mean_watermarked_rif",
                "mean_control_rif",
                "mean_watermarked_ncf",
                "mean_control_ncf",
                "pristine_watermarked_tpr",
                "transformed_watermarked_tpr",
                "transformed_control_positive_rate",
            ):
                if not 0.0 <= float(getattr(self, name)) <= 1.0:
                    raise ValueError(f"{name} must be in [0,1]")
            if self.mean_watermarked_vdr < 0.0 or self.mean_control_vdr < 0.0:
                raise ValueError("mean VDR must be non-negative")
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("cell summary hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevV5CellSummary":
        payload = {"algorithm_version": MID_DEV_V5_CELL_SUMMARY_VERSION, **values}
        return cls(**values, summary_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_CELL_SUMMARY_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "summary_hash"},
        }


@dataclass(frozen=True, slots=True)
class MidDevV5MatchedComparison:
    cell_id: str
    status: str
    planned_source_group_count: int
    eligible_source_group_count: int
    excluded_source_group_ids: tuple[str, ...]
    source_effects: tuple[MidDevV5SourceEffect, ...]
    mean_control_adjusted_margin_advantage: float | None
    margin_bootstrap_lower: float | None
    margin_bootstrap_upper: float | None
    mean_control_adjusted_rif_advantage: float | None
    rif_bootstrap_lower: float | None
    rif_bootstrap_upper: float | None
    bootstrap_replicates: int
    comparison_hash: str

    def __post_init__(self) -> None:
        if not self.cell_id:
            raise ValueError("comparison cell_id must be non-empty")
        if self.status not in {MID_DEV_V5_CELL_ELIGIBLE, MID_DEV_V5_CELL_INELIGIBLE}:
            raise ValueError("unsupported comparison status")
        if self.planned_source_group_count != 36:
            raise ValueError("comparison must start from 36 planned source groups")
        if self.eligible_source_group_count != len(self.source_effects):
            raise ValueError("comparison source-effect count mismatch")
        if len(self.excluded_source_group_ids) != 36 - self.eligible_source_group_count:
            raise ValueError("comparison source partition mismatch")
        if self.status != _cell_status(self.eligible_source_group_count):
            raise ValueError("comparison status does not match source count")
        if len({value.source_group_id for value in self.source_effects}) != len(self.source_effects):
            raise ValueError("comparison source effects must be unique")
        inferential = (
            self.mean_control_adjusted_margin_advantage,
            self.margin_bootstrap_lower,
            self.margin_bootstrap_upper,
            self.mean_control_adjusted_rif_advantage,
            self.rif_bootstrap_lower,
            self.rif_bootstrap_upper,
        )
        if self.status == MID_DEV_V5_CELL_ELIGIBLE:
            if self.bootstrap_replicates != 10_000:
                raise ValueError("eligible comparison must use 10,000 source-level bootstrap replicates")
            if any(value is None or not math.isfinite(float(value)) for value in inferential):
                raise ValueError("eligible comparison requires finite inferential summaries")
            if self.margin_bootstrap_lower > self.margin_bootstrap_upper:
                raise ValueError("margin bootstrap interval reversed")
            if self.rif_bootstrap_lower > self.rif_bootstrap_upper:
                raise ValueError("RIF bootstrap interval reversed")
        else:
            if self.bootstrap_replicates != 0 or any(value is not None for value in inferential):
                raise ValueError("ineligible comparison cannot report inferential summaries")
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self.payload()):
            raise ValueError("comparison hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevV5MatchedComparison":
        payload = {
            "algorithm_version": MID_DEV_V5_MATCHED_COMPARISON_VERSION,
            **{
                key: (tuple(value.effect_hash for value in value) if key == "source_effects" else value)
                for key, value in values.items()
            },
        }
        return cls(**values, comparison_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_MATCHED_COMPARISON_VERSION,
            "cell_id": self.cell_id,
            "status": self.status,
            "planned_source_group_count": self.planned_source_group_count,
            "eligible_source_group_count": self.eligible_source_group_count,
            "excluded_source_group_ids": self.excluded_source_group_ids,
            "source_effects": tuple(value.effect_hash for value in self.source_effects),
            "mean_control_adjusted_margin_advantage": self.mean_control_adjusted_margin_advantage,
            "margin_bootstrap_lower": self.margin_bootstrap_lower,
            "margin_bootstrap_upper": self.margin_bootstrap_upper,
            "mean_control_adjusted_rif_advantage": self.mean_control_adjusted_rif_advantage,
            "rif_bootstrap_lower": self.rif_bootstrap_lower,
            "rif_bootstrap_upper": self.rif_bootstrap_upper,
            "bootstrap_replicates": self.bootstrap_replicates,
        }


@dataclass(frozen=True, slots=True)
class MidDevV5SaturationReport:
    evaluable: bool
    budgets: tuple[int, ...]
    eligible_row_counts: tuple[int, ...]
    median_rif_by_budget: tuple[float | None, ...]
    median_character_edit_rate_by_budget: tuple[float | None, ...]
    consecutive_small_improvement_count: int
    saturation_triggered: bool
    report_hash: str

    def __post_init__(self) -> None:
        if type(self.evaluable) is not bool or type(self.saturation_triggered) is not bool:
            raise TypeError("saturation flags must be bool")
        if self.budgets != (1, 2, 4, 6):
            raise ValueError("saturation budgets drifted")
        if len(self.eligible_row_counts) != 4 or len(self.median_rif_by_budget) != 4 or len(self.median_character_edit_rate_by_budget) != 4:
            raise ValueError("saturation vectors must contain four budgets")
        for value in self.eligible_row_counts:
            require_int("eligible_row_count", value)
            if value < 0:
                raise ValueError("eligible row counts must be non-negative")
        require_int("consecutive_small_improvement_count", self.consecutive_small_improvement_count)
        if self.consecutive_small_improvement_count < 0:
            raise ValueError("consecutive small-improvement count must be non-negative")
        if self.evaluable != all(value > 0 for value in self.eligible_row_counts):
            raise ValueError("saturation evaluable flag does not match row availability")
        if self.evaluable:
            if any(value is None for value in self.median_rif_by_budget + self.median_character_edit_rate_by_budget):
                raise ValueError("evaluable saturation report requires all medians")
            if self.saturation_triggered != (self.consecutive_small_improvement_count >= 2):
                raise ValueError("saturation trigger does not reproduce")
        else:
            if self.saturation_triggered or self.consecutive_small_improvement_count:
                raise ValueError("unevaluable saturation report cannot trigger")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("saturation report hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevV5SaturationReport":
        payload = {"algorithm_version": MID_DEV_V5_SATURATION_VERSION, **values}
        return cls(**values, report_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_SATURATION_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "report_hash"},
        }


@dataclass(frozen=True, slots=True)
class MidDevV5AnalysisArtifact:
    development_plan_hash: str
    scoring_artifact_hash: str
    geometry_audit_hash: str
    rule_usage_artifact_hash: str
    normalized_trace_artifact_hash: str
    detector_identity_hash: str
    threshold_registry_hash: str
    analysis_contract_hash: str
    legacy_primary_cells_hash: str
    cell_summaries: tuple[MidDevV5CellSummary, ...]
    matched_comparisons: tuple[MidDevV5MatchedComparison, ...]
    saturation_report: MidDevV5SaturationReport
    rule_usage_counts: tuple[tuple[str, int], ...]
    human_audit_sampling_rule: str
    human_audit_status: str
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "development_plan_hash",
            "scoring_artifact_hash",
            "geometry_audit_hash",
            "rule_usage_artifact_hash",
            "normalized_trace_artifact_hash",
            "detector_identity_hash",
            "threshold_registry_hash",
            "analysis_contract_hash",
            "legacy_primary_cells_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.analysis_contract_hash != FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT.contract_hash:
            raise ValueError("analysis contract hash drifted")
        if self.legacy_primary_cells_hash != MID_DEV_FROZEN_PRIMARY_CELLS_HASH:
            raise ValueError("legacy primary cell hash drifted")
        expected_cells = {
            *(f"LEGACY_{condition.value}_B{budget}" for condition, budget in MID_DEV_FROZEN_PRIMARY_CELLS),
            "BEAM_V2_STRICT",
            "BEAM_V2_RELAXED",
            "RANDOM_SAFE_MATCHED_COST_STRICT",
            "RANDOM_SAFE_MATCHED_COST_RELAXED",
        }
        if {value.cell_id for value in self.cell_summaries} != expected_cells:
            raise ValueError("analysis must report all six legacy and four normalized cells")
        expected_comparisons = {
            *(f"LEGACY_{condition.value}_B{budget}" for condition, budget in MID_DEV_FROZEN_PRIMARY_CELLS),
            "MATCHED_BEAM_V2_STRICT",
            "MATCHED_BEAM_V2_RELAXED",
        }
        if {value.cell_id for value in self.matched_comparisons} != expected_comparisons:
            raise ValueError("analysis must report all frozen matched comparisons")
        if tuple(sorted(self.rule_usage_counts)) != self.rule_usage_counts:
            raise ValueError("rule usage counts must be sorted")
        if self.human_audit_sampling_rule != PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE:
            raise ValueError("human audit sampling rule drifted")
        if self.human_audit_status != MID_DEV_V5_HUMAN_AUDIT_PENDING:
            raise ValueError("automated analysis cannot self-approve human audit")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("analysis artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_ANALYSIS_VERSION,
            "development_plan_hash": self.development_plan_hash,
            "scoring_artifact_hash": self.scoring_artifact_hash,
            "geometry_audit_hash": self.geometry_audit_hash,
            "rule_usage_artifact_hash": self.rule_usage_artifact_hash,
            "normalized_trace_artifact_hash": self.normalized_trace_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_registry_hash": self.threshold_registry_hash,
            "analysis_contract_hash": self.analysis_contract_hash,
            "legacy_primary_cells_hash": self.legacy_primary_cells_hash,
            "cell_summary_hashes": tuple(value.summary_hash for value in self.cell_summaries),
            "matched_comparison_hashes": tuple(value.comparison_hash for value in self.matched_comparisons),
            "saturation_report_hash": self.saturation_report.report_hash,
            "rule_usage_counts": self.rule_usage_counts,
            "human_audit_sampling_rule": self.human_audit_sampling_rule,
            "human_audit_status": self.human_audit_status,
        }


def _visible_fidelity_passed(row: MidDevV5ScoredRow, tier: VisibleCostTier) -> bool:
    policy = policy_for_tier(tier)
    if row.word_edit_rate > policy.word_edit_rate_max or row.character_edit_rate > policy.character_edit_rate_max:
        return False
    if policy.length_ratio_min is not None and not policy.length_ratio_min <= row.length_ratio <= policy.length_ratio_max:
        return False
    return True


def _auto_eligible(
    row: MidDevV5ScoredRow,
    geometry_by_scored_hash,
    *,
    tier: VisibleCostTier | None,
) -> bool:
    geometry = geometry_by_scored_hash[row.row_hash]
    if geometry.valid_denominator_ratio < 0.90:
        return False
    if geometry.repetition_mask_delta > MID_DEV_V5_REPETITION_MASK_GROWTH_CAP:
        return False
    if row.protected_span_violation_count != 0 or not row.hard_invariant_passed:
        return False
    if tier is not None and not _visible_fidelity_passed(row, tier):
        return False
    return True


def _group_value(rows: Sequence[MidDevV5ScoredRow]) -> dict[str, float]:
    return {
        "margin_drop": _mean(tuple(_margin_drop(row) for row in rows)),
        "rif": _mean(tuple(row.residual_inherited_fraction for row in rows)),
        "ncf": _mean(tuple(row.new_context_opportunity_fraction for row in rows)),
        "vdr": _mean(tuple(row.valid_denominator_ratio for row in rows)),
        "pristine_detected": _mean(tuple(float(row.pristine_score.detected) for row in rows)),
        "transformed_detected": _mean(tuple(float(row.transformed_score.detected) for row in rows)),
    }


def _make_cell_summary(cell_id: str, group_pairs: Sequence[tuple[dict[str, float], dict[str, float]]], excluded: Sequence[str]) -> MidDevV5CellSummary:
    pairs = tuple(group_pairs)
    count = len(pairs)
    if count:
        wm = tuple(pair[0] for pair in pairs)
        control = tuple(pair[1] for pair in pairs)
        metrics = {
            "mean_watermarked_margin_drop": _mean(tuple(value["margin_drop"] for value in wm)),
            "mean_control_margin_drop": _mean(tuple(value["margin_drop"] for value in control)),
            "mean_control_adjusted_margin_drop": _mean(tuple(wm[i]["margin_drop"] - control[i]["margin_drop"] for i in range(count))),
            "mean_watermarked_rif": _mean(tuple(value["rif"] for value in wm)),
            "mean_control_rif": _mean(tuple(value["rif"] for value in control)),
            "mean_watermarked_ncf": _mean(tuple(value["ncf"] for value in wm)),
            "mean_control_ncf": _mean(tuple(value["ncf"] for value in control)),
            "mean_watermarked_vdr": _mean(tuple(value["vdr"] for value in wm)),
            "mean_control_vdr": _mean(tuple(value["vdr"] for value in control)),
            "pristine_watermarked_tpr": _mean(tuple(value["pristine_detected"] for value in wm)),
            "transformed_watermarked_tpr": _mean(tuple(value["transformed_detected"] for value in wm)),
            "transformed_control_positive_rate": _mean(tuple(value["transformed_detected"] for value in control)),
        }
    else:
        metrics = {name: None for name in (
            "mean_watermarked_margin_drop",
            "mean_control_margin_drop",
            "mean_control_adjusted_margin_drop",
            "mean_watermarked_rif",
            "mean_control_rif",
            "mean_watermarked_ncf",
            "mean_control_ncf",
            "mean_watermarked_vdr",
            "mean_control_vdr",
            "pristine_watermarked_tpr",
            "transformed_watermarked_tpr",
            "transformed_control_positive_rate",
        )}
    return MidDevV5CellSummary.create(
        cell_id=cell_id,
        status=_cell_status(count),
        planned_source_group_count=36,
        eligible_source_group_count=count,
        excluded_source_group_ids=tuple(sorted(excluded)),
        **metrics,
    )


def _make_comparison(cell_id: str, effects: Sequence[MidDevV5SourceEffect], excluded: Sequence[str], seed: int) -> MidDevV5MatchedComparison:
    materialized = tuple(sorted(effects, key=lambda value: value.source_group_id))
    count = len(materialized)
    status = _cell_status(count)
    if status == MID_DEV_V5_CELL_ELIGIBLE:
        margin_values = tuple(value.control_adjusted_margin_advantage for value in materialized)
        rif_values = tuple(value.control_adjusted_rif_advantage for value in materialized)
        margin_mean, margin_lower, margin_upper = source_level_bootstrap_mean(margin_values, seed=seed)
        rif_mean, rif_lower, rif_upper = source_level_bootstrap_mean(rif_values, seed=seed ^ 0x524946)
        metrics = {
            "mean_control_adjusted_margin_advantage": margin_mean,
            "margin_bootstrap_lower": margin_lower,
            "margin_bootstrap_upper": margin_upper,
            "mean_control_adjusted_rif_advantage": rif_mean,
            "rif_bootstrap_lower": rif_lower,
            "rif_bootstrap_upper": rif_upper,
            "bootstrap_replicates": 10_000,
        }
    else:
        metrics = {
            "mean_control_adjusted_margin_advantage": None,
            "margin_bootstrap_lower": None,
            "margin_bootstrap_upper": None,
            "mean_control_adjusted_rif_advantage": None,
            "rif_bootstrap_lower": None,
            "rif_bootstrap_upper": None,
            "bootstrap_replicates": 0,
        }
    return MidDevV5MatchedComparison.create(
        cell_id=cell_id,
        status=status,
        planned_source_group_count=36,
        eligible_source_group_count=count,
        excluded_source_group_ids=tuple(sorted(excluded)),
        source_effects=materialized,
        **metrics,
    )


def _normalized_rows_by_group(scoring: MidDevV5ScoringArtifact) -> dict[str, tuple[MidDevV5ScoredRow, ...]]:
    grouped: dict[str, list[MidDevV5ScoredRow]] = {}
    for row in scoring.rows:
        if row.row_kind is MidDevV5ScoredRowKind.NORMALIZED:
            grouped.setdefault(row.source_group_id, []).append(row)
    if len(grouped) != 36:
        raise ValueError("normalized analysis requires all 36 source groups")
    return {key: tuple(value) for key, value in grouped.items()}


def _normalized_beam(rows, label: WatermarkLabel, tier: VisibleCostTier, geometry_map):
    selected = tuple(
        row for row in rows
        if row.source_label == label.value
        and row.planner_or_condition == MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2.value
        and row.tier == tier.value
        and row.replicate == 0
        and _auto_eligible(row, geometry_map, tier=tier)
    )
    return selected[0] if len(selected) == 1 else None


def _normalized_random(rows, label: WatermarkLabel, tier: VisibleCostTier, beam, geometry_map, plan_map, trace_status):
    if beam is None:
        return ()
    beam_plan = plan_map[beam.plan_row_hash]
    values = []
    for row in rows:
        if row.source_label != label.value or row.planner_or_condition != MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST.value or row.tier != tier.value:
            continue
        plan_row = plan_map[row.plan_row_hash]
        if trace_status.get(row.selection_trace_hash) != MATCHED_COST_SUCCESS:
            continue
        if plan_row.realized_operation_count != beam_plan.realized_operation_count:
            continue
        if not _auto_eligible(row, geometry_map, tier=tier):
            continue
        if row.word_edit_rate > beam.word_edit_rate or row.character_edit_rate > beam.character_edit_rate:
            continue
        if row.token_edit_distance > beam.token_edit_distance:
            continue
        values.append(row)
    return tuple(values)


def _normalized_cell_and_comparison(scoring, plan, traces, geometry_map, tier: VisibleCostTier, planner: MidDevNormalizedPlanner, seed: int):
    grouped = _normalized_rows_by_group(scoring)
    plan_map = {row.row_hash: row for row in plan.normalized_rows}
    trace_status = {trace.trace_hash: trace.status for trace in traces.traces}
    pairs = []
    effects = []
    excluded = []
    for group_id in sorted(grouped):
        rows = grouped[group_id]
        wm_beam = _normalized_beam(rows, WatermarkLabel.WATERMARKED, tier, geometry_map)
        control_beam = _normalized_beam(rows, WatermarkLabel.UNWATERMARKED, tier, geometry_map)
        if wm_beam is None or control_beam is None or wm_beam.target_length != control_beam.target_length:
            excluded.append(group_id)
            continue
        if planner is MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2:
            pairs.append((_group_value((wm_beam,)), _group_value((control_beam,))))
            continue
        wm_random = _normalized_random(rows, WatermarkLabel.WATERMARKED, tier, wm_beam, geometry_map, plan_map, trace_status)
        control_random = _normalized_random(rows, WatermarkLabel.UNWATERMARKED, tier, control_beam, geometry_map, plan_map, trace_status)
        if len(wm_random) < 8 or len(control_random) < 8:
            excluded.append(group_id)
            continue
        pairs.append((_group_value(wm_random), _group_value(control_random)))
        wm_margin = _margin_drop(wm_beam) - _mean(tuple(_margin_drop(row) for row in wm_random))
        control_margin = _margin_drop(control_beam) - _mean(tuple(_margin_drop(row) for row in control_random))
        wm_rif = _mean(tuple(row.residual_inherited_fraction for row in wm_random)) - wm_beam.residual_inherited_fraction
        control_rif = _mean(tuple(row.residual_inherited_fraction for row in control_random)) - control_beam.residual_inherited_fraction
        effects.append(MidDevV5SourceEffect.create(
            source_group_id=group_id,
            cell_id=f"MATCHED_BEAM_V2_{tier.value}",
            target_length=wm_beam.target_length,
            watermarked_random_count=len(wm_random),
            control_random_count=len(control_random),
            watermarked_margin_advantage=wm_margin,
            control_margin_advantage=control_margin,
            control_adjusted_margin_advantage=wm_margin - control_margin,
            watermarked_rif_advantage=wm_rif,
            control_rif_advantage=control_rif,
            control_adjusted_rif_advantage=wm_rif - control_rif,
        ))
    cell_id = (
        f"BEAM_V2_{tier.value}"
        if planner is MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2
        else f"RANDOM_SAFE_MATCHED_COST_{tier.value}"
    )
    summary = _make_cell_summary(cell_id, pairs, excluded)
    comparison = None
    if planner is MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST:
        comparison = _make_comparison(f"MATCHED_BEAM_V2_{tier.value}", effects, excluded, seed)
    return summary, comparison


def _legacy_rows_by_group(scoring: MidDevV5ScoringArtifact) -> dict[str, tuple[MidDevV5ScoredRow, ...]]:
    grouped: dict[str, list[MidDevV5ScoredRow]] = {}
    for row in scoring.rows:
        if row.row_kind is MidDevV5ScoredRowKind.LEGACY:
            grouped.setdefault(row.source_group_id, []).append(row)
    if len(grouped) != 36:
        raise ValueError("legacy analysis requires all 36 source groups")
    return {key: tuple(value) for key, value in grouped.items()}


def _legacy_deterministic(rows, label, condition, budget, geometry_map, plan_map):
    selected = []
    for row in rows:
        if row.source_label != label.value or row.planner_or_condition != condition.value or row.budget != budget or row.replicate != 0:
            continue
        plan_row = plan_map[row.plan_row_hash]
        if plan_row.status != SUCCESS or plan_row.operation_count <= 0:
            continue
        if not _auto_eligible(row, geometry_map, tier=None):
            continue
        selected.append(row)
    return selected[0] if len(selected) == 1 else None


def _legacy_random(rows, label, budget, realized_cost, target_length, geometry_map, plan_map):
    values = []
    for row in rows:
        if row.source_label != label.value or row.planner_or_condition != MidDevCondition.RANDOM_SAFE.value or row.budget != budget or row.target_length != target_length:
            continue
        plan_row = plan_map[row.plan_row_hash]
        if plan_row.status != SUCCESS or plan_row.operation_count != realized_cost:
            continue
        if not _auto_eligible(row, geometry_map, tier=None):
            continue
        values.append(row)
    return tuple(values)


def _legacy_cell_and_comparison(scoring, plan, geometry_map, condition: MidDevCondition, budget: int, seed: int):
    grouped = _legacy_rows_by_group(scoring)
    plan_map = {row.plan_row_hash: row for row in plan.legacy_plan.rows}
    pairs = []
    effects = []
    excluded = []
    for group_id in sorted(grouped):
        rows = grouped[group_id]
        wm = _legacy_deterministic(rows, WatermarkLabel.WATERMARKED, condition, budget, geometry_map, plan_map)
        control = _legacy_deterministic(rows, WatermarkLabel.UNWATERMARKED, condition, budget, geometry_map, plan_map)
        if wm is None or control is None:
            excluded.append(group_id)
            continue
        wm_plan = plan_map[wm.plan_row_hash]
        control_plan = plan_map[control.plan_row_hash]
        if wm_plan.operation_count != control_plan.operation_count or wm.target_length != control.target_length:
            excluded.append(group_id)
            continue
        pairs.append((_group_value((wm,)), _group_value((control,))))
        wm_random = _legacy_random(rows, WatermarkLabel.WATERMARKED, budget, wm_plan.operation_count, wm.target_length, geometry_map, plan_map)
        control_random = _legacy_random(rows, WatermarkLabel.UNWATERMARKED, budget, control_plan.operation_count, control.target_length, geometry_map, plan_map)
        if len(wm_random) < 8 or len(control_random) < 8:
            continue
        wm_margin = _margin_drop(wm) - _mean(tuple(_margin_drop(row) for row in wm_random))
        control_margin = _margin_drop(control) - _mean(tuple(_margin_drop(row) for row in control_random))
        wm_rif = _mean(tuple(row.residual_inherited_fraction for row in wm_random)) - wm.residual_inherited_fraction
        control_rif = _mean(tuple(row.residual_inherited_fraction for row in control_random)) - control.residual_inherited_fraction
        effects.append(MidDevV5SourceEffect.create(
            source_group_id=group_id,
            cell_id=f"LEGACY_{condition.value}_B{budget}",
            target_length=wm.target_length,
            watermarked_random_count=len(wm_random),
            control_random_count=len(control_random),
            watermarked_margin_advantage=wm_margin,
            control_margin_advantage=control_margin,
            control_adjusted_margin_advantage=wm_margin - control_margin,
            watermarked_rif_advantage=wm_rif,
            control_rif_advantage=control_rif,
            control_adjusted_rif_advantage=wm_rif - control_rif,
        ))
    effect_ids = {value.source_group_id for value in effects}
    comparison_excluded = tuple(sorted(set(grouped) - effect_ids))
    cell_id = f"LEGACY_{condition.value}_B{budget}"
    return (
        _make_cell_summary(cell_id, pairs, excluded),
        _make_comparison(cell_id, effects, comparison_excluded, seed),
    )


def _saturation_report(scoring, plan, geometry_map) -> MidDevV5SaturationReport:
    plan_map = {row.plan_row_hash: row for row in plan.legacy_plan.rows}
    budgets = (1, 2, 4, 6)
    counts = []
    med_rif = []
    med_char = []
    for budget in budgets:
        rows = []
        for row in scoring.rows:
            if row.row_kind is not MidDevV5ScoredRowKind.LEGACY:
                continue
            if row.planner_or_condition != MidDevCondition.CONTEXT_SURVIVAL_GREEDY.value or row.budget != budget or row.replicate != 0:
                continue
            plan_row = plan_map[row.plan_row_hash]
            if plan_row.status != SUCCESS or plan_row.operation_count <= 0:
                continue
            if not _auto_eligible(row, geometry_map, tier=None):
                continue
            rows.append(row)
        counts.append(len(rows))
        med_rif.append(None if not rows else float(median(value.residual_inherited_fraction for value in rows)))
        med_char.append(None if not rows else float(median(value.character_edit_rate for value in rows)))
    evaluable = all(value > 0 for value in counts)
    consecutive = 0
    best = 0
    if evaluable:
        for index in range(1, 4):
            improvement = med_rif[index - 1] - med_rif[index]
            higher_cost = med_char[index] > med_char[index - 1]
            if improvement < 0.01 and higher_cost:
                consecutive += 1
                best = max(best, consecutive)
            else:
                consecutive = 0
    return MidDevV5SaturationReport.create(
        evaluable=evaluable,
        budgets=budgets,
        eligible_row_counts=tuple(counts),
        median_rif_by_budget=tuple(med_rif),
        median_character_edit_rate_by_budget=tuple(med_char),
        consecutive_small_improvement_count=best if evaluable else 0,
        saturation_triggered=(best >= 2) if evaluable else False,
    )


def build_mid_dev_v5_analysis_artifact(
    plan: MidDevDevelopmentPlanV5,
    normalized_traces: MidDevNormalizedTraceArtifact,
    scoring: MidDevV5ScoringArtifact,
    geometry_audit: MidDevV5GeometryAuditArtifact,
    rule_usage: MidDevV5RuleUsageArtifact,
) -> MidDevV5AnalysisArtifact:
    if scoring.development_plan_hash != plan.plan_hash:
        raise ValueError("analysis scoring/plan mismatch")
    if scoring.normalized_trace_artifact_hash != normalized_traces.artifact_hash:
        raise ValueError("analysis scoring/normalized-trace mismatch")
    if geometry_audit.development_plan_hash != plan.plan_hash or geometry_audit.scoring_artifact_hash != scoring.artifact_hash:
        raise ValueError("analysis geometry audit binding mismatch")
    if rule_usage.development_plan_hash != plan.plan_hash or rule_usage.normalized_trace_artifact_hash != normalized_traces.artifact_hash:
        raise ValueError("analysis rule-usage binding mismatch")
    if geometry_audit.repetition_mask_growth_cap != MID_DEV_V5_REPETITION_MASK_GROWTH_CAP:
        raise ValueError("analysis repetition-mask cap drifted")
    scoring_hashes = {row.row_hash for row in scoring.rows}
    geometry_hashes = {row.scored_row_hash for row in geometry_audit.rows}
    if scoring_hashes != geometry_hashes:
        raise ValueError("geometry audit does not cover every scored row exactly")
    geometry_map = {row.scored_row_hash: row for row in geometry_audit.rows}

    summaries = []
    comparisons = []
    for index, (condition, budget) in enumerate(MID_DEV_FROZEN_PRIMARY_CELLS):
        summary, comparison = _legacy_cell_and_comparison(
            scoring,
            plan,
            geometry_map,
            condition,
            budget,
            PRE_RUN_BOOTSTRAP_SEED_BASE + 100 + index,
        )
        summaries.append(summary)
        comparisons.append(comparison)
    for index, tier in enumerate((VisibleCostTier.STRICT, VisibleCostTier.RELAXED)):
        beam_summary, _ = _normalized_cell_and_comparison(
            scoring,
            plan,
            normalized_traces,
            geometry_map,
            tier,
            MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
            PRE_RUN_BOOTSTRAP_SEED_BASE + 200 + index,
        )
        random_summary, comparison = _normalized_cell_and_comparison(
            scoring,
            plan,
            normalized_traces,
            geometry_map,
            tier,
            MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
            PRE_RUN_BOOTSTRAP_SEED_BASE + 200 + index,
        )
        summaries.extend((beam_summary, random_summary))
        comparisons.append(comparison)
    saturation = _saturation_report(scoring, plan, geometry_map)
    materialized_summaries = tuple(summaries)
    materialized_comparisons = tuple(comparisons)
    payload = {
        "algorithm_version": MID_DEV_V5_ANALYSIS_VERSION,
        "development_plan_hash": plan.plan_hash,
        "scoring_artifact_hash": scoring.artifact_hash,
        "geometry_audit_hash": geometry_audit.artifact_hash,
        "rule_usage_artifact_hash": rule_usage.artifact_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "detector_identity_hash": scoring.detector_identity_hash,
        "threshold_registry_hash": scoring.threshold_registry_hash,
        "analysis_contract_hash": FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT.contract_hash,
        "legacy_primary_cells_hash": MID_DEV_FROZEN_PRIMARY_CELLS_HASH,
        "cell_summary_hashes": tuple(value.summary_hash for value in materialized_summaries),
        "matched_comparison_hashes": tuple(value.comparison_hash for value in materialized_comparisons),
        "saturation_report_hash": saturation.report_hash,
        "rule_usage_counts": rule_usage.rule_usage_counts,
        "human_audit_sampling_rule": PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE,
        "human_audit_status": MID_DEV_V5_HUMAN_AUDIT_PENDING,
    }
    return MidDevV5AnalysisArtifact(
        development_plan_hash=plan.plan_hash,
        scoring_artifact_hash=scoring.artifact_hash,
        geometry_audit_hash=geometry_audit.artifact_hash,
        rule_usage_artifact_hash=rule_usage.artifact_hash,
        normalized_trace_artifact_hash=normalized_traces.artifact_hash,
        detector_identity_hash=scoring.detector_identity_hash,
        threshold_registry_hash=scoring.threshold_registry_hash,
        analysis_contract_hash=FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT.contract_hash,
        legacy_primary_cells_hash=MID_DEV_FROZEN_PRIMARY_CELLS_HASH,
        cell_summaries=materialized_summaries,
        matched_comparisons=materialized_comparisons,
        saturation_report=saturation,
        rule_usage_counts=rule_usage.rule_usage_counts,
        human_audit_sampling_rule=PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE,
        human_audit_status=MID_DEV_V5_HUMAN_AUDIT_PENDING,
        artifact_hash=sha256_json(payload),
    )
