from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from ..tiny_dev_transform_hf import PRIMARY_TARGET_FPR
from .mid_dev_context_survival import MidDevCondition, MidDevPlanRow


MID_DEV_SCORED_PLAN_ROW_VERSION = "mid-dev-scored-plan-row-v1"
MID_DEV_SCORING_ARTIFACT_VERSION = "mid-dev-scoring-artifact-v1"


@dataclass(frozen=True, slots=True)
class MidDevScoredPlanRow:
    plan_row_hash: str
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    condition: MidDevCondition
    budget: int
    replicate: int
    status: str
    realized_edit_cost: int
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    pristine_score: float
    transformed_score: float
    pristine_detected: bool
    transformed_detected: bool
    scored_row_hash: str

    def __post_init__(self) -> None:
        for name in (
            "plan_row_hash",
            "detector_identity_hash",
            "threshold_hash",
            "scored_row_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.source_group_id, str) or not self.source_group_id:
            raise ValueError("source_group_id must be non-empty")
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be WatermarkLabel")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status must be non-empty")
        require_int("budget", self.budget)
        require_int("replicate", self.replicate)
        require_int("realized_edit_cost", self.realized_edit_cost)
        if self.realized_edit_cost < 0:
            raise ValueError("realized_edit_cost must be non-negative")
        for name in ("threshold_value", "pristine_score", "transformed_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not isinstance(self.pristine_detected, bool):
            raise TypeError("pristine_detected must be boolean")
        if not isinstance(self.transformed_detected, bool):
            raise TypeError("transformed_detected must be boolean")
        if self.scored_row_hash != sha256_json(self.payload()):
            raise ValueError("scored_row_hash does not match MidDev scored row")

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
    ) -> "MidDevScoredPlanRow":
        payload = {
            "algorithm_version": MID_DEV_SCORED_PLAN_ROW_VERSION,
            "plan_row_hash": plan_row.plan_row_hash,
            "source_group_id": plan_row.source_group_id,
            "sample_id": plan_row.sample_id,
            "source_label": plan_row.source_label.value,
            "condition": plan_row.condition.value,
            "budget": plan_row.budget,
            "replicate": plan_row.replicate,
            "status": plan_row.status,
            "realized_edit_cost": plan_row.operation_count,
            "detector_identity_hash": detector_identity_hash,
            "threshold_hash": threshold_hash,
            "threshold_value": float(threshold_value),
            "pristine_score": float(pristine_score),
            "transformed_score": float(transformed_score),
            "pristine_detected": pristine_score >= threshold_value,
            "transformed_detected": transformed_score >= threshold_value,
        }
        return cls(
            plan_row.plan_row_hash,
            plan_row.source_group_id,
            plan_row.sample_id,
            plan_row.source_label,
            plan_row.condition,
            plan_row.budget,
            plan_row.replicate,
            plan_row.status,
            plan_row.operation_count,
            detector_identity_hash,
            threshold_hash,
            float(threshold_value),
            float(pristine_score),
            float(transformed_score),
            pristine_score >= threshold_value,
            transformed_score >= threshold_value,
            sha256_json(payload),
        )

    @property
    def margin_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SCORED_PLAN_ROW_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "status": self.status,
            "realized_edit_cost": self.realized_edit_cost,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "pristine_detected": self.pristine_detected,
            "transformed_detected": self.transformed_detected,
        }


@dataclass(frozen=True, slots=True)
class MidDevScoringArtifact:
    mid_dev_corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    plan_hash: str
    trace_artifact_hash: str
    calibration_corpus_artifact_hash: str
    calibration_bundle_hash: str
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    target_fpr: float
    independent_source_group_count: int
    independent_watermarked_source_count: int
    independent_control_source_count: int
    pristine_watermarked_detected_count: int
    pristine_control_detected_count: int
    rows: tuple[MidDevScoredPlanRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "mid_dev_corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "plan_hash",
            "trace_artifact_hash",
            "calibration_corpus_artifact_hash",
            "calibration_bundle_hash",
            "detector_identity_hash",
            "threshold_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "independent_source_group_count",
            "independent_watermarked_source_count",
            "independent_control_source_count",
            "pristine_watermarked_detected_count",
            "pristine_control_detected_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.independent_source_group_count != 36:
            raise ValueError("MidDev scoring artifact must contain exactly 36 source groups")
        if self.independent_watermarked_source_count != 36:
            raise ValueError("MidDev scoring artifact must contain exactly 36 watermarked sources")
        if self.independent_control_source_count != 36:
            raise ValueError("MidDev scoring artifact must contain exactly 36 controls")
        if not math.isfinite(self.threshold_value):
            raise ValueError("threshold_value must be finite")
        if not math.isclose(self.target_fpr, PRIMARY_TARGET_FPR, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("MidDev scorer must use the frozen primary target FPR")
        if not isinstance(self.rows, tuple) or len(self.rows) != 5688:
            raise ValueError("MidDev scoring artifact must contain 5688 rows")
        if len({row.plan_row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("MidDev scored rows must bind unique plan rows")
        if {row.detector_identity_hash for row in self.rows} != {self.detector_identity_hash}:
            raise ValueError("MidDev scored rows mixed detector identities")
        if {row.threshold_hash for row in self.rows} != {self.threshold_hash}:
            raise ValueError("MidDev scored rows mixed threshold identities")
        if {row.threshold_value for row in self.rows} != {self.threshold_value}:
            raise ValueError("MidDev scored rows mixed threshold values")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match MidDev scoring artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SCORING_ARTIFACT_VERSION,
            "mid_dev_corpus_artifact_hash": self.mid_dev_corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "plan_hash": self.plan_hash,
            "trace_artifact_hash": self.trace_artifact_hash,
            "calibration_corpus_artifact_hash": self.calibration_corpus_artifact_hash,
            "calibration_bundle_hash": self.calibration_bundle_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "target_fpr": self.target_fpr,
            "independent_source_group_count": self.independent_source_group_count,
            "independent_watermarked_source_count": self.independent_watermarked_source_count,
            "independent_control_source_count": self.independent_control_source_count,
            "pristine_watermarked_detected_count": self.pristine_watermarked_detected_count,
            "pristine_control_detected_count": self.pristine_control_detected_count,
            "row_hashes": tuple(row.scored_row_hash for row in self.rows),
        }
