from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json, sha256_text


MID_DEV_PLAN_ALGORITHM_VERSION = "mid-dev-context-survival-plan-v1"
MID_DEV_EVIDENCE_ALGORITHM_VERSION = "mid-dev-context-survival-evidence-v1"
MID_DEV_SOURCE_AGGREGATE_ALGORITHM_VERSION = "mid-dev-source-group-aggregate-v1"
MID_DEV_BOOTSTRAP_REPLICATES = 10_000
MID_DEV_MINIMUM_SOURCE_GROUPS = 32


class MidDevCondition(str, Enum):
    CURRENT_BASELINE = "E-CS1-current-strongest-baseline"
    CONTEXT_GREEDY = "E-CS2-context-survival-greedy"
    CONTEXT_BEAM = "E-CS3-context-survival-beam"
    EVEN_SPACING = "E-CS4-spacing-baseline"
    RANDOM_SAFE = "E-CS5-budget-matched-random-safe"
    NO_OP = "E-CS6-no-op-control"


MID_DEV_CONDITIONS = tuple(MidDevCondition)


@dataclass(frozen=True, slots=True)
class MidDevPlanRow:
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    source_text_hash: str
    condition: MidDevCondition
    transformed_text: str
    transformed_text_hash: str
    operation_count: int
    selection_trace_hash: str
    plan_row_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_group_id", self.source_group_id)
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be a WatermarkLabel")
        require_sha256("source_text_hash", self.source_text_hash)
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be a MidDevCondition")
        if not isinstance(self.transformed_text, str) or not self.transformed_text:
            raise ValueError("transformed_text must be a non-empty string")
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        require_int("operation_count", self.operation_count)
        if self.operation_count < 0:
            raise ValueError("operation_count must be non-negative")
        if self.condition is MidDevCondition.NO_OP and self.operation_count != 0:
            raise ValueError("no-op condition must realize zero operations")
        require_sha256("selection_trace_hash", self.selection_trace_hash)
        require_sha256("plan_row_hash", self.plan_row_hash)
        if self.plan_row_hash != sha256_json(self.payload()):
            raise ValueError("plan_row_hash does not match MidDevPlanRow payload")

    @classmethod
    def create(
        cls,
        *,
        source_group_id: str,
        sample_id: str,
        source_label: WatermarkLabel,
        source_text_hash: str,
        condition: MidDevCondition,
        transformed_text: str,
        operation_count: int,
        selection_trace_hash: str,
    ) -> MidDevPlanRow:
        transformed_text_hash = sha256_text(transformed_text)
        payload = {
            "source_group_id": source_group_id,
            "sample_id": sample_id,
            "source_label": source_label.value,
            "source_text_hash": source_text_hash,
            "condition": condition.value,
            "transformed_text_hash": transformed_text_hash,
            "operation_count": operation_count,
            "selection_trace_hash": selection_trace_hash,
        }
        return cls(
            source_group_id,
            sample_id,
            source_label,
            source_text_hash,
            condition,
            transformed_text,
            transformed_text_hash,
            operation_count,
            selection_trace_hash,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "source_text_hash": self.source_text_hash,
            "condition": self.condition.value,
            "transformed_text_hash": self.transformed_text_hash,
            "operation_count": self.operation_count,
            "selection_trace_hash": self.selection_trace_hash,
        }


