from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..corpus.mid_dev_calibration_shards import (
    MID_DEV_CALIBRATION_DEFAULT_SHARD_SIZE,
    MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
    CalibrationRole,
    MidDevCalibrationShardPlan,
    build_mid_dev_calibration_shard_plan,
    validate_calibration_role_independence,
)
from ..hashing import sha256_json


MID_DEV_CALIBRATION_READINESS_VERSION = "mid-dev-calibration-readiness-v1"
MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET = MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET
MID_DEV_CALIBRATION_READINESS_SHARD_SIZE = MID_DEV_CALIBRATION_DEFAULT_SHARD_SIZE
MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE = 16


@dataclass(frozen=True, slots=True)
class MidDevCalibrationReadinessPlan:
    algorithm_version: str
    negatives_per_target: int
    shard_size: int
    select_plan: MidDevCalibrationShardPlan
    audit_plan: MidDevCalibrationShardPlan
    select_plan_hash: str
    audit_plan_hash: str
    role_independence_hash: str
    readiness_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_READINESS_VERSION:
            raise ValueError("unsupported calibration readiness version")
        for name, expected in (
            ("negatives_per_target", MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET),
            ("shard_size", MID_DEV_CALIBRATION_READINESS_SHARD_SIZE),
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value != expected:
                raise ValueError(f"{name} drifted from preferred calibration readiness design")
        if not isinstance(self.select_plan, MidDevCalibrationShardPlan) or not isinstance(self.audit_plan, MidDevCalibrationShardPlan):
            raise TypeError("readiness plans must be MidDevCalibrationShardPlan values")
        if self.select_plan.role is not CalibrationRole.SELECT or self.audit_plan.role is not CalibrationRole.AUDIT:
            raise ValueError("readiness plan roles must be CAL-SELECT then CAL-AUDIT")
        if self.select_plan.negatives_per_target != self.negatives_per_target or self.audit_plan.negatives_per_target != self.negatives_per_target:
            raise ValueError("readiness plan counts drifted")
        if self.select_plan.shard_size != self.shard_size or self.audit_plan.shard_size != self.shard_size:
            raise ValueError("readiness shard sizes drifted")
        if len(self.select_plan.shards) != MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE:
            raise ValueError("CAL-SELECT must contain exactly 16 canonical shards")
        if len(self.audit_plan.shards) != MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE:
            raise ValueError("CAL-AUDIT must contain exactly 16 canonical shards")
        for name in ("select_plan_hash", "audit_plan_hash", "role_independence_hash", "readiness_hash"):
            require_sha256(name, getattr(self, name))
        if self.select_plan_hash != self.select_plan.plan_hash or self.audit_plan_hash != self.audit_plan.plan_hash:
            raise ValueError("readiness plan hashes do not bind nested shard plans")
        expected_independence = validate_calibration_role_independence(self.select_plan, self.audit_plan)
        if self.role_independence_hash != expected_independence:
            raise ValueError("CAL-SELECT/CAL-AUDIT plan independence hash does not replay")
        if self.readiness_hash != sha256_json(self.payload()):
            raise ValueError("calibration readiness hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "negatives_per_target": self.negatives_per_target,
            "shard_size": self.shard_size,
            "select_plan_hash": self.select_plan_hash,
            "audit_plan_hash": self.audit_plan_hash,
            "role_independence_hash": self.role_independence_hash,
        }


def build_mid_dev_calibration_readiness_plan() -> MidDevCalibrationReadinessPlan:
    select_plan = build_mid_dev_calibration_shard_plan(
        CalibrationRole.SELECT,
        negatives_per_target=MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
        shard_size=MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
    )
    audit_plan = build_mid_dev_calibration_shard_plan(
        CalibrationRole.AUDIT,
        negatives_per_target=MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
        shard_size=MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
    )
    independence_hash = validate_calibration_role_independence(select_plan, audit_plan)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_READINESS_VERSION,
        "negatives_per_target": MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
        "shard_size": MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
        "select_plan_hash": select_plan.plan_hash,
        "audit_plan_hash": audit_plan.plan_hash,
        "role_independence_hash": independence_hash,
    }
    return MidDevCalibrationReadinessPlan(
        algorithm_version=MID_DEV_CALIBRATION_READINESS_VERSION,
        negatives_per_target=MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
        shard_size=MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
        select_plan=select_plan,
        audit_plan=audit_plan,
        select_plan_hash=select_plan.plan_hash,
        audit_plan_hash=audit_plan.plan_hash,
        role_independence_hash=independence_hash,
        readiness_hash=sha256_json(payload),
    )


FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN = build_mid_dev_calibration_readiness_plan()
