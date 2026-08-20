from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.mid_dev import MID_DEV_SOURCE_COUNT, MID_DEV_TARGET_LENGTHS, MidDevAttackArtifact
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .detector_opportunity_audit import (
    CalibrationRegimeDecision,
    DetectorOpportunityAuditArtifact,
)


MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION = "mid-dev-source-opportunity-coverage-v1"
MID_DEV_SOURCE_OPPORTUNITY_ROW_VERSION = "mid-dev-source-opportunity-row-v1"
MID_DEV_SOURCE_REGIME_COUNT_VERSION = "mid-dev-source-regime-count-v1"
MID_DEV_SOURCE_SAMPLE_COUNT = MID_DEV_SOURCE_COUNT * 2


@dataclass(frozen=True, slots=True)
class MidDevSourceOpportunityCoverageRow:
    algorithm_version: str
    sample_id: str
    source_group_id: str
    prompt_id: str
    label: str
    target_length: int
    source_record_hash: str
    text_sha256: str
    opportunity_row_hash: str
    eligible_observation_count: int
    regime_id: str
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_SOURCE_OPPORTUNITY_ROW_VERSION:
            raise ValueError("unsupported source opportunity row version")
        for name in ("sample_id", "source_group_id", "prompt_id", "label", "regime_id"):
            require_clean_string(name, getattr(self, name))
        if self.label not in {item.value for item in WatermarkLabel}:
            raise ValueError("unsupported source opportunity label")
        require_int("target_length", self.target_length)
        if self.target_length not in MID_DEV_TARGET_LENGTHS:
            raise ValueError("source opportunity target length is not frozen")
        require_int("eligible_observation_count", self.eligible_observation_count)
        if self.eligible_observation_count < 0:
            raise ValueError("eligible observation count must be non-negative")
        for name in ("source_record_hash", "text_sha256", "opportunity_row_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("source opportunity row hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "row_hash"
        }

    @classmethod
    def create(
        cls,
        *,
        sample_id: str,
        source_group_id: str,
        prompt_id: str,
        label: str,
        target_length: int,
        source_record_hash: str,
        text_sha256: str,
        opportunity_row_hash: str,
        eligible_observation_count: int,
        regime_id: str,
    ) -> "MidDevSourceOpportunityCoverageRow":
        payload = {
            "algorithm_version": MID_DEV_SOURCE_OPPORTUNITY_ROW_VERSION,
            "sample_id": sample_id,
            "source_group_id": source_group_id,
            "prompt_id": prompt_id,
            "label": label,
            "target_length": target_length,
            "source_record_hash": source_record_hash,
            "text_sha256": text_sha256,
            "opportunity_row_hash": opportunity_row_hash,
            "eligible_observation_count": eligible_observation_count,
            "regime_id": regime_id,
        }
        return cls(**payload, row_hash=sha256_json(payload))


@dataclass(frozen=True, slots=True)
class MidDevSourceRegimeCount:
    algorithm_version: str
    regime_id: str
    sample_count: int
    count_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_SOURCE_REGIME_COUNT_VERSION:
            raise ValueError("unsupported source regime count version")
        require_clean_string("regime_id", self.regime_id)
        require_int("sample_count", self.sample_count)
        if self.sample_count <= 0:
            raise ValueError("source regime sample count must be positive")
        require_sha256("count_hash", self.count_hash)
        if self.count_hash != sha256_json(self.payload()):
            raise ValueError("source regime count hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "regime_id": self.regime_id,
            "sample_count": self.sample_count,
        }

    @classmethod
    def create(cls, regime_id: str, sample_count: int) -> "MidDevSourceRegimeCount":
        payload = {
            "algorithm_version": MID_DEV_SOURCE_REGIME_COUNT_VERSION,
            "regime_id": regime_id,
            "sample_count": sample_count,
        }
        return cls(**payload, count_hash=sha256_json(payload))


