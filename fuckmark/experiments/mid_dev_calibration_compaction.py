from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.mid_dev_calibration_merged import (
    MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
    MidDevCalibrationMergedArtifact,
)
from ..corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION,
    MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
    MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
    CalibrationRole,
    MidDevCalibrationMergedManifest,
)
from ..corpus.sample import CorpusSample
from ..corpus.schema import WatermarkLabel
from ..hashing import sha256_json
from .detector_opportunity_audit import (
    CalibrationRegimeDecision,
    DetectorOpportunityAuditArtifact,
    build_detector_opportunity_audit_row,
)
from .mid_dev_source_opportunity_coverage import MidDevSourceOpportunityCoverageArtifact


MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION = "mid-dev-calibration-compaction-record-v2"
MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE = (
    "GLOBAL_FIRST_OCCURRENCE_DEDUP_TEXT_OR_TOKEN_SHA_IN_FROZEN_CANDIDATE_ORDER;"
    "SELECT_CANONICAL_FIRST_2000_ELSE_FIRST_1000_ELSE_DESCRIPTIVE;"
    "AUDIT_MIRRORS_SELECT_SERIOUS_N"
)
MID_DEV_CALIBRATION_COMPACTED_PROMPT_MANIFEST_VERSION = "mid-dev-calibration-compacted-prompt-manifest-v2"


class CalibrationCompactionStatus(str, Enum):
    SERIOUS_THRESHOLD = "SERIOUS_THRESHOLD"
    COMPUTE_LIMITED_DESCRIPTIVE = "COMPUTE_LIMITED_DESCRIPTIVE"


@dataclass(frozen=True, slots=True)
class MidDevCalibrationCompactionRecord:
    algorithm_version: str
    regime_id: str
    source_sample_count: int
    candidate_count: int
    selected_count: int
    status: CalibrationCompactionStatus
    selected_sample_ids_hash: str
    selected_record_hashes_hash: str
    record_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION:
            raise ValueError("unsupported calibration compaction record version")
        require_clean_string("regime_id", self.regime_id)
        for name in ("source_sample_count", "candidate_count", "selected_count"):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.source_sample_count <= 0:
            raise ValueError("source_sample_count must be positive for required regimes")
        if not isinstance(self.status, CalibrationCompactionStatus):
            raise TypeError("status must be CalibrationCompactionStatus")
        if self.status is CalibrationCompactionStatus.SERIOUS_THRESHOLD:
            if self.selected_count not in (
                MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
                MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
            ):
                raise ValueError("serious calibration regime must select exactly 1000 or 2000 negatives")
            if self.candidate_count < self.selected_count:
                raise ValueError("serious calibration selection exceeds candidate count")
        elif self.selected_count != 0:
            raise ValueError("compute-limited descriptive regime must select zero threshold negatives")
        for name in ("selected_sample_ids_hash", "selected_record_hashes_hash", "record_hash"):
            require_sha256(name, getattr(self, name))
        if self.record_hash != sha256_json(self.payload()):
            raise ValueError("calibration compaction record hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "regime_id": self.regime_id,
            "source_sample_count": self.source_sample_count,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "status": self.status.value,
            "selected_sample_ids_hash": self.selected_sample_ids_hash,
            "selected_record_hashes_hash": self.selected_record_hashes_hash,
        }


def select_calibration_compaction_target(
    candidate_count: int,
) -> tuple[CalibrationCompactionStatus, int]:
    require_int("candidate_count", candidate_count)
    if candidate_count < 0:
        raise ValueError("candidate_count must be non-negative")
    if candidate_count >= MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET:
        return (
            CalibrationCompactionStatus.SERIOUS_THRESHOLD,
            MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
        )
    if candidate_count >= MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET:
        return (
            CalibrationCompactionStatus.SERIOUS_THRESHOLD,
            MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
        )
    return CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE, 0


