from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET,
    CalibrationRole,
    MidDevCalibrationMergedManifest,
    validate_calibration_merged_independence,
)
from ..corpus.sample import CorpusSample
from ..detector_calibration import PRIMARY_TARGET_FPR, text_only_weighted_evidence
from ..detectors import CalibrationScope, ComparisonOperator, calibrate_detector
from ..detectors.calibration_selection import _false_positive_count, _normalize_negative_evidence
from ..detectors.calibration_statistics import exact_binomial_interval
from ..detectors.calibration_types import ExactBinomialInterval
from ..hashing import sha256_json
from .detector_opportunity_audit import (
    CalibrationRegimeDecision,
    DetectorOpportunityAuditArtifact,
    build_detector_opportunity_audit_row,
)


MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION = "mid-dev-calibration-threshold-registry-vnext-v1"
MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION = "mid-dev-calibration-threshold-record-vnext-v1"
MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION = "mid-dev-calibration-audit-artifact-vnext-v1"
MID_DEV_CALIBRATION_CONFIDENCE_LEVEL = 0.95


class MidDevCalibrationAuditError(ValueError):
    pass


def _regime_hash(decision: CalibrationRegimeDecision, regime_id: str) -> str:
    require_clean_string("regime_id", regime_id)
    return sha256_json({
        "algorithm_version": "mid-dev-calibration-regime-identity-v1",
        "regime_decision_hash": decision.decision_hash,
        "regime_id": regime_id,
    })


def _length_policy_id(decision: CalibrationRegimeDecision) -> str:
    return f"vnext-{decision.mode.value.lower()}-{decision.decision_hash[:16]}"


def _validate_manifest_samples(
    samples: Sequence[CorpusSample],
    manifest: MidDevCalibrationMergedManifest,
    expected_role: CalibrationRole,
) -> tuple[CorpusSample, ...]:
    if not isinstance(manifest, MidDevCalibrationMergedManifest):
        raise TypeError("manifest must be MidDevCalibrationMergedManifest")
    if manifest.role is not expected_role:
        raise MidDevCalibrationAuditError("calibration manifest role is incorrect")
    materialized = tuple(samples)
    if len(materialized) != len(manifest.sample_ids) or any(not isinstance(item, CorpusSample) for item in materialized):
        raise MidDevCalibrationAuditError("samples do not match merged manifest size/type")
    by_id = {item.sample_id: item for item in materialized}
    if len(by_id) != len(materialized) or set(by_id) != set(manifest.sample_ids):
        raise MidDevCalibrationAuditError("sample IDs do not match merged manifest")
    ordered = tuple(by_id[item] for item in manifest.sample_ids)
    if tuple(item.record_hash for item in ordered) != manifest.sample_record_hashes:
        raise MidDevCalibrationAuditError("sample record hashes do not match merged manifest")
    if tuple(item.text_sha256 for item in ordered) != manifest.text_sha256s:
        raise MidDevCalibrationAuditError("sample text hashes do not match merged manifest")
    if tuple(item.generation_tokens.continuation_token_hash for item in ordered) != manifest.continuation_token_hashes:
        raise MidDevCalibrationAuditError("sample continuation-token hashes do not match merged manifest")
    if {item.model.identity_hash for item in ordered} != {manifest.model_tokenizer_identity_hash}:
        raise MidDevCalibrationAuditError("sample model/tokenizer identity drifted")
    if {item.watermark.watermark_config_hash for item in ordered} != {manifest.watermark_config_hash}:
        raise MidDevCalibrationAuditError("sample watermark config drifted")
    if {item.watermark.condition_hash for item in ordered} != {manifest.watermark_condition_hash}:
        raise MidDevCalibrationAuditError("sample watermark condition drifted")
    return ordered


def _group_by_frozen_regime(
    samples: Sequence[CorpusSample],
    source_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    retokenize: Callable[[str], Sequence[int]],
) -> dict[str, tuple[CorpusSample, ...]]:
    if decision.opportunity_audit_hash != source_audit.artifact_hash:
        raise MidDevCalibrationAuditError("regime decision is not bound to pristine opportunity audit")
    groups: dict[str, list[CorpusSample]] = {}
    for sample in samples:
        row = build_detector_opportunity_audit_row(
            sample,
            ngram_len=source_audit.ngram_len,
            context_history_size=source_audit.context_history_size,
            retokenize=retokenize,
        )
        if not row.tokenizer_round_trip_ok:
            raise MidDevCalibrationAuditError("calibration sample failed tokenizer round-trip")
        regime = decision.regime_id_for(row.requested_generation_length, row.root_valid_eligible_observation_count)
        groups.setdefault(regime, []).append(sample)
    return {key: tuple(value) for key, value in sorted(groups.items())}