@dataclass(frozen=True, slots=True)
class MidDevFrozenPlan:
    algorithm_version: str
    corpus_artifact_hash: str
    source_profile_hash: str
    selection_config_hash: str
    rows: tuple[MidDevPlanRow, ...]
    detector_access_observed: bool
    secret_access_observed: bool
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_PLAN_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev plan algorithm version")
        for name in ("corpus_artifact_hash", "source_profile_hash", "selection_config_hash", "plan_hash"):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.rows, tuple) or any(not isinstance(value, MidDevPlanRow) for value in self.rows):
            raise TypeError("rows must be a tuple of MidDevPlanRow values")
        if not self.rows:
            raise ValueError("MidDev plan must contain rows")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("MidDev plan selection must remain detector-blind and secret-blind")
        if len({value.plan_row_hash for value in self.rows}) != len(self.rows):
            raise ValueError("MidDev plan rows must be unique")
        _validate_plan_matrix(self.rows)
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match MidDevFrozenPlan payload")

    @classmethod
    def create(
        cls,
        *,
        corpus_artifact_hash: str,
        source_profile_hash: str,
        selection_config_hash: str,
        rows: Sequence[MidDevPlanRow],
    ) -> MidDevFrozenPlan:
        materialized = tuple(sorted(rows, key=lambda value: (value.source_group_id, value.sample_id, value.condition.value)))
        payload = {
            "algorithm_version": MID_DEV_PLAN_ALGORITHM_VERSION,
            "corpus_artifact_hash": corpus_artifact_hash,
            "source_profile_hash": source_profile_hash,
            "selection_config_hash": selection_config_hash,
            "row_hashes": tuple(value.plan_row_hash for value in materialized),
            "detector_access_observed": False,
            "secret_access_observed": False,
        }
        return cls(
            MID_DEV_PLAN_ALGORITHM_VERSION,
            corpus_artifact_hash,
            source_profile_hash,
            selection_config_hash,
            materialized,
            False,
            False,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "selection_config_hash": self.selection_config_hash,
            "row_hashes": tuple(value.plan_row_hash for value in self.rows),
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _validate_plan_matrix(rows: Sequence[MidDevPlanRow]) -> None:
    source_groups = sorted({value.source_group_id for value in rows})
    if len(source_groups) < MID_DEV_MINIMUM_SOURCE_GROUPS:
        raise ValueError("MidDev frozen plan must contain at least 32 independent source groups")
    by_sample: dict[tuple[str, str], list[MidDevPlanRow]] = {}
    group_labels: dict[str, set[WatermarkLabel]] = {}
    for row in rows:
        by_sample.setdefault((row.source_group_id, row.sample_id), []).append(row)
        group_labels.setdefault(row.source_group_id, set()).add(row.source_label)
    for group_id in source_groups:
        if group_labels[group_id] != {WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED}:
            raise ValueError("each MidDev source group must contain watermarked and control plans")
    for values in by_sample.values():
        if {value.condition for value in values} != set(MID_DEV_CONDITIONS):
            raise ValueError("each MidDev sample must have exactly one row for every frozen condition")
        if len(values) != len(MID_DEV_CONDITIONS):
            raise ValueError("MidDev sample condition rows must not be duplicated")


@dataclass(frozen=True, slots=True)
class MidDevScoredRow:
    plan_row_hash: str
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    condition: MidDevCondition
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    pristine_score: float
    transformed_score: float
    pristine_detected: bool
    transformed_detected: bool
    scored_row_hash: str

    def __post_init__(self) -> None:
        for name in ("plan_row_hash", "detector_identity_hash", "threshold_hash", "scored_row_hash"):
            require_sha256(name, getattr(self, name))
        require_clean_string("source_group_id", self.source_group_id)
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be a WatermarkLabel")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be a MidDevCondition")
        for name in ("threshold_value", "pristine_score", "transformed_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not isinstance(self.pristine_detected, bool) or not isinstance(self.transformed_detected, bool):
            raise TypeError("detected fields must be booleans")
        if self.scored_row_hash != sha256_json(self.payload()):
            raise ValueError("scored_row_hash does not match MidDevScoredRow payload")

    @classmethod
    def create(
        cls,
        *,
        plan_row: MidDevPlanRow,
        detector_identity_hash: str,
        threshold_hash: str,
        threshold_value: float,
        pristine_score: float,
        transformed_score: float,
    ) -> MidDevScoredRow:
        pristine_detected = pristine_score >= threshold_value
        transformed_detected = transformed_score >= threshold_value
        payload = {
            "plan_row_hash": plan_row.plan_row_hash,
            "source_group_id": plan_row.source_group_id,
            "sample_id": plan_row.sample_id,
            "source_label": plan_row.source_label.value,
            "condition": plan_row.condition.value,
            "detector_identity_hash": detector_identity_hash,
            "threshold_hash": threshold_hash,
            "threshold_value": float(threshold_value),
            "pristine_score": float(pristine_score),
            "transformed_score": float(transformed_score),
            "pristine_detected": pristine_detected,
            "transformed_detected": transformed_detected,
        }
        return cls(
            plan_row.plan_row_hash,
            plan_row.source_group_id,
            plan_row.sample_id,
            plan_row.source_label,
            plan_row.condition,
            detector_identity_hash,
            threshold_hash,
            float(threshold_value),
            float(pristine_score),
            float(transformed_score),
            pristine_detected,
            transformed_detected,
            sha256_json(payload),
        )

    @property
    def score_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    def payload(self) -> dict[str, object]:
        return {
            "plan_row_hash": self.plan_row_hash,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "condition": self.condition.value,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "pristine_detected": self.pristine_detected,
            "transformed_detected": self.transformed_detected,
        }


@dataclass(frozen=True, slots=True)
class SourceGroupedComparison:
    baseline_condition: MidDevCondition
    comparison_condition: MidDevCondition
    source_group_count: int
    mean_score_drop_difference: float
    bootstrap_lower: float
    bootstrap_upper: float
    positive_difference_count: int
    negative_difference_count: int
    zero_difference_count: int
    two_sided_sign_p_value: float
    comparison_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.baseline_condition, MidDevCondition) or not isinstance(self.comparison_condition, MidDevCondition):
            raise TypeError("comparison conditions must be MidDevCondition values")
        require_int("source_group_count", self.source_group_count)
        if self.source_group_count < MID_DEV_MINIMUM_SOURCE_GROUPS:
            raise ValueError("source-group comparison requires at least 32 sources")
        for name in ("mean_score_drop_difference", "bootstrap_lower", "bootstrap_upper", "two_sided_sign_p_value"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.bootstrap_lower > self.bootstrap_upper:
            raise ValueError("bootstrap interval is reversed")
        for name in ("positive_difference_count", "negative_difference_count", "zero_difference_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.positive_difference_count + self.negative_difference_count + self.zero_difference_count != self.source_group_count:
            raise ValueError("sign counts must partition source groups")
        if not 0.0 <= self.two_sided_sign_p_value <= 1.0:
            raise ValueError("sign p-value must be between zero and one")
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self.payload()):
            raise ValueError("comparison_hash does not match SourceGroupedComparison payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SOURCE_AGGREGATE_ALGORITHM_VERSION,
            "baseline_condition": self.baseline_condition.value,
            "comparison_condition": self.comparison_condition.value,
            "source_group_count": self.source_group_count,
            "mean_score_drop_difference": self.mean_score_drop_difference,
            "bootstrap_lower": self.bootstrap_lower,
            "bootstrap_upper": self.bootstrap_upper,
            "positive_difference_count": self.positive_difference_count,
            "negative_difference_count": self.negative_difference_count,
            "zero_difference_count": self.zero_difference_count,
            "two_sided_sign_p_value": self.two_sided_sign_p_value,
        }


def source_grouped_comparison(
    rows: Sequence[MidDevScoredRow],
    *,
    comparison_condition: MidDevCondition,
    baseline_condition: MidDevCondition = MidDevCondition.CURRENT_BASELINE,
    bootstrap_replicates: int = MID_DEV_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = 0x4D4944444556,
) -> SourceGroupedComparison:
    require_int("bootstrap_replicates", bootstrap_replicates)
    require_int("bootstrap_seed", bootstrap_seed)
    if bootstrap_replicates <= 0:
        raise ValueError("bootstrap_replicates must be positive")
    if bootstrap_seed < 0:
        raise ValueError("bootstrap_seed must be non-negative")
    positives = tuple(value for value in rows if value.source_label is WatermarkLabel.WATERMARKED)
    grouped: dict[str, dict[MidDevCondition, MidDevScoredRow]] = {}
    for row in positives:
        grouped.setdefault(row.source_group_id, {})[row.condition] = row
    differences: list[float] = []
    for group_id in sorted(grouped):
        values = grouped[group_id]
        if baseline_condition not in values or comparison_condition not in values:
            raise ValueError("source-group comparison is missing a required condition")
        differences.append(values[comparison_condition].score_drop - values[baseline_condition].score_drop)
    if len(differences) < MID_DEV_MINIMUM_SOURCE_GROUPS:
        raise ValueError("source-group comparison requires at least 32 independent sources")
    rng = random.Random(bootstrap_seed)
    bootstrap_means: list[float] = []
    count = len(differences)
    for _ in range(bootstrap_replicates):
        bootstrap_means.append(sum(differences[rng.randrange(count)] for _ in range(count)) / count)
    bootstrap_means.sort()
    lower_index = max(0, math.floor(0.025 * (bootstrap_replicates - 1)))
    upper_index = min(bootstrap_replicates - 1, math.ceil(0.975 * (bootstrap_replicates - 1)))
    positive = sum(value > 0 for value in differences)
    negative = sum(value < 0 for value in differences)
    zero = count - positive - negative
    nonzero = positive + negative
    if nonzero == 0:
        sign_p = 1.0
    else:
        tail = min(positive, negative)
        cumulative = sum(math.comb(nonzero, value) for value in range(tail + 1)) / (2**nonzero)
        sign_p = min(1.0, 2.0 * cumulative)
    payload = {
        "algorithm_version": MID_DEV_SOURCE_AGGREGATE_ALGORITHM_VERSION,
        "baseline_condition": baseline_condition.value,
        "comparison_condition": comparison_condition.value,
        "source_group_count": count,
        "mean_score_drop_difference": sum(differences) / count,
        "bootstrap_lower": bootstrap_means[lower_index],
        "bootstrap_upper": bootstrap_means[upper_index],
        "positive_difference_count": positive,
        "negative_difference_count": negative,
        "zero_difference_count": zero,
        "two_sided_sign_p_value": sign_p,
    }
    return SourceGroupedComparison(
        baseline_condition,
        comparison_condition,
        count,
        payload["mean_score_drop_difference"],
        payload["bootstrap_lower"],
        payload["bootstrap_upper"],
        positive,
        negative,
        zero,
        sign_p,
        sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class MidDevEvidenceArtifact:
    algorithm_version: str
    plan_hash: str
    calibration_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    scored_rows: tuple[MidDevScoredRow, ...]
    comparisons: tuple[SourceGroupedComparison, ...]
    scoring_started_after_plan_freeze: bool
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev evidence algorithm version")
        for name in ("plan_hash", "calibration_artifact_hash", "detector_identity_hash", "threshold_hash", "evidence_hash"):
            require_sha256(name, getattr(self, name))
        if not self.scoring_started_after_plan_freeze:
            raise ValueError("MidDev evidence requires plan freeze before detector scoring")
        if not isinstance(self.scored_rows, tuple) or any(not isinstance(value, MidDevScoredRow) for value in self.scored_rows):
            raise TypeError("scored_rows must contain MidDevScoredRow values")
        if not isinstance(self.comparisons, tuple) or any(not isinstance(value, SourceGroupedComparison) for value in self.comparisons):
            raise TypeError("comparisons must contain SourceGroupedComparison values")
        if len({value.scored_row_hash for value in self.scored_rows}) != len(self.scored_rows):
            raise ValueError("scored rows must be unique")
        if self.evidence_hash != sha256_json(self.payload()):
            raise ValueError("evidence_hash does not match MidDevEvidenceArtifact payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "plan_hash": self.plan_hash,
            "calibration_artifact_hash": self.calibration_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "scored_row_hashes": tuple(value.scored_row_hash for value in self.scored_rows),
            "comparison_hashes": tuple(value.comparison_hash for value in self.comparisons),
            "scoring_started_after_plan_freeze": self.scoring_started_after_plan_freeze,
        }