def _deduplicate_calibration_candidates(
    candidates: Sequence[CorpusSample],
) -> tuple[CorpusSample, ...]:
    """Keep the first raw attempt for each text/token content identity.

    Candidate order is already frozen by the merged calibration plan.  The
    rule is deliberately detector-blind: a later sample is excluded whenever
    either its text SHA or continuation-token SHA was observed earlier.
    """
    seen_text_sha256s: set[str] = set()
    seen_token_sha256s: set[str] = set()
    unique: list[CorpusSample] = []
    for sample in candidates:
        text_sha256 = sample.text_sha256
        token_sha256 = sample.generation_tokens.continuation_token_hash
        if text_sha256 in seen_text_sha256s or token_sha256 in seen_token_sha256s:
            continue
        seen_text_sha256s.add(text_sha256)
        seen_token_sha256s.add(token_sha256)
        unique.append(sample)
    return tuple(unique)


def _record(
    *,
    regime_id: str,
    source_sample_count: int,
    candidates: Sequence[CorpusSample],
    selected_count: int,
    status: CalibrationCompactionStatus,
) -> MidDevCalibrationCompactionRecord:
    selected = tuple(candidates[:selected_count])
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
        "regime_id": regime_id,
        "source_sample_count": source_sample_count,
        "candidate_count": len(candidates),
        "selected_count": selected_count,
        "status": status.value,
        "selected_sample_ids_hash": sha256_json(tuple(item.sample_id for item in selected)),
        "selected_record_hashes_hash": sha256_json(tuple(item.record_hash for item in selected)),
    }
    return MidDevCalibrationCompactionRecord(
        algorithm_version=MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
        regime_id=regime_id,
        source_sample_count=source_sample_count,
        candidate_count=len(candidates),
        selected_count=selected_count,
        status=status,
        selected_sample_ids_hash=payload["selected_sample_ids_hash"],
        selected_record_hashes_hash=payload["selected_record_hashes_hash"],
        record_hash=sha256_json(payload),
    )


def _compacted_manifest(
    candidate: MidDevCalibrationMergedArtifact,
    selected_samples: tuple[CorpusSample, ...],
    *,
    source_coverage_artifact_hash: str,
    regime_decision_hash: str,
    record_hashes: tuple[str, ...],
    select_compaction_provenance_hash: str | None,
) -> MidDevCalibrationMergedManifest:
    if not selected_samples:
        raise ValueError("no serious calibration regimes are available under the frozen compute cap")
    prompt_ids = tuple(sample.prompt_id for sample in selected_samples)
    sample_ids = tuple(sample.sample_id for sample in selected_samples)
    sample_record_hashes = tuple(sample.record_hash for sample in selected_samples)
    text_sha256s = tuple(sample.text_sha256 for sample in selected_samples)
    continuation_token_hashes = tuple(
        sample.generation_tokens.continuation_token_hash for sample in selected_samples
    )
    compacted_prompt_manifest_hash = sha256_json(
        {
            "algorithm_version": MID_DEV_CALIBRATION_COMPACTED_PROMPT_MANIFEST_VERSION,
            "role": candidate.role.value,
            "candidate_manifest_hash": candidate.manifest.manifest_hash,
            "source_coverage_artifact_hash": source_coverage_artifact_hash,
            "regime_decision_hash": regime_decision_hash,
            "selection_rule": MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
            "record_hashes": record_hashes,
            "selected_prompt_ids": prompt_ids,
            "select_compaction_provenance_hash": select_compaction_provenance_hash,
        }
    )
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION,
        "role": candidate.role.value,
        "plan_hash": candidate.plan_hash,
        "prompt_manifest_hash": compacted_prompt_manifest_hash,
        "shard_output_hashes": candidate.manifest.shard_output_hashes,
        "prompt_ids": prompt_ids,
        "sample_ids": sample_ids,
        "sample_record_hashes": sample_record_hashes,
        "text_sha256s": text_sha256s,
        "continuation_token_hashes": continuation_token_hashes,
        "model_tokenizer_identity_hash": candidate.manifest.model_tokenizer_identity_hash,
        "watermark_config_hash": candidate.manifest.watermark_config_hash,
        "watermark_condition_hash": candidate.manifest.watermark_condition_hash,
    }
    return MidDevCalibrationMergedManifest(
        algorithm_version=MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION,
        role=candidate.role,
        plan_hash=candidate.plan_hash,
        prompt_manifest_hash=compacted_prompt_manifest_hash,
        shard_output_hashes=candidate.manifest.shard_output_hashes,
        prompt_ids=prompt_ids,
        sample_ids=sample_ids,
        sample_record_hashes=sample_record_hashes,
        text_sha256s=text_sha256s,
        continuation_token_hashes=continuation_token_hashes,
        model_tokenizer_identity_hash=candidate.manifest.model_tokenizer_identity_hash,
        watermark_config_hash=candidate.manifest.watermark_config_hash,
        watermark_condition_hash=candidate.manifest.watermark_condition_hash,
        manifest_hash=sha256_json(payload),
    )


