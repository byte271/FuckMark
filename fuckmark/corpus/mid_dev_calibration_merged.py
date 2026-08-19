from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .._validation import require_sha256
from ..hashing import sha256_json
from .mid_dev_calibration_shards import (
    CalibrationRole,
    MidDevCalibrationMergedManifest,
    MidDevCalibrationShardPlan,
    MidDevGeneratedCalibrationShard,
    merge_mid_dev_calibration_shard_outputs,
)
from .sample import CorpusSample


MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION = "mid-dev-calibration-merged-artifact-v1"


@dataclass(frozen=True, slots=True)
class MidDevCalibrationMergedArtifact:
    algorithm_version: str
    role: CalibrationRole
    readiness_hash: str
    plan_hash: str
    samples: tuple[CorpusSample, ...]
    manifest: MidDevCalibrationMergedManifest
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION:
            raise ValueError("unsupported calibration merged artifact version")
        if not isinstance(self.role, CalibrationRole):
            raise TypeError("role must be CalibrationRole")
        for name in ("readiness_hash", "plan_hash", "artifact_hash"):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.manifest, MidDevCalibrationMergedManifest):
            raise TypeError("manifest must be MidDevCalibrationMergedManifest")
        if self.manifest.role is not self.role or self.manifest.plan_hash != self.plan_hash:
            raise ValueError("merged artifact role/plan binding drifted")
        if not isinstance(self.samples, tuple) or not self.samples:
            raise ValueError("merged calibration artifact requires samples")
        if tuple(sample.sample_id for sample in self.samples) != self.manifest.sample_ids:
            raise ValueError("merged artifact samples do not match manifest sample IDs")
        if tuple(sample.record_hash for sample in self.samples) != self.manifest.sample_record_hashes:
            raise ValueError("merged artifact sample record hashes do not match manifest")
        if tuple(sample.text_sha256 for sample in self.samples) != self.manifest.text_sha256s:
            raise ValueError("merged artifact text hashes do not match manifest")
        if len({sample.sample_id for sample in self.samples}) != len(self.samples):
            raise ValueError("merged calibration artifact contains duplicate sample IDs")
        if len({sample.text_sha256 for sample in self.samples}) != len(self.samples):
            raise ValueError("merged calibration artifact contains duplicate text")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("merged calibration artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "role": self.role.value,
            "readiness_hash": self.readiness_hash,
            "plan_hash": self.plan_hash,
            "sample_record_hashes": tuple(sample.record_hash for sample in self.samples),
            "manifest_hash": self.manifest.manifest_hash,
        }


def merge_mid_dev_generated_calibration_shards(
    *,
    readiness_hash: str,
    plan: MidDevCalibrationShardPlan,
    shards: Sequence[MidDevGeneratedCalibrationShard],
) -> MidDevCalibrationMergedArtifact:
    require_sha256("readiness_hash", readiness_hash)
    if not isinstance(plan, MidDevCalibrationShardPlan):
        raise TypeError("plan must be MidDevCalibrationShardPlan")
    shards = tuple(shards)
    if len(shards) != len(plan.shards):
        raise ValueError("generated shard set must contain exactly the frozen plan shard count")
    if any(not isinstance(shard, MidDevGeneratedCalibrationShard) for shard in shards):
        raise TypeError("shards must contain MidDevGeneratedCalibrationShard values")
    manifest = merge_mid_dev_calibration_shard_outputs(
        plan,
        tuple(shard.manifest for shard in shards),
    )
    sample_by_id: dict[str, CorpusSample] = {}
    for shard in shards:
        for sample in shard.samples:
            if sample.sample_id in sample_by_id:
                raise ValueError("duplicate sample ID across generated calibration shards")
            sample_by_id[sample.sample_id] = sample
    if set(sample_by_id) != set(manifest.sample_ids):
        raise ValueError("generated shard samples do not cover merged manifest exactly")
    samples = tuple(sample_by_id[sample_id] for sample_id in manifest.sample_ids)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
        "role": plan.role.value,
        "readiness_hash": readiness_hash,
        "plan_hash": plan.plan_hash,
        "sample_record_hashes": tuple(sample.record_hash for sample in samples),
        "manifest_hash": manifest.manifest_hash,
    }
    return MidDevCalibrationMergedArtifact(
        algorithm_version=MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
        role=plan.role,
        readiness_hash=readiness_hash,
        plan_hash=plan.plan_hash,
        samples=samples,
        manifest=manifest,
        artifact_hash=sha256_json(payload),
    )
