from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus.mid_dev import (
    MidDevAnalysisSplit,
    MidDevAttackArtifact,
    build_mid_dev_analysis_split,
)
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .mid_dev_scored_schema import MidDevScoringArtifact
from .mid_dev_scoring_contracts import MidDevCondition, MidDevFrozenPlanView


MID_DEV_ECS1_RAW_ROW_VERSION = "E-CS1-raw-predictor-row-v2"
MID_DEV_ECS1_RAW_ARTIFACT_VERSION = "E-CS1-raw-predictor-artifact-v2"


@dataclass(frozen=True, slots=True)
class MidDevECS1RawRow:
    plan_row_hash: str
    scored_row_hash: str
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    condition: MidDevCondition
    budget: int
    replicate: int
    status: str
    realized_edit_cost: int
    analysis_split: MidDevAnalysisSplit
    word_edit_rate: float
    old_observation_replacement_ratio: float
    exact_destruction_ratio: float
    exact_survival_ratio: float
    detector_margin_drop: float
    row_hash: str

    def __post_init__(self) -> None:
        for name in ("plan_row_hash", "scored_row_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.source_group_id, str) or not self.source_group_id:
            raise ValueError("source_group_id must be non-empty")
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be WatermarkLabel")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        if not isinstance(self.analysis_split, MidDevAnalysisSplit):
            raise TypeError("analysis_split must be MidDevAnalysisSplit")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status must be non-empty")
        for name in ("budget", "replicate", "realized_edit_cost"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in (
            "word_edit_rate",
            "old_observation_replacement_ratio",
            "exact_destruction_ratio",
            "exact_survival_ratio",
            "detector_margin_drop",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match E-CS1 raw row")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_ECS1_RAW_ROW_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "scored_row_hash": self.scored_row_hash,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "status": self.status,
            "realized_edit_cost": self.realized_edit_cost,
            "analysis_split": self.analysis_split.value,
            "word_edit_rate": self.word_edit_rate,
            "old_observation_replacement_ratio": self.old_observation_replacement_ratio,
            "exact_destruction_ratio": self.exact_destruction_ratio,
            "exact_survival_ratio": self.exact_survival_ratio,
            "detector_margin_drop": self.detector_margin_drop,
        }


@dataclass(frozen=True, slots=True)
class MidDevECS1RawArtifact:
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    plan_hash: str
    scoring_artifact_hash: str
    detector_identity_hash: str
    threshold_hash: str
    fit_source_group_count: int
    evaluation_source_group_count: int
    rows: tuple[MidDevECS1RawRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "plan_hash",
            "scoring_artifact_hash",
            "detector_identity_hash",
            "threshold_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("fit_source_group_count", self.fit_source_group_count)
        require_int("evaluation_source_group_count", self.evaluation_source_group_count)
        if self.fit_source_group_count != 24 or self.evaluation_source_group_count != 12:
            raise ValueError("E-CS1 raw artifact must preserve the frozen 24/12 source holdout")
        if not isinstance(self.rows, tuple) or len(self.rows) != 5688:
            raise ValueError("E-CS1 raw artifact must preserve all 5688 scored plan rows")
        if len({row.plan_row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("E-CS1 raw rows must bind unique plan rows")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match E-CS1 raw artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_ECS1_RAW_ARTIFACT_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "plan_hash": self.plan_hash,
            "scoring_artifact_hash": self.scoring_artifact_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "fit_source_group_count": self.fit_source_group_count,
            "evaluation_source_group_count": self.evaluation_source_group_count,
            "row_hashes": tuple(row.row_hash for row in self.rows),
        }


def build_ecs1_raw_artifact(
    corpus: MidDevAttackArtifact,
    plan: MidDevFrozenPlanView,
    scoring: MidDevScoringArtifact,
) -> MidDevECS1RawArtifact:
    if plan.corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("E-CS1 plan does not bind the supplied MidDev corpus")
    if scoring.mid_dev_corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("E-CS1 scoring artifact does not bind the supplied MidDev corpus")
    if scoring.plan_hash != plan.plan_hash:
        raise ValueError("E-CS1 scoring artifact does not bind the supplied plan")
    quality_by_hash = {row.plan_row_hash: row for row in plan.quality_rows}
    plan_by_hash = {row.plan_row_hash: row for row in plan.rows}
    scored_by_hash = {row.plan_row_hash: row for row in scoring.rows}
    if set(quality_by_hash) != set(plan_by_hash) or set(scored_by_hash) != set(plan_by_hash):
        raise ValueError("E-CS1 inputs do not cover the same frozen plan rows")
    split_by_prompt = build_mid_dev_analysis_split(corpus.manifest.prompts)
    source_split: dict[str, MidDevAnalysisSplit] = {}
    output: list[MidDevECS1RawRow] = []
    for plan_row in plan.rows:
        quality = quality_by_hash[plan_row.plan_row_hash]
        scored = scored_by_hash[plan_row.plan_row_hash]
        split = split_by_prompt.get(plan_row.prompt_id)
        if split is None:
            raise ValueError("E-CS1 plan row has no frozen source-holdout assignment")
        existing = source_split.setdefault(plan_row.source_group_id, split)
        if existing is not split:
            raise ValueError("E-CS1 matched source group crossed the frozen holdout boundary")
        payload = {
            "algorithm_version": MID_DEV_ECS1_RAW_ROW_VERSION,
            "plan_row_hash": plan_row.plan_row_hash,
            "scored_row_hash": scored.scored_row_hash,
            "source_group_id": plan_row.source_group_id,
            "sample_id": plan_row.sample_id,
            "source_label": plan_row.source_label.value,
            "condition": plan_row.condition.value,
            "budget": plan_row.budget,
            "replicate": plan_row.replicate,
            "status": scored.status,
            "realized_edit_cost": scored.realized_edit_cost,
            "analysis_split": split.value,
            "word_edit_rate": quality.word_edit_rate,
            "old_observation_replacement_ratio": quality.old_observation_replacement_ratio,
            "exact_destruction_ratio": quality.exact_destruction_ratio,
            "exact_survival_ratio": quality.exact_survival_ratio,
            "detector_margin_drop": scored.margin_drop,
        }
        output.append(
            MidDevECS1RawRow(
                plan_row.plan_row_hash,
                scored.scored_row_hash,
                plan_row.source_group_id,
                plan_row.sample_id,
                plan_row.source_label,
                plan_row.condition,
                plan_row.budget,
                plan_row.replicate,
                scored.status,
                scored.realized_edit_cost,
                split,
                quality.word_edit_rate,
                quality.old_observation_replacement_ratio,
                quality.exact_destruction_ratio,
                quality.exact_survival_ratio,
                scored.margin_drop,
                sha256_json(payload),
            )
        )
    fit_groups = {group for group, split in source_split.items() if split is MidDevAnalysisSplit.FIT}
    eval_groups = {
        group for group, split in source_split.items() if split is MidDevAnalysisSplit.EVALUATION
    }
    materialized = tuple(output)
    payload = {
        "algorithm_version": MID_DEV_ECS1_RAW_ARTIFACT_VERSION,
        "corpus_artifact_hash": corpus.artifact_hash,
        "source_profile_hash": corpus.source_profile_hash,
        "analysis_split_hash": corpus.analysis_split_hash,
        "plan_hash": plan.plan_hash,
        "scoring_artifact_hash": scoring.artifact_hash,
        "detector_identity_hash": scoring.detector_identity_hash,
        "threshold_hash": scoring.threshold_hash,
        "fit_source_group_count": len(fit_groups),
        "evaluation_source_group_count": len(eval_groups),
        "row_hashes": tuple(row.row_hash for row in materialized),
    }
    return MidDevECS1RawArtifact(
        corpus.artifact_hash,
        corpus.source_profile_hash,
        corpus.analysis_split_hash,
        plan.plan_hash,
        scoring.artifact_hash,
        scoring.detector_identity_hash,
        scoring.threshold_hash,
        len(fit_groups),
        len(eval_groups),
        materialized,
        sha256_json(payload),
    )
