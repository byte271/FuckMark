from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev import MID_DEV_PROMPT_FAMILIES, MID_DEV_TARGET_LENGTHS
from .mid_dev_generation import MidDevGenerationBackend, _build_sample
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusSplit, KeySplit, WatermarkLabel


MID_DEV_CALIBRATION_SHARD_ALGORITHM_VERSION = "mid-dev-calibration-shards-vnext-v1"
MID_DEV_CALIBRATION_SHARD_PLAN_VERSION = "mid-dev-calibration-shard-plan-v1"
MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION = "mid-dev-calibration-shard-output-v2"
MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION = "mid-dev-calibration-merged-manifest-v2"
MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET = 2000
MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET = 1000
MID_DEV_CALIBRATION_DEFAULT_SHARD_SIZE = 250
MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET = 100_000
MID_DEV_CALIBRATION_LICENSE_ID = "LicenseRef-FuckMark-Unspecified"
MID_DEV_CALIBRATION_PROVENANCE = "fuckmark/corpus/mid_dev_calibration_shards.py"
_TARGET_SEED_STRIDE = 100_000


class CalibrationRole(str, Enum):
    SELECT = "CAL-SELECT"
    AUDIT = "CAL-AUDIT"


_ROLE_SEED_BASE = {CalibrationRole.SELECT: 1_710_000, CalibrationRole.AUDIT: 2_710_000}
_ROLE_TOPIC_BASE = {CalibrationRole.SELECT: 10_000_000, CalibrationRole.AUDIT: 20_000_000}
_ROLE_SLUG = {CalibrationRole.SELECT: "select", CalibrationRole.AUDIT: "audit"}


class MidDevCalibrationShardError(ValueError):
    pass


def _role(value: CalibrationRole) -> CalibrationRole:
    if not isinstance(value, CalibrationRole):
        raise TypeError("role must be CalibrationRole")
    return value


def _count(value: int) -> int:
    require_int("negatives_per_target", value)
    if not MID_DEV_CALIBRATION_MINIMUM_NEGATIVES_PER_TARGET <= value <= MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET:
        raise ValueError("negatives_per_target must be between 1000 and 100000")
    return value


def calibration_prompt_source_id(role: CalibrationRole) -> str:
    role = _role(role)
    return f"fuckmark-mid-dev-calibration-vnext-{_ROLE_SLUG[role]}-prompts-v1"


def calibration_prompt_id(role: CalibrationRole, target_length: int, source_index: int) -> str:
    role = _role(role)
    require_int("target_length", target_length)
    require_int("source_index", source_index)
    if target_length not in MID_DEV_TARGET_LENGTHS:
        raise ValueError("target_length must be a frozen MidDev target")
    if not 0 <= source_index < MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET:
        raise ValueError("source_index is outside frozen calibration range")
    return f"middev-cal-vnext-{_ROLE_SLUG[role]}-{target_length}-{source_index:05d}"


def calibration_seed(role: CalibrationRole, target_length: int, source_index: int) -> int:
    role = _role(role)
    if target_length not in MID_DEV_TARGET_LENGTHS:
        raise ValueError("target_length must be a frozen MidDev target")
    require_int("source_index", source_index)
    if not 0 <= source_index < MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET:
        raise ValueError("source_index is outside frozen calibration range")
    return _ROLE_SEED_BASE[role] + MID_DEV_TARGET_LENGTHS.index(target_length) * _TARGET_SEED_STRIDE + source_index


def _prompt_source_hash(role: CalibrationRole, count: int) -> str:
    return sha256_json({
        "algorithm_version": MID_DEV_CALIBRATION_SHARD_ALGORITHM_VERSION,
        "role": role.value,
        "source_id": calibration_prompt_source_id(role),
        "license_id": MID_DEV_CALIBRATION_LICENSE_ID,
        "provenance": MID_DEV_CALIBRATION_PROVENANCE,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "negatives_per_target": count,
        "family_ids": tuple(item.family_id for item in MID_DEV_PROMPT_FAMILIES),
        "seed_base": _ROLE_SEED_BASE[role],
        "target_seed_stride": _TARGET_SEED_STRIDE,
    })


