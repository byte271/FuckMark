from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .._validation import require_sha256
from ..detector_calibration import PRIMARY_TARGET_FPR
from ..hashing import sha256_json
from .mid_dev_calibration_audit import CalibrationAuditArtifact, FrozenCalibrationThresholdRegistry
from .mid_dev_pre_run_lock import PRE_RUN_CALIBRATION_CONSISTENCY_RULE


MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION = "mid-dev-calibration-audit-registry-v1"
CALIBRATION_AUDIT_UNSTABLE_REASON = "CALIBRATION_AUDIT_FPR_UNSTABLE"


@dataclass(frozen=True, slots=True)
class MidDevCalibrationAuditRegistry:
    algorithm_version: str
    threshold_registry_hash: str
    opportunity_audit_hash: str
    regime_decision_hash: str
    select_manifest_hash: str
    audit_manifest_hash: str
    detector_identity_hash: str
    calibration_consistency_rule: str
    target_fpr: float
    artifacts: tuple[CalibrationAuditArtifact, ...]
    consistency_pass: bool
    unstable_regime_ids: tuple[str, ...]
    registry_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION:
            raise ValueError("unsupported calibration audit registry version")
        for name in (
            "threshold_registry_hash",
            "opportunity_audit_hash",
            "regime_decision_hash",
            "select_manifest_hash",
            "audit_manifest_hash",
            "detector_identity_hash",
            "registry_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.calibration_consistency_rule != PRE_RUN_CALIBRATION_CONSISTENCY_RULE:
            raise ValueError("calibration audit consistency rule drifted")
        if self.target_fpr != PRIMARY_TARGET_FPR:
            raise ValueError("calibration audit registry target FPR must remain 1%")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ValueError("calibration audit registry requires artifacts")
        if tuple(sorted(self.artifacts, key=lambda item: item.regime_id)) != self.artifacts:
            raise ValueError("calibration audit artifacts must be canonical by regime")
        if len({item.regime_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("calibration audit regime IDs must be unique")
        if {item.detector_identity_hash for item in self.artifacts} != {self.detector_identity_hash}:
            raise ValueError("calibration audit detector identity drifted")
        if {item.regime_decision_hash for item in self.artifacts} != {self.regime_decision_hash}:
            raise ValueError("calibration audit regime decision binding drifted")
        if {item.select_manifest_hash for item in self.artifacts} != {self.select_manifest_hash}:
            raise ValueError("calibration audit SELECT manifest binding drifted")
        if {item.audit_manifest_hash for item in self.artifacts} != {self.audit_manifest_hash}:
            raise ValueError("calibration audit AUDIT manifest binding drifted")
        expected_unstable = tuple(
            item.regime_id
            for item in self.artifacts
            if not (item.audit_fpr_interval.lower <= PRIMARY_TARGET_FPR <= item.audit_fpr_interval.upper)
        )
        if self.unstable_regime_ids != expected_unstable:
            raise ValueError("calibration audit unstable regime set does not replay")
        if self.consistency_pass is not (len(expected_unstable) == 0):
            raise ValueError("calibration audit consistency decision does not replay")
        if self.registry_hash != sha256_json(self.payload()):
            raise ValueError("calibration audit registry hash mismatch")

    @property
    def reason_code(self) -> str | None:
        return None if self.consistency_pass else CALIBRATION_AUDIT_UNSTABLE_REASON

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "threshold_registry_hash": self.threshold_registry_hash,
            "opportunity_audit_hash": self.opportunity_audit_hash,
            "regime_decision_hash": self.regime_decision_hash,
            "select_manifest_hash": self.select_manifest_hash,
            "audit_manifest_hash": self.audit_manifest_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "calibration_consistency_rule": self.calibration_consistency_rule,
            "target_fpr": self.target_fpr,
            "artifact_hashes": tuple(item.artifact_hash for item in self.artifacts),
            "consistency_pass": self.consistency_pass,
            "unstable_regime_ids": self.unstable_regime_ids,
        }


def build_mid_dev_calibration_audit_registry(
    threshold_registry: FrozenCalibrationThresholdRegistry,
    artifacts: Sequence[CalibrationAuditArtifact],
) -> MidDevCalibrationAuditRegistry:
    if not isinstance(threshold_registry, FrozenCalibrationThresholdRegistry):
        raise TypeError("threshold_registry must be FrozenCalibrationThresholdRegistry")
    materialized = tuple(sorted(tuple(artifacts), key=lambda item: item.regime_id))
    if not materialized or any(not isinstance(item, CalibrationAuditArtifact) for item in materialized):
        raise TypeError("artifacts must contain CalibrationAuditArtifact values")
    if {item.regime_id for item in materialized} != {item.regime_id for item in threshold_registry.records}:
        raise ValueError("CAL-AUDIT regime set differs from frozen threshold registry")
    select_manifest_hash = threshold_registry.select_manifest_hash
    audit_manifest_hashes = {item.audit_manifest_hash for item in materialized}
    if len(audit_manifest_hashes) != 1:
        raise ValueError("CAL-AUDIT artifacts mix audit manifests")
    audit_manifest_hash = next(iter(audit_manifest_hashes))
    unstable = tuple(
        item.regime_id
        for item in materialized
        if not (item.audit_fpr_interval.lower <= PRIMARY_TARGET_FPR <= item.audit_fpr_interval.upper)
    )
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION,
        "threshold_registry_hash": threshold_registry.registry_hash,
        "opportunity_audit_hash": threshold_registry.opportunity_audit_hash,
        "regime_decision_hash": threshold_registry.regime_decision_hash,
        "select_manifest_hash": select_manifest_hash,
        "audit_manifest_hash": audit_manifest_hash,
        "detector_identity_hash": threshold_registry.detector_identity_hash,
        "calibration_consistency_rule": PRE_RUN_CALIBRATION_CONSISTENCY_RULE,
        "target_fpr": PRIMARY_TARGET_FPR,
        "artifact_hashes": tuple(item.artifact_hash for item in materialized),
        "consistency_pass": len(unstable) == 0,
        "unstable_regime_ids": unstable,
    }
    return MidDevCalibrationAuditRegistry(
        algorithm_version=MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION,
        threshold_registry_hash=threshold_registry.registry_hash,
        opportunity_audit_hash=threshold_registry.opportunity_audit_hash,
        regime_decision_hash=threshold_registry.regime_decision_hash,
        select_manifest_hash=select_manifest_hash,
        audit_manifest_hash=audit_manifest_hash,
        detector_identity_hash=threshold_registry.detector_identity_hash,
        calibration_consistency_rule=PRE_RUN_CALIBRATION_CONSISTENCY_RULE,
        target_fpr=PRIMARY_TARGET_FPR,
        artifacts=materialized,
        consistency_pass=len(unstable) == 0,
        unstable_regime_ids=unstable,
        registry_hash=sha256_json(payload),
    )
