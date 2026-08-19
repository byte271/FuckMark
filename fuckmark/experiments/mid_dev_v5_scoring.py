from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..detector_calibration import encode_text
from ..detectors import DetectorCalibrationIdentity, weighted_mean_evidence
from ..hashing import sha256_json, sha256_text
from ..native_observations import build_native_observations
from ..public_eligibility import build_huggingface_public_eligibility
from ..transforms.hard_invariants import validate_hard_invariants
from .detector_opportunity_audit import CalibrationRegimeDecision, DetectorOpportunityAuditArtifact
from .mid_dev_calibration_audit import FrozenCalibrationThresholdRecord, FrozenCalibrationThresholdRegistry
from .mid_dev_plan_v5 import MidDevDevelopmentPlanV5
from .mid_dev_v5_builder import MidDevNormalizedTraceArtifact
from .mid_dev_v5_execution_contract import validate_mid_dev_v5_execution_contract
from .mid_dev_quality import protected_span_violation_count, word_edit_rate
from .residual_signal_geometry import compute_residual_signal_geometry
from .structural_leverage import character_edit_rate


MID_DEV_V5_SCORE_VALUE_VERSION = "mid-dev-v5-score-value-v2"
MID_DEV_V5_SCORED_ROW_VERSION = "mid-dev-v5-scored-row-v2"
MID_DEV_V5_SCORING_ARTIFACT_VERSION = "mid-dev-v5-scoring-artifact-v2"


class MidDevV5ScoredRowKind(str, Enum):
    LEGACY = "LEGACY"
    NORMALIZED = "NORMALIZED"


@dataclass(frozen=True, slots=True)
class MidDevV5ScoreValue:
    text_hash: str
    token_hash: str
    eligibility_mask_hash: str
    eligible_observation_count: int
    regime_id: str
    calibration_regime_hash: str
    threshold_record_hash: str
    threshold_hash: str
    threshold_value: float
    raw_score: float
    margin: float
    detected: bool
    detector_identity_hash: str
    value_hash: str

    def __post_init__(self) -> None:
        for name in (
            "text_hash", "token_hash", "eligibility_mask_hash", "calibration_regime_hash",
            "threshold_record_hash", "threshold_hash", "detector_identity_hash", "value_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_clean_string("regime_id", self.regime_id)
        require_int("eligible_observation_count", self.eligible_observation_count)
        if self.eligible_observation_count <= 0:
            raise ValueError("score value requires positive eligible observations")
        for name in ("threshold_value", "raw_score", "margin"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if not 0.0 <= self.threshold_value <= 1.0 or not 0.0 <= self.raw_score <= 1.0:
            raise ValueError("threshold/raw score must be in [0,1]")
        if self.margin != self.raw_score - self.threshold_value:
            raise ValueError("margin does not reproduce")
        if type(self.detected) is not bool or self.detected != (self.raw_score >= self.threshold_value):
            raise ValueError("detected flag does not reproduce >= threshold")
        if self.value_hash != sha256_json(self.payload()):
            raise ValueError("score value hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        text_hash: str,
        token_hash: str,
        eligibility_mask_hash: str,
        eligible_observation_count: int,
        record: FrozenCalibrationThresholdRecord,
        raw_score: float,
        detector_identity_hash: str,
    ) -> "MidDevV5ScoreValue":
        values = {
            "text_hash": text_hash,
            "token_hash": token_hash,
            "eligibility_mask_hash": eligibility_mask_hash,
            "eligible_observation_count": eligible_observation_count,
            "regime_id": record.regime_id,
            "calibration_regime_hash": record.calibration_regime_hash,
            "threshold_record_hash": record.record_hash,
            "threshold_hash": record.threshold_hash,
            "threshold_value": float(record.threshold_value),
            "raw_score": float(raw_score),
            "margin": float(raw_score) - float(record.threshold_value),
            "detected": float(raw_score) >= float(record.threshold_value),
            "detector_identity_hash": detector_identity_hash,
        }
        payload = {"algorithm_version": MID_DEV_V5_SCORE_VALUE_VERSION, **values}
        return cls(**values, value_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_SCORE_VALUE_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "value_hash"},
        }


@dataclass(frozen=True, slots=True)
class MidDevV5ScoredRow:
    row_kind: MidDevV5ScoredRowKind
    plan_row_hash: str
    source_group_id: str
    sample_id: str
    source_label: str
    target_length: int
    planner_or_condition: str
    tier: str | None
    budget: int | None
    replicate: int
    selection_trace_hash: str
    transformed_text_hash: str
    pristine_score: MidDevV5ScoreValue
    transformed_score: MidDevV5ScoreValue
    residual_geometry_hash: str
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    word_edit_rate: float
    character_edit_rate: float
    token_edit_distance: int
    length_ratio: float
    protected_span_violation_count: int
    hard_invariant_passed: bool
    row_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.row_kind, MidDevV5ScoredRowKind):
            raise TypeError("row_kind must be MidDevV5ScoredRowKind")
        for name in ("plan_row_hash", "selection_trace_hash", "transformed_text_hash", "residual_geometry_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        for name in ("source_group_id", "sample_id", "source_label", "planner_or_condition"):
            require_clean_string(name, getattr(self, name))
        if self.tier is not None:
            require_clean_string("tier", self.tier)
        for name in ("target_length", "replicate", "token_edit_distance", "protected_span_violation_count"):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.target_length <= 0:
            raise ValueError("target_length must be positive")
        if self.budget is not None:
            require_int("budget", self.budget)
            if self.budget < 0:
                raise ValueError("budget must be non-negative")
        if not isinstance(self.pristine_score, MidDevV5ScoreValue) or not isinstance(self.transformed_score, MidDevV5ScoreValue):
            raise TypeError("score fields have invalid types")
        if self.transformed_score.text_hash != self.transformed_text_hash:
            raise ValueError("transformed score does not bind transformed text")
        for name in (
            "residual_inherited_fraction", "new_context_opportunity_fraction", "valid_denominator_ratio",
            "word_edit_rate", "character_edit_rate", "length_ratio",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
            if float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if self.residual_inherited_fraction > 1.0 or self.new_context_opportunity_fraction > 1.0:
            raise ValueError("RIF/NCF must be in [0,1]")
        if self.word_edit_rate > 1.0 or self.character_edit_rate > 1.0 or self.length_ratio <= 0.0:
            raise ValueError("visible-cost metric out of range")
        if type(self.hard_invariant_passed) is not bool:
            raise TypeError("hard_invariant_passed must be bool")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("scored row hash mismatch")

    def payload(self) -> dict[str, object]:
        values = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"row_kind", "row_hash"}
        }
        return {"algorithm_version": MID_DEV_V5_SCORED_ROW_VERSION, "row_kind": self.row_kind.value, **values}