def build_mid_dev_calibration_prompt_records(
    role: CalibrationRole,
    *,
    negatives_per_target: int = MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
) -> tuple[PromptRecord, ...]:
    role = _role(role)
    count = _count(negatives_per_target)
    source_id = calibration_prompt_source_id(role)
    source_hash = _prompt_source_hash(role, count)
    rows: list[PromptRecord] = []
    for target_length in MID_DEV_TARGET_LENGTHS:
        target_slot = MID_DEV_TARGET_LENGTHS.index(target_length)
        for source_index in range(count):
            family = MID_DEV_PROMPT_FAMILIES[source_index % len(MID_DEV_PROMPT_FAMILIES)]
            topic_id = _ROLE_TOPIC_BASE[role] + target_slot * MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET + source_index
            topic = f"ordinary measurement scenario {topic_id:08d} involving routine planning, documentation, comparison, and follow-up"
            rows.append(PromptRecord.create(
                prompt_id=calibration_prompt_id(role, target_length, source_index),
                prompt_family_id=f"cal-vnext-{_ROLE_SLUG[role]}-{family.family_id}",
                domain=family.domain,
                split=CorpusSplit.THRESHOLD_CALIBRATION,
                source_id=source_id,
                source_hash=source_hash,
                license_id=MID_DEV_CALIBRATION_LICENSE_ID,
                provenance=MID_DEV_CALIBRATION_PROVENANCE,
                text=family.template.format(topic=topic, target_length=target_length),
            ))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class MidDevCalibrationShardSpec:
    role: CalibrationRole
    target_length: int
    start_index: int
    end_index_exclusive: int
    prompt_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    shard_id: str
    shard_hash: str

    def __post_init__(self) -> None:
        _role(self.role)
        for name in ("target_length", "start_index", "end_index_exclusive"):
            require_int(name, getattr(self, name))
        if self.target_length not in MID_DEV_TARGET_LENGTHS:
            raise ValueError("invalid shard target length")
        if not 0 <= self.start_index < self.end_index_exclusive <= MID_DEV_CALIBRATION_MAX_NEGATIVES_PER_TARGET:
            raise ValueError("invalid shard range")
        indices = tuple(range(self.start_index, self.end_index_exclusive))
        if self.prompt_ids != tuple(calibration_prompt_id(self.role, self.target_length, i) for i in indices):
            raise ValueError("shard prompt map drifted")
        if self.seeds != tuple(calibration_seed(self.role, self.target_length, i) for i in indices):
            raise ValueError("shard seed map drifted")
        expected_id = f"middev-cal-vnext-{_ROLE_SLUG[self.role]}-{self.target_length}-{self.start_index:05d}-{self.end_index_exclusive:05d}"
        if self.shard_id != expected_id:
            raise ValueError("noncanonical shard id")
        require_sha256("shard_hash", self.shard_hash)
        if self.shard_hash != sha256_json(self.payload()):
            raise ValueError("shard hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "target_length": self.target_length,
            "start_index": self.start_index,
            "end_index_exclusive": self.end_index_exclusive,
            "prompt_ids": self.prompt_ids,
            "seeds": self.seeds,
            "shard_id": self.shard_id,
        }


def _make_shard(role: CalibrationRole, target: int, start: int, end: int) -> MidDevCalibrationShardSpec:
    prompt_ids = tuple(calibration_prompt_id(role, target, i) for i in range(start, end))
    seeds = tuple(calibration_seed(role, target, i) for i in range(start, end))
    shard_id = f"middev-cal-vnext-{_ROLE_SLUG[role]}-{target}-{start:05d}-{end:05d}"
    payload = {
        "role": role.value,
        "target_length": target,
        "start_index": start,
        "end_index_exclusive": end,
        "prompt_ids": prompt_ids,
        "seeds": seeds,
        "shard_id": shard_id,
    }
    return MidDevCalibrationShardSpec(role, target, start, end, prompt_ids, seeds, shard_id, sha256_json(payload))