@dataclass(frozen=True, slots=True)
class MidDevSourceOpportunityCoverageArtifact:
    algorithm_version: str
    calibration_opportunity_audit_hash: str
    regime_decision_hash: str
    source_corpus_artifact_hash: str
    source_manifest_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    source_opportunity_audit_hash: str
    model_tokenizer_identity_hash: str
    source_count: int
    sample_count: int
    rows: tuple[MidDevSourceOpportunityCoverageRow, ...]
    regime_counts: tuple[MidDevSourceRegimeCount, ...]
    required_regime_ids: tuple[str, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION:
            raise ValueError("unsupported source opportunity coverage version")
        for name in (
            "calibration_opportunity_audit_hash",
            "regime_decision_hash",
            "source_corpus_artifact_hash",
            "source_manifest_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "source_opportunity_audit_hash",
            "model_tokenizer_identity_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("source_count", self.source_count)
        require_int("sample_count", self.sample_count)
        if self.source_count != MID_DEV_SOURCE_COUNT:
            raise ValueError("source opportunity coverage requires 36 source groups")
        if self.sample_count != MID_DEV_SOURCE_SAMPLE_COUNT:
            raise ValueError("source opportunity coverage requires 72 source samples")
        if len(self.rows) != self.sample_count:
            raise ValueError("source opportunity row count drifted")
        if any(not isinstance(row, MidDevSourceOpportunityCoverageRow) for row in self.rows):
            raise TypeError("source opportunity rows are invalid")
        if tuple(sorted(self.rows, key=lambda row: row.sample_id)) != self.rows:
            raise ValueError("source opportunity rows must be canonical")
        if len({row.sample_id for row in self.rows}) != self.sample_count:
            raise ValueError("source opportunity sample IDs must be unique")
        if len({row.source_group_id for row in self.rows}) != self.source_count:
            raise ValueError("source opportunity group count drifted")
        labels = Counter(row.label for row in self.rows)
        expected_labels = Counter({
            WatermarkLabel.UNWATERMARKED.value: MID_DEV_SOURCE_COUNT,
            WatermarkLabel.WATERMARKED.value: MID_DEV_SOURCE_COUNT,
        })
        if labels != expected_labels:
            raise ValueError("source opportunity coverage requires matched on/off samples")
        by_group: dict[str, list[MidDevSourceOpportunityCoverageRow]] = {}
        for row in self.rows:
            by_group.setdefault(row.source_group_id, []).append(row)
        expected_pair_labels = {
            WatermarkLabel.UNWATERMARKED.value,
            WatermarkLabel.WATERMARKED.value,
        }
        for values in by_group.values():
            if len(values) != 2:
                raise ValueError("each source opportunity group must contain exactly two samples")
            if {row.label for row in values} != expected_pair_labels:
                raise ValueError("each source opportunity group must contain one matched on/off pair")
            if len({row.prompt_id for row in values}) != 1:
                raise ValueError("matched source opportunity samples must share one prompt")
            if len({row.target_length for row in values}) != 1:
                raise ValueError("matched source opportunity samples must share one target length")
        if any(not isinstance(item, MidDevSourceRegimeCount) for item in self.regime_counts):
            raise TypeError("source regime counts are invalid")
        if tuple(sorted(self.regime_counts, key=lambda item: item.regime_id)) != self.regime_counts:
            raise ValueError("source regime counts must be canonical")
        if sum(item.sample_count for item in self.regime_counts) != self.sample_count:
            raise ValueError("source regime counts do not cover every sample")
        expected_ids = tuple(item.regime_id for item in self.regime_counts)
        if self.required_regime_ids != expected_ids:
            raise ValueError("required regime IDs do not bind regime counts")
        if tuple(sorted(set(self.required_regime_ids))) != self.required_regime_ids:
            raise ValueError("required regime IDs must be unique and sorted")
        if set(self.required_regime_ids) != {row.regime_id for row in self.rows}:
            raise ValueError("required regime IDs do not cover source rows")
        observed = Counter(row.regime_id for row in self.rows)
        if observed != Counter({item.regime_id: item.sample_count for item in self.regime_counts}):
            raise ValueError("source regime counts do not replay rows")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("source opportunity coverage artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "calibration_opportunity_audit_hash": self.calibration_opportunity_audit_hash,
            "regime_decision_hash": self.regime_decision_hash,
            "source_corpus_artifact_hash": self.source_corpus_artifact_hash,
            "source_manifest_hash": self.source_manifest_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "source_opportunity_audit_hash": self.source_opportunity_audit_hash,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "source_count": self.source_count,
            "sample_count": self.sample_count,
            "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in self.rows),
            "regime_counts": tuple(item.payload() | {"count_hash": item.count_hash} for item in self.regime_counts),
            "required_regime_ids": self.required_regime_ids,
        }


def build_mid_dev_source_opportunity_coverage(
    source_corpus: MidDevAttackArtifact,
    calibration_opportunity_audit: DetectorOpportunityAuditArtifact,
    source_opportunity_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
) -> MidDevSourceOpportunityCoverageArtifact:
    if not isinstance(source_corpus, MidDevAttackArtifact):
        raise TypeError("source_corpus must be MidDevAttackArtifact")
    if decision.opportunity_audit_hash != calibration_opportunity_audit.artifact_hash:
        raise ValueError("regime decision does not bind calibration opportunity audit")
    if source_opportunity_audit.model_tokenizer_identity_hash != calibration_opportunity_audit.model_tokenizer_identity_hash:
        raise ValueError("source/calibration opportunity model identity differs")
    if source_opportunity_audit.watermark_config_hash != calibration_opportunity_audit.watermark_config_hash:
        raise ValueError("source/calibration opportunity watermark config differs")
    if source_opportunity_audit.watermark_condition_hash != calibration_opportunity_audit.watermark_condition_hash:
        raise ValueError("source/calibration opportunity watermark condition differs")
    samples = tuple(source_corpus.manifest.samples)
    if len(samples) != MID_DEV_SOURCE_SAMPLE_COUNT:
        raise ValueError("source corpus does not contain 72 samples")
    opportunity_by_id = {row.sample_id: row for row in source_opportunity_audit.rows}
    if len(opportunity_by_id) != MID_DEV_SOURCE_SAMPLE_COUNT:
        raise ValueError("source opportunity audit does not contain 72 unique rows")
    if set(opportunity_by_id) != {sample.sample_id for sample in samples}:
        raise ValueError("source opportunity audit sample IDs differ from source corpus")
    sample_by_id = {sample.sample_id: sample for sample in samples}
    rows = []
    for sample_id in sorted(sample_by_id):
        sample = sample_by_id[sample_id]
        opportunity = opportunity_by_id[sample_id]
        if not opportunity.tokenizer_round_trip_ok:
            raise ValueError("source opportunity audit contains tokenizer round-trip failure")
        if opportunity.model_tokenizer_identity_hash != sample.model.identity_hash:
            raise ValueError("source opportunity row model identity drifted")
        regime_id = decision.regime_id_for(
            opportunity.requested_generation_length,
            opportunity.root_valid_eligible_observation_count,
        )
        rows.append(
            MidDevSourceOpportunityCoverageRow.create(
                sample_id=sample.sample_id,
                source_group_id=sample.match_id,
                prompt_id=sample.prompt_id,
                label=sample.label.value,
                target_length=sample.target_length,
                source_record_hash=sample.record_hash,
                text_sha256=sample.text_sha256,
                opportunity_row_hash=opportunity.row_hash,
                eligible_observation_count=opportunity.root_valid_eligible_observation_count,
                regime_id=regime_id,
            )
        )
    row_tuple = tuple(rows)
    counter = Counter(row.regime_id for row in row_tuple)
    regime_counts = tuple(
        MidDevSourceRegimeCount.create(regime_id, counter[regime_id])
        for regime_id in sorted(counter)
    )
    payload = {
        "algorithm_version": MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
        "calibration_opportunity_audit_hash": calibration_opportunity_audit.artifact_hash,
        "regime_decision_hash": decision.decision_hash,
        "source_corpus_artifact_hash": source_corpus.artifact_hash,
        "source_manifest_hash": source_corpus.manifest.manifest_hash,
        "source_profile_hash": source_corpus.source_profile_hash,
        "analysis_split_hash": source_corpus.analysis_split_hash,
        "source_opportunity_audit_hash": source_opportunity_audit.artifact_hash,
        "model_tokenizer_identity_hash": source_opportunity_audit.model_tokenizer_identity_hash,
        "source_count": source_corpus.source_count,
        "sample_count": len(row_tuple),
        "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in row_tuple),
        "regime_counts": tuple(item.payload() | {"count_hash": item.count_hash} for item in regime_counts),
        "required_regime_ids": tuple(item.regime_id for item in regime_counts),
    }
    return MidDevSourceOpportunityCoverageArtifact(
        algorithm_version=MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
        calibration_opportunity_audit_hash=calibration_opportunity_audit.artifact_hash,
        regime_decision_hash=decision.decision_hash,
        source_corpus_artifact_hash=source_corpus.artifact_hash,
        source_manifest_hash=source_corpus.manifest.manifest_hash,
        source_profile_hash=source_corpus.source_profile_hash,
        analysis_split_hash=source_corpus.analysis_split_hash,
        source_opportunity_audit_hash=source_opportunity_audit.artifact_hash,
        model_tokenizer_identity_hash=source_opportunity_audit.model_tokenizer_identity_hash,
        source_count=source_corpus.source_count,
        sample_count=len(row_tuple),
        rows=row_tuple,
        regime_counts=regime_counts,
        required_regime_ids=tuple(item.regime_id for item in regime_counts),
        artifact_hash=sha256_json(payload),
    )