@dataclass(frozen=True, slots=True)
class MidDevV5ScoringArtifact:
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    development_plan_hash: str
    normalized_trace_artifact_hash: str
    execution_attestation_hash: str
    opportunity_audit_hash: str
    regime_decision_hash: str
    threshold_registry_hash: str
    detector_identity_hash: str
    independent_source_group_count: int
    source_sample_count: int
    rows: tuple[MidDevV5ScoredRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "corpus_artifact_hash", "source_profile_hash", "analysis_split_hash", "development_plan_hash",
            "normalized_trace_artifact_hash", "execution_attestation_hash", "opportunity_audit_hash",
            "regime_decision_hash", "threshold_registry_hash", "detector_identity_hash", "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.independent_source_group_count != 36 or self.source_sample_count != 72:
            raise ValueError("v5 scoring requires 36 groups / 72 samples")
        if not isinstance(self.rows, tuple) or len(self.rows) != 8136:
            raise ValueError("v5 scoring requires 5688 legacy + 2448 normalized rows")
        if any(not isinstance(row, MidDevV5ScoredRow) for row in self.rows):
            raise TypeError("scoring artifact contains invalid row")
        if len({row.row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("scored row hashes must be unique")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("scoring artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_SCORING_ARTIFACT_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "development_plan_hash": self.development_plan_hash,
            "normalized_trace_artifact_hash": self.normalized_trace_artifact_hash,
            "execution_attestation_hash": self.execution_attestation_hash,
            "opportunity_audit_hash": self.opportunity_audit_hash,
            "regime_decision_hash": self.regime_decision_hash,
            "threshold_registry_hash": self.threshold_registry_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "independent_source_group_count": self.independent_source_group_count,
            "source_sample_count": self.source_sample_count,
            "row_hashes": tuple(row.row_hash for row in self.rows),
        }


def score_text_with_frozen_registry(
    *,
    source: Any,
    text: str,
    tokenizer: Any,
    adapter: Any,
    source_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    registry: FrozenCalibrationThresholdRegistry,
) -> MidDevV5ScoreValue:
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise ValueError("regime decision does not bind opportunity audit")
    if registry.regime_decision_hash != decision.decision_hash or registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise ValueError("threshold registry does not bind opportunity/regime artifacts")
    if int(adapter.ngram_len) != int(source_audit.ngram_len):
        raise ValueError("runtime detector ngram length differs from frozen opportunity audit")
    tokens = tuple(encode_text(tokenizer, text))
    eos = source.model.eos_token_id
    if isinstance(eos, bool) or not isinstance(eos, int) or eos < 0:
        raise ValueError("source tokenizer must define non-negative eos_token_id")
    mask = build_huggingface_public_eligibility(
        tokens,
        eos,
        source_audit.ngram_len,
        source_audit.context_history_size,
    )
    if mask.valid_count <= 0:
        raise ValueError("scoring text has no public eligible observations")
    regime_id = decision.regime_id_for(source.target_length, mask.valid_count)
    records = {record.regime_id: record for record in registry.records}
    record = records.get(regime_id)
    if record is None:
        raise ValueError(f"no frozen threshold record for regime {regime_id}")
    batch = build_native_observations(
        f"{source.sample_id}-v5-{sha256_text(text)[:16]}",
        tokens,
        eos,
        adapter,
    )
    evidence = weighted_mean_evidence(batch)
    detector_identity = DetectorCalibrationIdentity.from_evidence(evidence)
    if detector_identity.identity_hash != registry.detector_identity_hash:
        raise ValueError("runtime detector identity differs from frozen threshold registry")
    return MidDevV5ScoreValue.create(
        text_hash=sha256_text(text),
        token_hash=mask.token_hash,
        eligibility_mask_hash=mask.mask_hash,
        eligible_observation_count=mask.valid_count,
        record=record,
        raw_score=evidence.raw_score,
        detector_identity_hash=detector_identity.identity_hash,
    )


def _structural_metrics(source: Any, text: str, tokenizer: Any, source_audit: DetectorOpportunityAuditArtifact):
    if source.text_only_tokens is None:
        raise ValueError("source is missing frozen text-only token track")
    final_tokens = tuple(encode_text(tokenizer, text))
    eos = source.model.eos_token_id
    if isinstance(eos, bool) or not isinstance(eos, int) or eos < 0:
        raise ValueError("source tokenizer must define non-negative eos_token_id")
    geometry = compute_residual_signal_geometry(
        source.text_only_tokens.token_ids,
        final_tokens,
        eos_token_id=eos,
        ngram_len=source_audit.ngram_len,
        context_history_size=source_audit.context_history_size,
    )
    hard = validate_hard_invariants(source.text, text)
    return {
        "geometry": geometry,
        "word_edit_rate": word_edit_rate(source.text, text),
        "character_edit_rate": character_edit_rate(source.text, text),
        "token_edit_distance": geometry.alignment_distance,
        "length_ratio": len(text) / max(1, len(source.text)),
        "protected_span_violation_count": protected_span_violation_count(source.text, text),
        "hard_invariant_passed": getattr(hard.status, "value", hard.status) == "pass",
    }


def score_mid_dev_development_plan_v5(
    corpus: Any,
    plan: MidDevDevelopmentPlanV5,
    normalized_traces: MidDevNormalizedTraceArtifact,
    source_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    registry: FrozenCalibrationThresholdRegistry,
    tokenizer: Any,
    adapter: Any,
) -> MidDevV5ScoringArtifact:
    execution = validate_mid_dev_v5_execution_contract(plan, normalized_traces)
    legacy = plan.legacy_plan
    if (
        legacy.corpus_artifact_hash != corpus.artifact_hash
        or legacy.source_profile_hash != corpus.source_profile_hash
        or legacy.analysis_split_hash != corpus.analysis_split_hash
    ):
        raise ValueError("v5 plan does not bind supplied MidDev corpus")
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise ValueError("regime decision does not bind opportunity audit")
    if registry.regime_decision_hash != decision.decision_hash or registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise ValueError("threshold registry does not bind opportunity/regime artifacts")
    sample_by_id = {sample.sample_id: sample for sample in corpus.manifest.samples}
    if len(sample_by_id) != 72:
        raise ValueError("v5 scoring requires exactly 72 source samples")
    for sample in sample_by_id.values():
        replay = tuple(encode_text(tokenizer, sample.text))
        if sample.text_only_tokens is None or replay != tuple(sample.text_only_tokens.token_ids):
            raise ValueError("runtime tokenizer does not replay frozen source text-only tokens")

    score_cache: dict[tuple[str, str], MidDevV5ScoreValue] = {}
    metric_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def score(source, text):
        key = (source.sample_id, sha256_text(text))
        if key not in score_cache:
            score_cache[key] = score_text_with_frozen_registry(
                source=source,
                text=text,
                tokenizer=tokenizer,
                adapter=adapter,
                source_audit=source_audit,
                decision=decision,
                registry=registry,
            )
        return score_cache[key]

    def metrics(source, text):
        key = (source.sample_id, sha256_text(text))
        if key not in metric_cache:
            metric_cache[key] = _structural_metrics(source, text, tokenizer, source_audit)
        return metric_cache[key]

    pristine = {sample_id: score(source, source.text) for sample_id, source in sample_by_id.items()}
    rows: list[MidDevV5ScoredRow] = []

    def append_row(*, row_kind, plan_row_hash, source, planner, tier, budget, replicate, trace_hash, text):
        transformed = score(source, text)
        m = metrics(source, text)
        geometry = m["geometry"]
        values = {
            "plan_row_hash": plan_row_hash,
            "source_group_id": source.match_id,
            "sample_id": source.sample_id,
            "source_label": source.label.value,
            "target_length": source.target_length,
            "planner_or_condition": planner,
            "tier": tier,
            "budget": budget,
            "replicate": replicate,
            "selection_trace_hash": trace_hash,
            "transformed_text_hash": sha256_text(text),
            "pristine_score": pristine[source.sample_id],
            "transformed_score": transformed,
            "residual_geometry_hash": geometry.geometry_hash,
            "residual_inherited_fraction": geometry.residual_inherited_fraction,
            "new_context_opportunity_fraction": geometry.new_context_opportunity_fraction,
            "valid_denominator_ratio": geometry.valid_denominator_ratio,
            "word_edit_rate": m["word_edit_rate"],
            "character_edit_rate": m["character_edit_rate"],
            "token_edit_distance": m["token_edit_distance"],
            "length_ratio": m["length_ratio"],
            "protected_span_violation_count": m["protected_span_violation_count"],
            "hard_invariant_passed": m["hard_invariant_passed"],
        }
        payload = {"algorithm_version": MID_DEV_V5_SCORED_ROW_VERSION, "row_kind": row_kind.value, **values}
        rows.append(MidDevV5ScoredRow(row_kind=row_kind, **values, row_hash=sha256_json(payload)))

    for row in legacy.rows:
        source = sample_by_id[row.sample_id]
        append_row(
            row_kind=MidDevV5ScoredRowKind.LEGACY,
            plan_row_hash=row.plan_row_hash,
            source=source,
            planner=row.condition.value,
            tier=None,
            budget=row.budget,
            replicate=row.replicate,
            trace_hash=row.selection_trace_hash,
            text=row.transformed_text,
        )
    for row in plan.normalized_rows:
        source = sample_by_id[row.sample_id]
        append_row(
            row_kind=MidDevV5ScoredRowKind.NORMALIZED,
            plan_row_hash=row.row_hash,
            source=source,
            planner=row.planner.value,
            tier=row.tier.value,
            budget=None,
            replicate=row.replicate,
            trace_hash=row.selection_trace_hash,
            text=row.transformed_text,
        )
    row_tuple = tuple(rows)
    payload = {
        "algorithm_version": MID_DEV_V5_SCORING_ARTIFACT_VERSION,
        "corpus_artifact_hash": corpus.artifact_hash,
        "source_profile_hash": corpus.source_profile_hash,
        "analysis_split_hash": corpus.analysis_split_hash,
        "development_plan_hash": plan.plan_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "execution_attestation_hash": execution.attestation_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "threshold_registry_hash": registry.registry_hash,
        "detector_identity_hash": registry.detector_identity_hash,
        "independent_source_group_count": 36,
        "source_sample_count": 72,
        "row_hashes": tuple(row.row_hash for row in row_tuple),
    }
    return MidDevV5ScoringArtifact(
        corpus_artifact_hash=corpus.artifact_hash,
        source_profile_hash=corpus.source_profile_hash,
        analysis_split_hash=corpus.analysis_split_hash,
        development_plan_hash=plan.plan_hash,
        normalized_trace_artifact_hash=normalized_traces.artifact_hash,
        execution_attestation_hash=execution.attestation_hash,
        opportunity_audit_hash=source_audit.artifact_hash,
        regime_decision_hash=decision.decision_hash,
        threshold_registry_hash=registry.registry_hash,
        detector_identity_hash=registry.detector_identity_hash,
        independent_source_group_count=36,
        source_sample_count=72,
        rows=row_tuple,
        artifact_hash=sha256_json(payload),
    )