@dataclass(frozen=True, slots=True)
class MidDevCalibrationShardPlan:
    algorithm_version: str
    role: CalibrationRole
    prompt_source_id: str
    negatives_per_target: int
    shard_size: int
    prompt_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    prompt_manifest_hash: str
    shards: tuple[MidDevCalibrationShardSpec, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_SHARD_PLAN_VERSION:
            raise ValueError("unsupported calibration shard plan version")
        role = _role(self.role)
        count = _count(self.negatives_per_target)
        require_int("shard_size", self.shard_size)
        if not 0 < self.shard_size <= count:
            raise ValueError("invalid shard size")
        if self.prompt_source_id != calibration_prompt_source_id(role):
            raise ValueError("prompt source id drifted")
        expected_prompts = tuple(calibration_prompt_id(role, target, i) for target in MID_DEV_TARGET_LENGTHS for i in range(count))
        expected_seeds = tuple(calibration_seed(role, target, i) for target in MID_DEV_TARGET_LENGTHS for i in range(count))
        if self.prompt_ids != expected_prompts or self.seeds != expected_seeds:
            raise ValueError("plan prompt/seed map drifted")
        if len(set(self.prompt_ids)) != len(self.prompt_ids) or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("plan prompt ids and seeds must be unique")
        expected_ranges = tuple((target, start, min(start + self.shard_size, count)) for target in MID_DEV_TARGET_LENGTHS for start in range(0, count, self.shard_size))
        if tuple((s.target_length, s.start_index, s.end_index_exclusive) for s in self.shards) != expected_ranges:
            raise ValueError("plan shard coverage is incomplete or noncanonical")
        require_sha256("prompt_manifest_hash", self.prompt_manifest_hash)
        require_sha256("plan_hash", self.plan_hash)
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "role": self.role.value,
            "prompt_source_id": self.prompt_source_id,
            "negatives_per_target": self.negatives_per_target,
            "shard_size": self.shard_size,
            "prompt_ids": self.prompt_ids,
            "seeds": self.seeds,
            "prompt_manifest_hash": self.prompt_manifest_hash,
            "shard_hashes": tuple(shard.shard_hash for shard in self.shards),
        }


def build_mid_dev_calibration_shard_plan(
    role: CalibrationRole,
    *,
    negatives_per_target: int = MID_DEV_CALIBRATION_PREFERRED_NEGATIVES_PER_TARGET,
    shard_size: int = MID_DEV_CALIBRATION_DEFAULT_SHARD_SIZE,
) -> MidDevCalibrationShardPlan:
    role = _role(role)
    count = _count(negatives_per_target)
    require_int("shard_size", shard_size)
    if not 0 < shard_size <= count:
        raise ValueError("invalid shard size")
    prompts = tuple(calibration_prompt_id(role, target, i) for target in MID_DEV_TARGET_LENGTHS for i in range(count))
    seeds = tuple(calibration_seed(role, target, i) for target in MID_DEV_TARGET_LENGTHS for i in range(count))
    prompt_manifest_hash = sha256_json({
        "algorithm_version": MID_DEV_CALIBRATION_SHARD_ALGORITHM_VERSION,
        "role": role.value,
        "prompt_source_id": calibration_prompt_source_id(role),
        "prompt_ids": prompts,
        "seeds": seeds,
        "source_hash": _prompt_source_hash(role, count),
    })
    shards = tuple(_make_shard(role, target, start, min(start + shard_size, count)) for target in MID_DEV_TARGET_LENGTHS for start in range(0, count, shard_size))
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_SHARD_PLAN_VERSION,
        "role": role.value,
        "prompt_source_id": calibration_prompt_source_id(role),
        "negatives_per_target": count,
        "shard_size": shard_size,
        "prompt_ids": prompts,
        "seeds": seeds,
        "prompt_manifest_hash": prompt_manifest_hash,
        "shard_hashes": tuple(shard.shard_hash for shard in shards),
    }
    return MidDevCalibrationShardPlan(
        MID_DEV_CALIBRATION_SHARD_PLAN_VERSION, role, calibration_prompt_source_id(role), count,
        shard_size, prompts, seeds, prompt_manifest_hash, shards, sha256_json(payload),
    )


