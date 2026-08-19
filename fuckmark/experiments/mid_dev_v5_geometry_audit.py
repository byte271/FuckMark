from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .._validation import require_int, require_sha256
from ..detector_calibration import encode_text
from ..hashing import sha256_json, sha256_text
from .detector_opportunity_audit import DetectorOpportunityAuditArtifact
from .mid_dev_plan_v5 import MidDevDevelopmentPlanV5
from .mid_dev_v5_scoring import MidDevV5ScoringArtifact
from .residual_signal_geometry import compute_residual_signal_geometry


MID_DEV_V5_GEOMETRY_AUDIT_ROW_VERSION = "mid-dev-v5-geometry-audit-row-v1"
MID_DEV_V5_GEOMETRY_AUDIT_VERSION = "mid-dev-v5-geometry-audit-v1"
MID_DEV_V5_REPETITION_MASK_GROWTH_CAP = 0


@dataclass(frozen=True, slots=True)
class MidDevV5GeometryAuditRow:
    scored_row_hash: str
    plan_row_hash: str
    sample_id: str
    transformed_text_hash: str
    residual_geometry_hash: str
    root_valid_observation_count: int
    final_valid_observation_count: int
    repetition_mask_delta: int
    eos_mask_delta: int
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    alignment_distance: int
    row_hash: str

    def __post_init__(self) -> None:
        for name in (
            "scored_row_hash",
            "plan_row_hash",
            "transformed_text_hash",
            "residual_geometry_hash",
            "row_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        for name in (
            "root_valid_observation_count",
            "final_valid_observation_count",
            "repetition_mask_delta",
            "eos_mask_delta",
            "alignment_distance",
        ):
            require_int(name, getattr(self, name))
        if self.root_valid_observation_count <= 0 or self.final_valid_observation_count <= 0:
            raise ValueError("geometry audit requires positive valid observation counts")
        if self.alignment_distance < 0:
            raise ValueError("alignment_distance must be non-negative")
        for name in (
            "residual_inherited_fraction",
            "new_context_opportunity_fraction",
            "valid_denominator_ratio",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if self.residual_inherited_fraction > 1.0 or self.new_context_opportunity_fraction > 1.0:
            raise ValueError("RIF/NCF must be in [0,1]")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("geometry audit row hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevV5GeometryAuditRow":
        payload = {"algorithm_version": MID_DEV_V5_GEOMETRY_AUDIT_ROW_VERSION, **values}
        return cls(**values, row_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_GEOMETRY_AUDIT_ROW_VERSION,
            **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"},
        }


@dataclass(frozen=True, slots=True)
class MidDevV5GeometryAuditArtifact:
    corpus_artifact_hash: str
    development_plan_hash: str
    scoring_artifact_hash: str
    opportunity_audit_hash: str
    repetition_mask_growth_cap: int
    rows: tuple[MidDevV5GeometryAuditRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "corpus_artifact_hash",
            "development_plan_hash",
            "scoring_artifact_hash",
            "opportunity_audit_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("repetition_mask_growth_cap", self.repetition_mask_growth_cap)
        if self.repetition_mask_growth_cap != MID_DEV_V5_REPETITION_MASK_GROWTH_CAP:
            raise ValueError("repetition-mask growth cap drifted")
        if not isinstance(self.rows, tuple) or len(self.rows) != 8136:
            raise ValueError("geometry audit requires exactly 8136 scored rows")
        if any(not isinstance(row, MidDevV5GeometryAuditRow) for row in self.rows):
            raise TypeError("geometry audit contains invalid row")
        if len({row.scored_row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("geometry audit scored-row bindings must be unique")
        if len({row.row_hash for row in self.rows}) != len(self.rows):
            raise ValueError("geometry audit row hashes must be unique")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("geometry audit artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_GEOMETRY_AUDIT_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "development_plan_hash": self.development_plan_hash,
            "scoring_artifact_hash": self.scoring_artifact_hash,
            "opportunity_audit_hash": self.opportunity_audit_hash,
            "repetition_mask_growth_cap": self.repetition_mask_growth_cap,
            "row_hashes": tuple(row.row_hash for row in self.rows),
        }


def build_mid_dev_v5_geometry_audit(
    corpus: Any,
    plan: MidDevDevelopmentPlanV5,
    scoring: MidDevV5ScoringArtifact,
    source_audit: DetectorOpportunityAuditArtifact,
    tokenizer: Any,
) -> MidDevV5GeometryAuditArtifact:
    if scoring.corpus_artifact_hash != corpus.artifact_hash:
        raise ValueError("geometry audit corpus/scoring mismatch")
    if scoring.development_plan_hash != plan.plan_hash:
        raise ValueError("geometry audit plan/scoring mismatch")
    if scoring.opportunity_audit_hash != source_audit.artifact_hash:
        raise ValueError("geometry audit opportunity/scoring mismatch")
    samples = {sample.sample_id: sample for sample in corpus.manifest.samples}
    if len(samples) != 72:
        raise ValueError("geometry audit requires exactly 72 source samples")
    text_by_plan_hash: dict[str, str] = {}
    for row in plan.legacy_plan.rows:
        if row.plan_row_hash in text_by_plan_hash:
            raise ValueError("duplicate legacy plan row hash")
        text_by_plan_hash[row.plan_row_hash] = row.transformed_text
    for row in plan.normalized_rows:
        if row.row_hash in text_by_plan_hash:
            raise ValueError("duplicate normalized plan row hash")
        text_by_plan_hash[row.row_hash] = row.transformed_text
    geometry_cache: dict[tuple[str, str], Any] = {}
    rows: list[MidDevV5GeometryAuditRow] = []
    for scored in scoring.rows:
        source = samples.get(scored.sample_id)
        if source is None:
            raise ValueError("scored row references unknown sample")
        text = text_by_plan_hash.get(scored.plan_row_hash)
        if text is None:
            raise ValueError("scored row references unknown plan row")
        if sha256_text(text) != scored.transformed_text_hash:
            raise ValueError("plan/scoring transformed text hash mismatch")
        if source.text_only_tokens is None:
            raise ValueError("source is missing frozen text-only tokens")
        key = (source.sample_id, scored.transformed_text_hash)
        geometry = geometry_cache.get(key)
        if geometry is None:
            final_tokens = tuple(encode_text(tokenizer, text))
            eos = source.model.eos_token_id
            if isinstance(eos, bool) or not isinstance(eos, int) or eos < 0:
                raise ValueError("source tokenizer must define eos_token_id")
            geometry = compute_residual_signal_geometry(
                source.text_only_tokens.token_ids,
                final_tokens,
                eos_token_id=eos,
                ngram_len=source_audit.ngram_len,
                context_history_size=source_audit.context_history_size,
            )
            geometry_cache[key] = geometry
        if geometry.geometry_hash != scored.residual_geometry_hash:
            raise ValueError("scoring residual geometry hash does not replay")
        if geometry.residual_inherited_fraction != scored.residual_inherited_fraction:
            raise ValueError("scoring RIF does not replay")
        if geometry.new_context_opportunity_fraction != scored.new_context_opportunity_fraction:
            raise ValueError("scoring NCF does not replay")
        if geometry.valid_denominator_ratio != scored.valid_denominator_ratio:
            raise ValueError("scoring VDR does not replay")
        if geometry.alignment_distance != scored.token_edit_distance:
            raise ValueError("scoring token edit distance does not replay")
        rows.append(
            MidDevV5GeometryAuditRow.create(
                scored_row_hash=scored.row_hash,
                plan_row_hash=scored.plan_row_hash,
                sample_id=scored.sample_id,
                transformed_text_hash=scored.transformed_text_hash,
                residual_geometry_hash=geometry.geometry_hash,
                root_valid_observation_count=geometry.root_valid_observation_count,
                final_valid_observation_count=geometry.final_valid_observation_count,
                repetition_mask_delta=geometry.repetition_mask_delta,
                eos_mask_delta=geometry.eos_mask_delta,
                residual_inherited_fraction=geometry.residual_inherited_fraction,
                new_context_opportunity_fraction=geometry.new_context_opportunity_fraction,
                valid_denominator_ratio=geometry.valid_denominator_ratio,
                alignment_distance=geometry.alignment_distance,
            )
        )
    materialized = tuple(rows)
    payload = {
        "algorithm_version": MID_DEV_V5_GEOMETRY_AUDIT_VERSION,
        "corpus_artifact_hash": corpus.artifact_hash,
        "development_plan_hash": plan.plan_hash,
        "scoring_artifact_hash": scoring.artifact_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "repetition_mask_growth_cap": MID_DEV_V5_REPETITION_MASK_GROWTH_CAP,
        "row_hashes": tuple(row.row_hash for row in materialized),
    }
    return MidDevV5GeometryAuditArtifact(
        corpus_artifact_hash=corpus.artifact_hash,
        development_plan_hash=plan.plan_hash,
        scoring_artifact_hash=scoring.artifact_hash,
        opportunity_audit_hash=source_audit.artifact_hash,
        repetition_mask_growth_cap=MID_DEV_V5_REPETITION_MASK_GROWTH_CAP,
        rows=materialized,
        artifact_hash=sha256_json(payload),
    )