@dataclass(frozen=True, slots=True)
class FrozenCalibrationThresholdRecord:
    algorithm_version: str
    regime_id: str
    calibration_regime_hash: str
    regime_decision_hash: str
    select_manifest_hash: str
    select_count: int
    calibration_bundle_hash: str
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    target_fpr: float
    comparison_operator: str
    select_false_positive_count: int
    select_empirical_fpr: float
    select_fpr_interval: ExactBinomialInterval
    length_policy_id: str
    record_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION:
            raise ValueError("unsupported threshold record version")
        for name in ("regime_id", "comparison_operator", "length_policy_id"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "calibration_regime_hash", "regime_decision_hash", "select_manifest_hash", "calibration_bundle_hash",
            "detector_identity_hash", "threshold_hash", "record_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("select_count", self.select_count)
        require_int("select_false_positive_count", self.select_false_positive_count)
        if self.select_count < MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET:
            raise ValueError("select_count is below serious 1% development minimum")
        if not 0 <= self.select_false_positive_count <= self.select_count:
            raise ValueError("invalid select false-positive count")
        for name in ("threshold_value", "target_fpr", "select_empirical_fpr"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if not 0.0 <= self.threshold_value <= 1.0 or not 0.0 <= self.select_empirical_fpr <= 1.0:
            raise ValueError("threshold/FPR must be in [0,1]")
        if self.target_fpr != PRIMARY_TARGET_FPR:
            raise ValueError("vNext target FPR must be 1%")
        if self.comparison_operator != ComparisonOperator.GREATER_THAN_OR_EQUAL.value:
            raise ValueError("vNext threshold operator must be >=")
        if self.select_empirical_fpr != self.select_false_positive_count / self.select_count:
            raise ValueError("select empirical FPR does not match count")
        if self.select_fpr_interval != exact_binomial_interval(
            self.select_false_positive_count, self.select_count, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL
        ):
            raise ValueError("select exact interval mismatch")
        if self.record_hash != sha256_json(self.payload()):
            raise ValueError("threshold record hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "record_hash"}


@dataclass(frozen=True, slots=True)
class FrozenCalibrationThresholdRegistry:
    algorithm_version: str
    regime_decision_hash: str
    opportunity_audit_hash: str
    select_manifest_hash: str
    detector_identity_hash: str
    records: tuple[FrozenCalibrationThresholdRecord, ...]
    registry_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION:
            raise ValueError("unsupported threshold registry version")
        for name in ("regime_decision_hash", "opportunity_audit_hash", "select_manifest_hash", "detector_identity_hash", "registry_hash"):
            require_sha256(name, getattr(self, name))
        if not self.records or tuple(sorted(self.records, key=lambda item: item.regime_id)) != self.records:
            raise ValueError("registry records must be non-empty and canonical")
        if len({item.regime_id for item in self.records}) != len(self.records):
            raise ValueError("registry regime IDs must be unique")
        if {item.regime_decision_hash for item in self.records} != {self.regime_decision_hash}:
            raise ValueError("registry decision binding drifted")
        if {item.select_manifest_hash for item in self.records} != {self.select_manifest_hash}:
            raise ValueError("registry select manifest binding drifted")
        if {item.detector_identity_hash for item in self.records} != {self.detector_identity_hash}:
            raise ValueError("registry detector identity drifted")
        if self.registry_hash != sha256_json(self.payload()):
            raise ValueError("registry hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "regime_decision_hash": self.regime_decision_hash,
            "opportunity_audit_hash": self.opportunity_audit_hash,
            "select_manifest_hash": self.select_manifest_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "record_hashes": tuple(item.record_hash for item in self.records),
        }


def build_frozen_calibration_threshold_registry(
    select_samples: Sequence[CorpusSample],
    select_manifest: MidDevCalibrationMergedManifest,
    source_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    *,
    retokenize: Callable[[str], Sequence[int]],
    adapter,
) -> FrozenCalibrationThresholdRegistry:
    ordered = _validate_manifest_samples(select_samples, select_manifest, CalibrationRole.SELECT)
    if select_manifest.model_tokenizer_identity_hash != source_audit.model_tokenizer_identity_hash:
        raise MidDevCalibrationAuditError("CAL-SELECT model/tokenizer identity differs from opportunity audit")
    if select_manifest.watermark_config_hash != source_audit.watermark_config_hash or select_manifest.watermark_condition_hash != source_audit.watermark_condition_hash:
        raise MidDevCalibrationAuditError("CAL-SELECT watermark identity differs from opportunity audit")
    groups = _group_by_frozen_regime(ordered, source_audit, decision, retokenize)
    records: list[FrozenCalibrationThresholdRecord] = []
    detector_identity_hash: str | None = None
    length_policy_id = _length_policy_id(decision)
    for regime_id, samples in groups.items():
        if len(samples) < MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET:
            raise MidDevCalibrationAuditError(f"CAL-SELECT regime {regime_id} has fewer than 1000 negatives")
        evidence = tuple(text_only_weighted_evidence(sample, adapter) for sample in samples)
        scope = CalibrationScope.create(
            corpus_id=select_manifest.manifest_hash,
            population_id=f"mid-dev-vnext-cal-select-{regime_id}",
            length_policy_id=length_policy_id,
            token_track="text_only",
            prompt_boundary_mode="continuation_only",
        )
        bundle = calibrate_detector(
            evidence,
            scope,
            target_fprs=(PRIMARY_TARGET_FPR,),
            comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
            confidence_level=MID_DEV_CALIBRATION_CONFIDENCE_LEVEL,
        )
        threshold = bundle.thresholds[0]
        current_identity = bundle.detector_identity.identity_hash
        if detector_identity_hash is None:
            detector_identity_hash = current_identity
        elif detector_identity_hash != current_identity:
            raise MidDevCalibrationAuditError("CAL-SELECT regimes have different detector identities")
        payload = {
            "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
            "regime_id": regime_id,
            "calibration_regime_hash": _regime_hash(decision, regime_id),
            "regime_decision_hash": decision.decision_hash,
            "select_manifest_hash": select_manifest.manifest_hash,
            "select_count": len(samples),
            "calibration_bundle_hash": bundle.bundle_hash,
            "detector_identity_hash": current_identity,
            "threshold_hash": threshold.threshold_hash,
            "threshold_value": threshold.value,
            "target_fpr": PRIMARY_TARGET_FPR,
            "comparison_operator": threshold.comparison_operator.value,
            "select_false_positive_count": threshold.false_positive_count,
            "select_empirical_fpr": threshold.achieved_fpr,
            "select_fpr_interval": threshold.fpr_interval,
            "length_policy_id": length_policy_id,
        }
        records.append(FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload)))
    if detector_identity_hash is None:
        raise MidDevCalibrationAuditError("CAL-SELECT produced no regimes")
    record_tuple = tuple(sorted(records, key=lambda item: item.regime_id))
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        "regime_decision_hash": decision.decision_hash,
        "opportunity_audit_hash": source_audit.artifact_hash,
        "select_manifest_hash": select_manifest.manifest_hash,
        "detector_identity_hash": detector_identity_hash,
        "record_hashes": tuple(item.record_hash for item in record_tuple),
    }
    return FrozenCalibrationThresholdRegistry(
        MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION, decision.decision_hash, source_audit.artifact_hash,
        select_manifest.manifest_hash, detector_identity_hash, record_tuple, sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class CalibrationAuditArtifact:
    algorithm_version: str
    model_tokenizer_identity_hash: str
    detector_identity_hash: str
    calibration_regime_hash: str
    regime_id: str
    regime_decision_hash: str
    select_manifest_hash: str
    select_count: int
    threshold_hash: str
    threshold_value: float
    target_fpr: float
    comparison_operator: str
    select_false_positive_count: int
    select_fpr_interval: ExactBinomialInterval
    audit_manifest_hash: str
    audit_count: int
    audit_false_positive_count: int
    audit_fpr: float
    audit_fpr_interval: ExactBinomialInterval
    length_policy_id: str
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION:
            raise ValueError("unsupported calibration audit artifact version")
        for name in ("regime_id", "comparison_operator", "length_policy_id"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "model_tokenizer_identity_hash", "detector_identity_hash", "calibration_regime_hash", "regime_decision_hash",
            "select_manifest_hash", "threshold_hash", "audit_manifest_hash", "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in ("select_count", "select_false_positive_count", "audit_count", "audit_false_positive_count"):
            require_int(name, getattr(self, name))
        if self.select_count < MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET or self.audit_count < MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET:
            raise ValueError("select/audit count is below serious 1% development minimum")
        if not 0 <= self.select_false_positive_count <= self.select_count or not 0 <= self.audit_false_positive_count <= self.audit_count:
            raise ValueError("invalid false-positive count")
        for name in ("threshold_value", "target_fpr", "audit_fpr"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if self.target_fpr != PRIMARY_TARGET_FPR or self.comparison_operator != ComparisonOperator.GREATER_THAN_OR_EQUAL.value:
            raise ValueError("frozen threshold target/operator drifted")
        if self.audit_fpr != self.audit_false_positive_count / self.audit_count:
            raise ValueError("audit FPR does not match count")
        if self.select_fpr_interval != exact_binomial_interval(self.select_false_positive_count, self.select_count, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL):
            raise ValueError("select exact interval mismatch")
        if self.audit_fpr_interval != exact_binomial_interval(self.audit_false_positive_count, self.audit_count, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL):
            raise ValueError("audit exact interval mismatch")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("calibration audit artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "artifact_hash"}


def audit_frozen_calibration_threshold_registry(
    registry: FrozenCalibrationThresholdRegistry,
    audit_samples: Sequence[CorpusSample],
    audit_manifest: MidDevCalibrationMergedManifest,
    select_manifest: MidDevCalibrationMergedManifest,
    source_audit: DetectorOpportunityAuditArtifact,
    decision: CalibrationRegimeDecision,
    *,
    retokenize: Callable[[str], Sequence[int]],
    adapter,
) -> tuple[CalibrationAuditArtifact, ...]:
    if not isinstance(registry, FrozenCalibrationThresholdRegistry):
        raise TypeError("registry must be FrozenCalibrationThresholdRegistry")
    validate_calibration_merged_independence(select_manifest, audit_manifest)
    if registry.select_manifest_hash != select_manifest.manifest_hash:
        raise MidDevCalibrationAuditError("threshold registry does not bind supplied CAL-SELECT manifest")
    if registry.regime_decision_hash != decision.decision_hash or registry.opportunity_audit_hash != source_audit.artifact_hash:
        raise MidDevCalibrationAuditError("threshold registry decision/opportunity binding drifted")
    if audit_manifest.model_tokenizer_identity_hash != source_audit.model_tokenizer_identity_hash:
        raise MidDevCalibrationAuditError("CAL-AUDIT model/tokenizer identity differs from opportunity audit")
    if audit_manifest.watermark_config_hash != source_audit.watermark_config_hash or audit_manifest.watermark_condition_hash != source_audit.watermark_condition_hash:
        raise MidDevCalibrationAuditError("CAL-AUDIT watermark identity differs from opportunity audit")
    ordered = _validate_manifest_samples(audit_samples, audit_manifest, CalibrationRole.AUDIT)
    groups = _group_by_frozen_regime(ordered, source_audit, decision, retokenize)
    frozen_records = {item.regime_id: item for item in registry.records}
    if set(groups) != set(frozen_records):
        raise MidDevCalibrationAuditError("CAL-AUDIT regime set differs from frozen CAL-SELECT registry")
    artifacts: list[CalibrationAuditArtifact] = []
    for regime_id, samples in groups.items():
        if len(samples) < MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET:
            raise MidDevCalibrationAuditError(f"CAL-AUDIT regime {regime_id} has fewer than 1000 negatives")
        frozen = frozen_records[regime_id]
        evidence = tuple(text_only_weighted_evidence(sample, adapter) for sample in samples)
        ordered_evidence, identity = _normalize_negative_evidence(evidence)
        if identity.identity_hash != registry.detector_identity_hash:
            raise MidDevCalibrationAuditError("CAL-AUDIT detector identity differs from frozen threshold registry")
        scores = tuple(sorted(item.raw_score for item in ordered_evidence))
        false_positives = _false_positive_count(scores, frozen.threshold_value, ComparisonOperator.GREATER_THAN_OR_EQUAL)
        audit_count = len(ordered_evidence)
        payload = {
            "algorithm_version": MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
            "model_tokenizer_identity_hash": audit_manifest.model_tokenizer_identity_hash,
            "detector_identity_hash": registry.detector_identity_hash,
            "calibration_regime_hash": frozen.calibration_regime_hash,
            "regime_id": regime_id,
            "regime_decision_hash": decision.decision_hash,
            "select_manifest_hash": select_manifest.manifest_hash,
            "select_count": frozen.select_count,
            "threshold_hash": frozen.threshold_hash,
            "threshold_value": frozen.threshold_value,
            "target_fpr": frozen.target_fpr,
            "comparison_operator": frozen.comparison_operator,
            "select_false_positive_count": frozen.select_false_positive_count,
            "select_fpr_interval": frozen.select_fpr_interval,
            "audit_manifest_hash": audit_manifest.manifest_hash,
            "audit_count": audit_count,
            "audit_false_positive_count": false_positives,
            "audit_fpr": false_positives / audit_count,
            "audit_fpr_interval": exact_binomial_interval(false_positives, audit_count, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL),
            "length_policy_id": frozen.length_policy_id,
        }
        artifacts.append(CalibrationAuditArtifact(**payload, artifact_hash=sha256_json(payload)))
    return tuple(sorted(artifacts, key=lambda item: item.regime_id))