def validate_calibration_role_independence(select_plan: MidDevCalibrationShardPlan, audit_plan: MidDevCalibrationShardPlan) -> str:
    if select_plan.role is not CalibrationRole.SELECT or audit_plan.role is not CalibrationRole.AUDIT:
        raise MidDevCalibrationShardError("plans must be CAL-SELECT then CAL-AUDIT")
    if select_plan.negatives_per_target != audit_plan.negatives_per_target:
        raise MidDevCalibrationShardError("CAL-SELECT and CAL-AUDIT counts differ")
    if select_plan.prompt_source_id == audit_plan.prompt_source_id:
        raise MidDevCalibrationShardError("CAL-SELECT and CAL-AUDIT prompt sources overlap")
    if set(select_plan.prompt_ids) & set(audit_plan.prompt_ids):
        raise MidDevCalibrationShardError("CAL-SELECT and CAL-AUDIT prompt IDs overlap")
    if set(select_plan.seeds) & set(audit_plan.seeds):
        raise MidDevCalibrationShardError("CAL-SELECT and CAL-AUDIT seeds overlap")
    return sha256_json({"algorithm_version": "mid-dev-calibration-plan-independence-v1", "select": select_plan.plan_hash, "audit": audit_plan.plan_hash})


@dataclass(frozen=True, slots=True)
class MidDevCalibrationShardOutputManifest:
    algorithm_version: str
    role: CalibrationRole
    plan_hash: str
    shard_id: str
    shard_spec_hash: str
    target_length: int
    source_indices: tuple[int, ...]
    prompt_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    sample_record_hashes: tuple[str, ...]
    text_sha256s: tuple[str, ...]
    continuation_token_hashes: tuple[str, ...]
    model_tokenizer_identity_hash: str
    watermark_config_hash: str
    watermark_condition_hash: str
    output_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION:
            raise ValueError("unsupported shard output version")
        _role(self.role)
        require_clean_string("shard_id", self.shard_id)
        require_int("target_length", self.target_length)
        for name in ("plan_hash", "shard_spec_hash", "model_tokenizer_identity_hash", "watermark_config_hash", "watermark_condition_hash", "output_hash"):
            require_sha256(name, getattr(self, name))
        size = len(self.source_indices)
        if size == 0 or any(len(vector) != size for vector in (self.prompt_ids, self.sample_ids, self.sample_record_hashes, self.text_sha256s, self.continuation_token_hashes)):
            raise ValueError("shard output vectors must be non-empty and equal length")
        if self.source_indices != tuple(range(self.source_indices[0], self.source_indices[-1] + 1)):
            raise ValueError("source indices must be a canonical contiguous range")
        if self.sample_ids != tuple(f"{prompt}-unwatermarked" for prompt in self.prompt_ids):
            raise ValueError("sample IDs do not bind prompt IDs")
        for child in self.sample_record_hashes + self.text_sha256s + self.continuation_token_hashes:
            require_sha256("child hash", child)
        if any(len(set(vector)) != size for vector in (self.prompt_ids, self.sample_ids, self.sample_record_hashes)):
            raise ValueError("shard output identity vectors must be unique")
        if self.output_hash != sha256_json(self.payload()):
            raise ValueError("shard output hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: (getattr(self, name).value if name == "role" else getattr(self, name)) for name in self.__dataclass_fields__ if name != "output_hash"}


@dataclass(frozen=True, slots=True)
class MidDevGeneratedCalibrationShard:
    samples: tuple[CorpusSample, ...]
    manifest: MidDevCalibrationShardOutputManifest

    def __post_init__(self) -> None:
        if tuple(sample.sample_id for sample in self.samples) != self.manifest.sample_ids:
            raise ValueError("generated samples do not match shard manifest")


def _shard_for_id(plan: MidDevCalibrationShardPlan, shard_id: str) -> MidDevCalibrationShardSpec:
    matches = tuple(shard for shard in plan.shards if shard.shard_id == shard_id)
    if len(matches) != 1:
        raise MidDevCalibrationShardError("shard id is not present exactly once in frozen plan")
    return matches[0]


def build_real_mid_dev_calibration_shard(
    backend: MidDevGenerationBackend,
    plan: MidDevCalibrationShardPlan,
    shard_id: str,
) -> MidDevGeneratedCalibrationShard:
    if not isinstance(plan, MidDevCalibrationShardPlan):
        raise TypeError("plan must be MidDevCalibrationShardPlan")
    shard = _shard_for_id(plan, shard_id)
    if backend.watermark_condition.key_split is not KeySplit.DEV:
        raise MidDevCalibrationShardError("calibration generation must use DEV_KEYS")
    prompt_by_id = {item.prompt_id: item for item in build_mid_dev_calibration_prompt_records(plan.role, negatives_per_target=plan.negatives_per_target)}
    samples: list[CorpusSample] = []
    for source_index, prompt_id, seed in zip(range(shard.start_index, shard.end_index_exclusive), shard.prompt_ids, shard.seeds):
        prompt = prompt_by_id[prompt_id]
        generated = backend.generate(prompt.text, seed, shard.target_length, watermarked=False)
        if len(generated.continuation_token_ids) != shard.target_length:
            raise MidDevCalibrationShardError("exact-length calibration generation failed; seed changes are forbidden")
        sample = _build_sample(
            prompt=prompt,
            label=WatermarkLabel.UNWATERMARKED,
            generated=generated,
            backend=backend,
            seed=seed,
            target_length=shard.target_length,
        )
        if sample.generation.seed != calibration_seed(plan.role, shard.target_length, source_index):
            raise MidDevCalibrationShardError("generated sample seed drifted")
        samples.append(sample)
    sample_tuple = tuple(samples)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION,
        "role": plan.role.value,
        "plan_hash": plan.plan_hash,
        "shard_id": shard.shard_id,
        "shard_spec_hash": shard.shard_hash,
        "target_length": shard.target_length,
        "source_indices": tuple(range(shard.start_index, shard.end_index_exclusive)),
        "prompt_ids": shard.prompt_ids,
        "sample_ids": tuple(sample.sample_id for sample in sample_tuple),
        "sample_record_hashes": tuple(sample.record_hash for sample in sample_tuple),
        "text_sha256s": tuple(sample.text_sha256 for sample in sample_tuple),
        "continuation_token_hashes": tuple(sha256_json(sample.generation_tokens.continuation_token_ids) for sample in sample_tuple),
        "model_tokenizer_identity_hash": backend.model_identity.identity_hash,
        "watermark_config_hash": backend.watermark_condition.watermark_config_hash,
        "watermark_condition_hash": backend.watermark_condition.condition_hash,
    }
    manifest = MidDevCalibrationShardOutputManifest(
        MID_DEV_CALIBRATION_SHARD_OUTPUT_VERSION, plan.role, plan.plan_hash, shard.shard_id, shard.shard_hash,
        shard.target_length, payload["source_indices"], shard.prompt_ids, payload["sample_ids"],
        payload["sample_record_hashes"], payload["text_sha256s"], payload["continuation_token_hashes"],
        payload["model_tokenizer_identity_hash"], payload["watermark_config_hash"], payload["watermark_condition_hash"],
        sha256_json(payload),
    )
    return MidDevGeneratedCalibrationShard(sample_tuple, manifest)


