from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from .._validation import require_int, require_sha256
from ..corpus.mid_dev import MidDevAttackArtifact
from ..corpus.schema import WatermarkLabel
from ..corpus.tiny_dev import TinyDevCorpusArtifact
from ..detectors import weighted_mean_evidence
from ..hashing import sha256_json
from ..native_observations import build_native_observations
from ..tiny_dev_transform_hf import (
    PRIMARY_TARGET_FPR,
    _encode_text,
    _text_only_calibration,
    _text_only_weighted_evidence,
    _threshold,
)
from .mid_dev_context_survival import MidDevCondition, MidDevPlanRow
from .mid_dev_freeze import MidDevDeterministicFrozenPlan
from .mid_dev_plan_builder import MidDevSelectionTraceArtifact
from .mid_dev_plan_io import validate_mid_dev_plan_trace_binding


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
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("rows must be a non-empty tuple")
        if len(self.rows) != 5688:
            raise ValueError("MidDev scoring artifact must score all 5688 frozen plan rows")
        if len({row.plan_row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("MidDev scored rows must bind unique plan rows")
        detector_hashes = {row.detector_identity_hash for row in self.rows}
        threshold_hashes = {row.threshold_hash for row in self.rows}
        threshold_values = {row.threshold_value for row in self.rows}
        if detector_hashes != {self.detector_identity_hash}:
            raise ValueError("MidDev scored rows mixed detector identities")
        if threshold_hashes != {self.threshold_hash} or threshold_values != {self.threshold_value}:
            raise ValueError("MidDev scored rows mixed thresholds")
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


def _validate_plan_against_corpus(
    corpus: MidDevAttackArtifact,
    plan: MidDevDeterministicFrozenPlan,
) -> dict[str, Any]:
    if plan.corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("frozen MidDev plan does not bind the supplied MidDev corpus")
    if plan.source_profile_hash != corpus.source_profile_hash:
        raise ValueError("frozen MidDev plan source profile does not match corpus")
    if plan.analysis_split_hash != corpus.analysis_split_hash:
        raise ValueError("frozen MidDev plan analysis split does not match corpus")
    sample_by_id = {sample.sample_id: sample for sample in corpus.manifest.samples}
    if len(sample_by_id) != 72:
        raise ValueError("MidDev corpus must contain exactly 72 source samples")
    for row in plan.rows:
        sample = sample_by_id.get(row.sample_id)
        if sample is None:
            raise ValueError("MidDev plan row references an unknown source sample")
        if (
            row.source_group_id != sample.match_id
            or row.prompt_id != sample.prompt_id
            or row.source_label is not sample.label
            or row.prompt_family_id != sample.prompt_family_id
            or row.domain is not sample.domain
            or row.target_length != sample.target_length
            or row.source_text_hash != sample.text_sha256
        ):
            raise ValueError("MidDev plan row metadata does not replay corpus source metadata")
    return sample_by_id


def _score_text(
    source: Any,
    text: str,
    tokenizer: Any,
    adapter: Any,
) -> float:
    tokens = _encode_text(tokenizer, text)
    eos = source.model.eos_token_id
    if eos is None:
        raise ValueError("MidDev source tokenizer must define eos_token_id")
    batch = build_native_observations(
        f"{source.sample_id}-middev-scored-{sha256_json(tokens)[:12]}",
        tokens,
        eos,
        adapter,
    )
    return float(weighted_mean_evidence(batch).raw_score)


def score_mid_dev_frozen_plan(
    mid_dev_corpus: MidDevAttackArtifact,
    calibration_corpus: TinyDevCorpusArtifact,
    tokenizer: Any,
    plan: MidDevDeterministicFrozenPlan,
    traces: MidDevSelectionTraceArtifact,
    adapter: Any,
) -> MidDevScoringArtifact:
    validate_mid_dev_plan_trace_binding(plan, traces)
    sample_by_id = _validate_plan_against_corpus(mid_dev_corpus, plan)
    mid_model_hashes = {sample.model.identity_hash for sample in mid_dev_corpus.manifest.samples}
    if mid_model_hashes != {calibration_corpus.model_identity_hash}:
        raise ValueError("MidDev and calibration corpora must use the same model/tokenizer identity")
    mid_watermark_hashes = {
        sample.watermark.condition_hash for sample in mid_dev_corpus.manifest.samples
    }
    if mid_watermark_hashes != {calibration_corpus.watermark_condition_hash}:
        raise ValueError("MidDev and calibration corpora must use the same watermark condition")
    if int(plan.ngram_len) != int(adapter.ngram_len):
        raise ValueError("MidDev plan ngram_len does not match scoring adapter")

    calibration = _text_only_calibration(calibration_corpus, adapter)
    threshold = _threshold(calibration, PRIMARY_TARGET_FPR)
    detector_identity_hash = calibration.detector_identity.identity_hash
    pristine = {
        sample_id: float(_text_only_weighted_evidence(source, adapter).raw_score)
        for sample_id, source in sample_by_id.items()
    }
    cache: dict[tuple[str, str], float] = {}
    scored_rows: list[MidDevScoredPlanRow] = []
    for plan_row in plan.rows:
        source = sample_by_id[plan_row.sample_id]
        cache_key = (plan_row.sample_id, plan_row.transformed_text_hash)
        transformed_score = cache.get(cache_key)
        if transformed_score is None:
            transformed_score = _score_text(source, plan_row.transformed_text, tokenizer, adapter)
            cache[cache_key] = transformed_score
        scored_rows.append(
            MidDevScoredPlanRow.create(
                plan_row=plan_row,
                detector_identity_hash=detector_identity_hash,
                threshold_hash=threshold.threshold_hash,
                threshold_value=threshold.value,
                pristine_score=pristine[plan_row.sample_id],
                transformed_score=transformed_score,
            )
        )
    row_tuple = tuple(scored_rows)
    positive_ids = {
        sample.sample_id
        for sample in mid_dev_corpus.manifest.samples
        if sample.label is WatermarkLabel.WATERMARKED
    }
    control_ids = {
        sample.sample_id
        for sample in mid_dev_corpus.manifest.samples
        if sample.label is WatermarkLabel.UNWATERMARKED
    }
    payload = {
        "algorithm_version": MID_DEV_SCORING_ARTIFACT_VERSION,
        "mid_dev_corpus_artifact_hash": mid_dev_corpus.artifact_hash,
        "source_profile_hash": mid_dev_corpus.source_profile_hash,
        "analysis_split_hash": mid_dev_corpus.analysis_split_hash,
        "plan_hash": plan.plan_hash,
        "trace_artifact_hash": traces.artifact_hash,
        "calibration_corpus_artifact_hash": calibration_corpus.artifact_hash,
        "calibration_bundle_hash": calibration.bundle_hash,
        "detector_identity_hash": detector_identity_hash,
        "threshold_hash": threshold.threshold_hash,
        "threshold_value": threshold.value,
        "target_fpr": PRIMARY_TARGET_FPR,
        "independent_source_group_count": 36,
        "independent_watermarked_source_count": len(positive_ids),
        "independent_control_source_count": len(control_ids),
        "pristine_watermarked_detected_count": sum(
            pristine[sample_id] >= threshold.value for sample_id in positive_ids
        ),
        "pristine_control_detected_count": sum(
            pristine[sample_id] >= threshold.value for sample_id in control_ids
        ),
        "row_hashes": tuple(row.scored_row_hash for row in row_tuple),
    }
    return MidDevScoringArtifact(
        mid_dev_corpus.artifact_hash,
        mid_dev_corpus.source_profile_hash,
        mid_dev_corpus.analysis_split_hash,
        plan.plan_hash,
        traces.artifact_hash,
        calibration_corpus.artifact_hash,
        calibration.bundle_hash,
        detector_identity_hash,
        threshold.threshold_hash,
        threshold.value,
        PRIMARY_TARGET_FPR,
        36,
        len(positive_ids),
        len(control_ids),
        payload["pristine_watermarked_detected_count"],
        payload["pristine_control_detected_count"],
        row_tuple,
        sha256_json(payload),
    )