def build_mid_dev_calibration_compaction(
    candidate: MidDevCalibrationMergedArtifact,
    calibration_opportunity_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    source_coverage: MidDevSourceOpportunityCoverageArtifact,
    *,
    retokenize: Callable[[str], Sequence[int]],
    select_records: Sequence[MidDevCalibrationCompactionRecord] | None = None,
    select_compaction_provenance_hash: str | None = None,
) -> tuple[
    MidDevCalibrationMergedArtifact,
    tuple[MidDevCalibrationCompactionRecord, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    if not isinstance(candidate, MidDevCalibrationMergedArtifact):
        raise TypeError("candidate must be MidDevCalibrationMergedArtifact")
    if decision.opportunity_audit_hash != calibration_opportunity_audit.artifact_hash:
        raise ValueError("regime decision does not bind calibration opportunity audit")
    if source_coverage.calibration_opportunity_audit_hash != calibration_opportunity_audit.artifact_hash:
        raise ValueError("source coverage does not bind calibration opportunity audit")
    if source_coverage.regime_decision_hash != decision.decision_hash:
        raise ValueError("source coverage does not bind frozen regime decision")
    if candidate.manifest.model_tokenizer_identity_hash != calibration_opportunity_audit.model_tokenizer_identity_hash:
        raise ValueError("candidate pool model/tokenizer identity differs from opportunity audit")
    if candidate.manifest.watermark_config_hash != calibration_opportunity_audit.watermark_config_hash:
        raise ValueError("candidate pool watermark config differs from opportunity audit")
    if candidate.manifest.watermark_condition_hash != calibration_opportunity_audit.watermark_condition_hash:
        raise ValueError("candidate pool watermark condition differs from opportunity audit")
    if any(sample.label is not WatermarkLabel.UNWATERMARKED for sample in candidate.samples):
        raise ValueError("calibration candidate pool must contain unwatermarked negatives only")

    # Preserve the raw fixed-compute candidate artifact for provenance, but
    # effective support is computed only from first-occurrence unique content.
    # This runs before regime assignment so one repeated generation can never
    # contribute statistical support more than once anywhere in the pool.
    unique_candidates = _deduplicate_calibration_candidates(candidate.samples)

    required_regimes = source_coverage.required_regime_ids
    source_counts = {item.regime_id: item.sample_count for item in source_coverage.regime_counts}
    grouped: dict[str, list[CorpusSample]] = {regime_id: [] for regime_id in required_regimes}
    for sample in unique_candidates:
        opportunity = build_detector_opportunity_audit_row(
            sample,
            ngram_len=calibration_opportunity_audit.ngram_len,
            context_history_size=calibration_opportunity_audit.context_history_size,
            retokenize=retokenize,
        )
        if not opportunity.tokenizer_round_trip_ok:
            raise ValueError("candidate pool sample failed tokenizer round-trip")
        regime_id = decision.regime_id_for(
            opportunity.requested_generation_length,
            opportunity.root_valid_eligible_observation_count,
        )
        if regime_id in grouped:
            grouped[regime_id].append(sample)

    select_by_regime: dict[str, MidDevCalibrationCompactionRecord] = {}
    if candidate.role is CalibrationRole.SELECT:
        if select_records is not None or select_compaction_provenance_hash is not None:
            raise ValueError("CAL-SELECT compaction cannot consume CAL-AUDIT or prior SELECT state")
    elif candidate.role is CalibrationRole.AUDIT:
        if select_records is None or select_compaction_provenance_hash is None:
            raise ValueError("CAL-AUDIT compaction requires frozen CAL-SELECT compaction records")
        require_sha256("select_compaction_provenance_hash", select_compaction_provenance_hash)
        select_by_regime = {item.regime_id: item for item in select_records}
        if tuple(sorted(select_by_regime)) != required_regimes:
            raise ValueError("CAL-SELECT compaction record set differs from required source regimes")
    else:
        raise TypeError("unsupported calibration role")

    records: list[MidDevCalibrationCompactionRecord] = []
    selected_ids: set[str] = set()
    for regime_id in required_regimes:
        candidates = tuple(grouped[regime_id])
        if candidate.role is CalibrationRole.SELECT:
            status, selected_count = select_calibration_compaction_target(len(candidates))
        else:
            frozen = select_by_regime[regime_id]
            status = frozen.status
            selected_count = frozen.selected_count
            if status is CalibrationCompactionStatus.SERIOUS_THRESHOLD and len(candidates) < selected_count:
                raise ValueError(
                    f"CAL-AUDIT regime {regime_id} cannot mirror frozen CAL-SELECT serious N"
                )
            if status is CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE:
                selected_count = 0
        record = _record(
            regime_id=regime_id,
            source_sample_count=source_counts[regime_id],
            candidates=candidates,
            selected_count=selected_count,
            status=status,
        )
        records.append(record)
        selected_ids.update(item.sample_id for item in candidates[:selected_count])

    record_tuple = tuple(records)
    serious = tuple(
        item.regime_id
        for item in record_tuple
        if item.status is CalibrationCompactionStatus.SERIOUS_THRESHOLD
    )
    descriptive = tuple(
        item.regime_id
        for item in record_tuple
        if item.status is CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE
    )
    selected_samples = tuple(
        sample for sample in candidate.samples if sample.sample_id in selected_ids
    )
    expected_selected = sum(item.selected_count for item in record_tuple)
    if len(selected_samples) != expected_selected:
        raise ValueError("compacted calibration sample selection does not replay")
    if len({sample.text_sha256 for sample in selected_samples}) != len(selected_samples):
        raise ValueError("compacted calibration selection contains duplicate text")
    if len({sample.generation_tokens.continuation_token_hash for sample in selected_samples}) != len(selected_samples):
        raise ValueError("compacted calibration selection contains duplicate continuation tokens")

    manifest = _compacted_manifest(
        candidate,
        selected_samples,
        source_coverage_artifact_hash=source_coverage.artifact_hash,
        regime_decision_hash=decision.decision_hash,
        record_hashes=tuple(item.record_hash for item in record_tuple),
        select_compaction_provenance_hash=select_compaction_provenance_hash,
    )
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
        "role": candidate.role.value,
        "readiness_hash": candidate.readiness_hash,
        "plan_hash": candidate.plan_hash,
        "sample_record_hashes": tuple(sample.record_hash for sample in selected_samples),
        "manifest_hash": manifest.manifest_hash,
    }
    compacted = MidDevCalibrationMergedArtifact(
        algorithm_version=MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
        role=candidate.role,
        readiness_hash=candidate.readiness_hash,
        plan_hash=candidate.plan_hash,
        samples=selected_samples,
        manifest=manifest,
        artifact_hash=sha256_json(payload),
    )
    return compacted, record_tuple, serious, descriptive