@dataclass(frozen=True, slots=True)
class MidDevCalibrationMergedManifest:
    algorithm_version: str
    role: CalibrationRole
    plan_hash: str
    prompt_manifest_hash: str
    shard_output_hashes: tuple[str, ...]
    prompt_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    sample_record_hashes: tuple[str, ...]
    text_sha256s: tuple[str, ...]
    continuation_token_hashes: tuple[str, ...]
    model_tokenizer_identity_hash: str
    watermark_config_hash: str
    watermark_condition_hash: str
    manifest_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION:
            raise ValueError("unsupported merged manifest version")
        _role(self.role)
        for name in ("plan_hash", "prompt_manifest_hash", "model_tokenizer_identity_hash", "watermark_config_hash", "watermark_condition_hash", "manifest_hash"):
            require_sha256(name, getattr(self, name))
        size = len(self.prompt_ids)
        if size == 0 or any(len(vector) != size for vector in (self.sample_ids, self.sample_record_hashes, self.text_sha256s, self.continuation_token_hashes)):
            raise ValueError("merged vectors must be non-empty and equal length")
        for child in self.shard_output_hashes + self.sample_record_hashes + self.text_sha256s + self.continuation_token_hashes:
            require_sha256("manifest child hash", child)
        if any(len(set(vector)) != size for vector in (self.prompt_ids, self.sample_ids, self.sample_record_hashes)):
            raise ValueError("merged calibration identity vectors must be unique")
        if self.sample_ids != tuple(f"{prompt}-unwatermarked" for prompt in self.prompt_ids):
            raise ValueError("merged sample IDs drifted")
        if self.manifest_hash != sha256_json(self.payload()):
            raise ValueError("merged manifest hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: (getattr(self, name).value if name == "role" else getattr(self, name)) for name in self.__dataclass_fields__ if name != "manifest_hash"}


def merge_mid_dev_calibration_shard_outputs(
    plan: MidDevCalibrationShardPlan,
    outputs: Sequence[MidDevCalibrationShardOutputManifest],
) -> MidDevCalibrationMergedManifest:
    if not isinstance(plan, MidDevCalibrationShardPlan):
        raise TypeError("plan must be MidDevCalibrationShardPlan")
    outputs = tuple(outputs)
    if any(not isinstance(item, MidDevCalibrationShardOutputManifest) for item in outputs):
        raise TypeError("outputs must contain shard manifests")
    if len(outputs) != len(plan.shards):
        raise MidDevCalibrationShardError("missing or extra calibration shard output")
    by_id = {item.shard_id: item for item in outputs}
    if len(by_id) != len(outputs):
        raise MidDevCalibrationShardError("duplicate calibration shard output")
    expected_ids = tuple(shard.shard_id for shard in plan.shards)
    if set(by_id) != set(expected_ids):
        raise MidDevCalibrationShardError("shard output set does not match frozen plan")
    ordered = tuple(by_id[item] for item in expected_ids)
    identities = {item.model_tokenizer_identity_hash for item in ordered}
    configs = {item.watermark_config_hash for item in ordered}
    conditions = {item.watermark_condition_hash for item in ordered}
    if len(identities) != 1 or len(configs) != 1 or len(conditions) != 1:
        raise MidDevCalibrationShardError("shards mix immutable identities")
    prompt_ids: list[str] = []
    sample_ids: list[str] = []
    record_hashes: list[str] = []
    text_hashes: list[str] = []
    token_hashes: list[str] = []
    for spec, output in zip(plan.shards, ordered):
        if output.role is not plan.role or output.plan_hash != plan.plan_hash or output.shard_spec_hash != spec.shard_hash:
            raise MidDevCalibrationShardError("shard binding drifted")
        if output.target_length != spec.target_length or output.source_indices != tuple(range(spec.start_index, spec.end_index_exclusive)) or output.prompt_ids != spec.prompt_ids:
            raise MidDevCalibrationShardError("shard coordinate drifted")
        prompt_ids.extend(output.prompt_ids)
        sample_ids.extend(output.sample_ids)
        record_hashes.extend(output.sample_record_hashes)
        text_hashes.extend(output.text_sha256s)
        token_hashes.extend(output.continuation_token_hashes)
    vectors = tuple(prompt_ids), tuple(sample_ids), tuple(record_hashes), tuple(text_hashes), tuple(token_hashes)
    if vectors[0] != plan.prompt_ids:
        raise MidDevCalibrationShardError("merged prompt coverage is incomplete")
    if any(len(set(vector)) != len(vector) for vector in vectors[1:3]):
        raise MidDevCalibrationShardError("merged calibration identities are not unique")
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION,
        "role": plan.role.value,
        "plan_hash": plan.plan_hash,
        "prompt_manifest_hash": plan.prompt_manifest_hash,
        "shard_output_hashes": tuple(item.output_hash for item in ordered),
        "prompt_ids": vectors[0], "sample_ids": vectors[1], "sample_record_hashes": vectors[2],
        "text_sha256s": vectors[3], "continuation_token_hashes": vectors[4],
        "model_tokenizer_identity_hash": next(iter(identities)),
        "watermark_config_hash": next(iter(configs)),
        "watermark_condition_hash": next(iter(conditions)),
    }
    return MidDevCalibrationMergedManifest(
        MID_DEV_CALIBRATION_MERGED_MANIFEST_VERSION, plan.role, plan.plan_hash, plan.prompt_manifest_hash,
        payload["shard_output_hashes"], vectors[0], vectors[1], vectors[2], vectors[3], vectors[4],
        payload["model_tokenizer_identity_hash"], payload["watermark_config_hash"], payload["watermark_condition_hash"],
        sha256_json(payload),
    )


