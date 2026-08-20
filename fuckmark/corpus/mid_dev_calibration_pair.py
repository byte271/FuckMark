from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev_calibration_merged import MidDevCalibrationMergedArtifact
from .mid_dev_calibration_shards import (
    CalibrationRole,
    validate_calibration_merged_independence,
)


MID_DEV_CALIBRATION_PAIR_VERSION = "mid-dev-calibration-pair-independence-v1"


@dataclass(frozen=True, slots=True)
class MidDevCalibrationPairArtifact:
    algorithm_version: str
    readiness_hash: str
    opportunity_audit_hash: str
    regime_decision_hash: str
    select_plan_hash: str
    audit_plan_hash: str
    select_artifact_hash: str
    audit_artifact_hash: str
    select_manifest_hash: str
    audit_manifest_hash: str
    merged_independence_hash: str
    sample_count_per_role: int
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_PAIR_VERSION:
            raise ValueError("unsupported calibration pair artifact version")
        for name in (
            "readiness_hash",
            "opportunity_audit_hash",
            "regime_decision_hash",
            "select_plan_hash",
            "audit_plan_hash",
            "select_artifact_hash",
            "audit_artifact_hash",
            "select_manifest_hash",
            "audit_manifest_hash",
            "merged_independence_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("sample_count_per_role", self.sample_count_per_role)
        if self.sample_count_per_role <= 0:
            raise ValueError("sample_count_per_role must be positive")
        if self.select_plan_hash == self.audit_plan_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT plans must differ")
        if self.select_artifact_hash == self.audit_artifact_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT merged artifacts must differ")
        if self.select_manifest_hash == self.audit_manifest_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT manifests must differ")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("calibration pair artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "artifact_hash"}


def build_mid_dev_calibration_pair_artifact(
    select: MidDevCalibrationMergedArtifact,
    audit: MidDevCalibrationMergedArtifact,
    *,
    opportunity_audit_hash: str,
    regime_decision_hash: str,
) -> MidDevCalibrationPairArtifact:
    if not isinstance(select, MidDevCalibrationMergedArtifact) or not isinstance(audit, MidDevCalibrationMergedArtifact):
        raise TypeError("select/audit must be MidDevCalibrationMergedArtifact values")
    require_sha256("opportunity_audit_hash", opportunity_audit_hash)
    require_sha256("regime_decision_hash", regime_decision_hash)
    if select.role is not CalibrationRole.SELECT or audit.role is not CalibrationRole.AUDIT:
        raise ValueError("calibration pair must be CAL-SELECT then CAL-AUDIT")
    if select.readiness_hash != audit.readiness_hash:
        raise ValueError("CAL-SELECT and CAL-AUDIT readiness hashes differ")
    if len(select.samples) != len(audit.samples):
        raise ValueError("CAL-SELECT and CAL-AUDIT sample counts differ")
    independence_hash = validate_calibration_merged_independence(select.manifest, audit.manifest)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_PAIR_VERSION,
        "readiness_hash": select.readiness_hash,
        "opportunity_audit_hash": opportunity_audit_hash,
        "regime_decision_hash": regime_decision_hash,
        "select_plan_hash": select.plan_hash,
        "audit_plan_hash": audit.plan_hash,
        "select_artifact_hash": select.artifact_hash,
        "audit_artifact_hash": audit.artifact_hash,
        "select_manifest_hash": select.manifest.manifest_hash,
        "audit_manifest_hash": audit.manifest.manifest_hash,
        "merged_independence_hash": independence_hash,
        "sample_count_per_role": len(select.samples),
    }
    return MidDevCalibrationPairArtifact(**payload, artifact_hash=sha256_json(payload))