def validate_calibration_merged_independence(select_manifest: MidDevCalibrationMergedManifest, audit_manifest: MidDevCalibrationMergedManifest) -> str:
    if select_manifest.role is not CalibrationRole.SELECT or audit_manifest.role is not CalibrationRole.AUDIT:
        raise MidDevCalibrationShardError("merged manifests must be CAL-SELECT then CAL-AUDIT")
    if len(select_manifest.sample_ids) != len(audit_manifest.sample_ids):
        raise MidDevCalibrationShardError("merged CAL-SELECT/CAL-AUDIT counts differ")
    if select_manifest.model_tokenizer_identity_hash != audit_manifest.model_tokenizer_identity_hash:
        raise MidDevCalibrationShardError("model/tokenizer identities differ")
    if select_manifest.watermark_config_hash != audit_manifest.watermark_config_hash or select_manifest.watermark_condition_hash != audit_manifest.watermark_condition_hash:
        raise MidDevCalibrationShardError("watermark identities differ")
    for name, left, right in (
        ("prompt IDs", select_manifest.prompt_ids, audit_manifest.prompt_ids),
        ("sample IDs", select_manifest.sample_ids, audit_manifest.sample_ids),
        ("text hashes", select_manifest.text_sha256s, audit_manifest.text_sha256s),
        ("token hashes", select_manifest.continuation_token_hashes, audit_manifest.continuation_token_hashes),
    ):
        if set(left) & set(right):
            raise MidDevCalibrationShardError(f"CAL-SELECT and CAL-AUDIT {name} overlap")
    return sha256_json({"algorithm_version": "mid-dev-calibration-merged-independence-v1", "select": select_manifest.manifest_hash, "audit": audit_manifest.manifest_hash})
