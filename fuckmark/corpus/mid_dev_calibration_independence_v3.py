from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .sample import CorpusSample
from .schema import MAX_GENERATION_SEED, WatermarkLabel
from .mid_dev_calibration_shards import CalibrationRole


MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION = "mid-dev-calibration-independence-v3"
MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE = (
    "ROLE_SAFE_FIRST_OCCURRENCE;SELECT_ORDER_FROZEN;"
    "WITHIN_ROLE_TEXT_OR_TOKEN_DEDUP;AUDIT_CROSS_ROLE_CONTENT_EXCLUSION;"
    "STRUCTURAL_IDENTITY_OVERLAP_HARD_FAILURE"
)


class CalibrationIndependenceV3Error(ValueError):
    pass


class CalibrationIndependenceV3InsufficientError(CalibrationIndependenceV3Error):
    pass


class CalibrationCollisionKind(str, Enum):
    TEXT_SHA256 = "TEXT_SHA256"
    CONTINUATION_TOKEN_HASH = "CONTINUATION_TOKEN_HASH"
    EXACT_TEXT_TOKEN_PAIR = "EXACT_TEXT_TOKEN_PAIR"


@dataclass(frozen=True, slots=True)
class CalibrationIndependenceV3Candidate:
    role: CalibrationRole
    prompt_id: str
    sample_id: str
    sample_record_hash: str
    text_sha256: str
    continuation_token_hash: str
    generation_seed: int
    model_tokenizer_identity_hash: str
    watermark_config_hash: str
    watermark_condition_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, CalibrationRole):
            raise TypeError("role must be CalibrationRole")
        for name in ("prompt_id", "sample_id"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "sample_record_hash",
            "text_sha256",
            "continuation_token_hash",
            "model_tokenizer_identity_hash",
            "watermark_config_hash",
            "watermark_condition_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("generation_seed", self.generation_seed)
        if not 0 <= self.generation_seed <= MAX_GENERATION_SEED:
            raise ValueError("generation_seed must be between 0 and 2^64-1")

    @classmethod
    def from_sample(
        cls,
        sample: CorpusSample,
        role: CalibrationRole,
    ) -> CalibrationIndependenceV3Candidate:
        if not isinstance(sample, CorpusSample):
            raise TypeError("sample must be CorpusSample")
        if sample.label is not WatermarkLabel.UNWATERMARKED:
            raise CalibrationIndependenceV3Error("calibration candidates must be unwatermarked")
        return cls(
            role=role,
            prompt_id=sample.prompt_id,
            sample_id=sample.sample_id,
            sample_record_hash=sample.record_hash,
            text_sha256=sample.text_sha256,
            continuation_token_hash=sample.generation_tokens.continuation_token_hash,
            generation_seed=sample.generation.seed,
            model_tokenizer_identity_hash=sample.model.identity_hash,
            watermark_config_hash=sample.watermark.watermark_config_hash,
            watermark_condition_hash=sample.watermark.condition_hash,
        )

    def payload(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "prompt_id": self.prompt_id,
            "sample_id": self.sample_id,
            "sample_record_hash": self.sample_record_hash,
            "text_sha256": self.text_sha256,
            "continuation_token_hash": self.continuation_token_hash,
            "generation_seed": self.generation_seed,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "watermark_config_hash": self.watermark_config_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
        }

    @property
    def text_token_pair(self) -> tuple[str, str]:
        return self.text_sha256, self.continuation_token_hash


@dataclass(frozen=True, slots=True)
class CalibrationIndependenceV3Exclusion:
    role: CalibrationRole
    ordinal: int
    prompt_id: str
    sample_id: str
    reason: str
    collision_kinds: tuple[CalibrationCollisionKind, ...]
    conflicting_role: CalibrationRole
    conflicting_ordinal: int
    conflicting_prompt_id: str
    conflicting_sample_id: str
    exclusion_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, CalibrationRole):
            raise TypeError("role must be CalibrationRole")
        require_int("ordinal", self.ordinal)
        if self.ordinal < 0:
            raise ValueError("ordinal must be non-negative")
        for name in ("prompt_id", "sample_id", "reason", "conflicting_prompt_id", "conflicting_sample_id"):
            require_clean_string(name, getattr(self, name))
        if not self.collision_kinds:
            raise ValueError("collision_kinds must not be empty")
        if tuple(sorted(set(self.collision_kinds), key=lambda item: item.value)) != self.collision_kinds:
            raise ValueError("collision_kinds must be sorted and unique")
        if not isinstance(self.conflicting_role, CalibrationRole):
            raise TypeError("conflicting_role must be CalibrationRole")
        require_int("conflicting_ordinal", self.conflicting_ordinal)
        if self.conflicting_ordinal < 0:
            raise ValueError("conflicting_ordinal must be non-negative")
        require_sha256("exclusion_hash", self.exclusion_hash)
        if self.exclusion_hash != sha256_json(self.payload()):
            raise ValueError("calibration exclusion hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "ordinal": self.ordinal,
            "prompt_id": self.prompt_id,
            "sample_id": self.sample_id,
            "reason": self.reason,
            "collision_kinds": tuple(item.value for item in self.collision_kinds),
            "conflicting_role": self.conflicting_role.value,
            "conflicting_ordinal": self.conflicting_ordinal,
            "conflicting_prompt_id": self.conflicting_prompt_id,
            "conflicting_sample_id": self.conflicting_sample_id,
        }


@dataclass(frozen=True, slots=True)
class CalibrationIndependenceV3RoleManifest:
    role: CalibrationRole
    plan_hash: str
    raw_candidate_count: int
    independent_candidate_count: int
    selected_candidate_count: int
    candidate_order_hash: str
    independent_sample_ids_hash: str
    selected_sample_ids: tuple[str, ...]
    selected_record_hashes: tuple[str, ...]
    selected_text_sha256s: tuple[str, ...]
    selected_continuation_token_hashes: tuple[str, ...]
    excluded_sample_ids: tuple[str, ...]
    exclusion_hashes: tuple[str, ...]
    manifest_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, CalibrationRole):
            raise TypeError("role must be CalibrationRole")
        require_sha256("plan_hash", self.plan_hash)
        for name in ("raw_candidate_count", "independent_candidate_count", "selected_candidate_count"):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.raw_candidate_count < self.independent_candidate_count:
            raise ValueError("independent candidates cannot exceed raw candidates")
        if self.independent_candidate_count < self.selected_candidate_count:
            raise ValueError("selected candidates cannot exceed independent candidates")
        for name in ("candidate_order_hash", "independent_sample_ids_hash", "manifest_hash"):
            require_sha256(name, getattr(self, name))
        size = self.selected_candidate_count
        if any(len(vector) != size for vector in (
            self.selected_sample_ids,
            self.selected_record_hashes,
            self.selected_text_sha256s,
            self.selected_continuation_token_hashes,
        )):
            raise ValueError("selected manifest vectors must have selected_candidate_count entries")
        if len(set(self.selected_sample_ids)) != size:
            raise ValueError("selected sample IDs must be unique")
        if len(set(self.selected_record_hashes)) != size:
            raise ValueError("selected record hashes must be unique")
        if len(set(self.selected_text_sha256s)) != size:
            raise ValueError("selected text hashes must be unique")
        if len(set(self.selected_continuation_token_hashes)) != size:
            raise ValueError("selected continuation-token hashes must be unique")
        if len(set(self.excluded_sample_ids)) != len(self.excluded_sample_ids):
            raise ValueError("excluded sample IDs must be unique")
        if set(self.selected_sample_ids) & set(self.excluded_sample_ids):
            raise ValueError("selected and excluded sample IDs must be disjoint")
        if len(self.excluded_sample_ids) != len(self.exclusion_hashes):
            raise ValueError("excluded sample IDs and exclusion hashes must align")
        for value in self.selected_sample_ids + self.excluded_sample_ids:
            require_clean_string("sample_id", value)
        for name, values in (
            ("selected_sample_ids", self.selected_sample_ids),
            ("selected_record_hashes", self.selected_record_hashes),
            ("selected_text_sha256s", self.selected_text_sha256s),
            ("selected_continuation_token_hashes", self.selected_continuation_token_hashes),
            ("excluded_sample_ids", self.excluded_sample_ids),
            ("exclusion_hashes", self.exclusion_hashes),
        ):
            if name.endswith("hashes") or name.endswith("sha256s"):
                for value in values:
                    require_sha256(name, value)
        if self.manifest_hash != sha256_json(self.payload()):
            raise ValueError("calibration role manifest hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "plan_hash": self.plan_hash,
            "raw_candidate_count": self.raw_candidate_count,
            "independent_candidate_count": self.independent_candidate_count,
            "selected_candidate_count": self.selected_candidate_count,
            "candidate_order_hash": self.candidate_order_hash,
            "independent_sample_ids_hash": self.independent_sample_ids_hash,
            "selected_sample_ids": self.selected_sample_ids,
            "selected_record_hashes": self.selected_record_hashes,
            "selected_text_sha256s": self.selected_text_sha256s,
            "selected_continuation_token_hashes": self.selected_continuation_token_hashes,
            "excluded_sample_ids": self.excluded_sample_ids,
            "exclusion_hashes": self.exclusion_hashes,
        }


@dataclass(frozen=True, slots=True)
class CalibrationIndependenceV3PairArtifact:
    algorithm_version: str
    selection_rule: str
    required_count_per_role: int
    select_plan_hash: str
    audit_plan_hash: str
    model_tokenizer_identity_hash: str
    watermark_config_hash: str
    watermark_condition_hash: str
    select_manifest_hash: str
    audit_manifest_hash: str
    exclusion_hashes: tuple[str, ...]
    cross_role_collision_count: int
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION:
            raise ValueError("unsupported calibration independence v3 version")
        if self.selection_rule != MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE:
            raise ValueError("unsupported calibration independence v3 selection rule")
        require_int("required_count_per_role", self.required_count_per_role)
        if self.required_count_per_role <= 0:
            raise ValueError("required_count_per_role must be positive")
        for name in (
            "select_plan_hash",
            "audit_plan_hash",
            "model_tokenizer_identity_hash",
            "watermark_config_hash",
            "watermark_condition_hash",
            "select_manifest_hash",
            "audit_manifest_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.select_plan_hash == self.audit_plan_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT plan hashes must differ")
        if self.select_manifest_hash == self.audit_manifest_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT manifest hashes must differ")
        if len(set(self.exclusion_hashes)) != len(self.exclusion_hashes):
            raise ValueError("exclusion hashes must be unique")
        for value in self.exclusion_hashes:
            require_sha256("exclusion_hash", value)
        require_int("cross_role_collision_count", self.cross_role_collision_count)
        if self.cross_role_collision_count < 0:
            raise ValueError("cross_role_collision_count must be non-negative")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("calibration independence v3 artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "selection_rule": self.selection_rule,
            "required_count_per_role": self.required_count_per_role,
            "select_plan_hash": self.select_plan_hash,
            "audit_plan_hash": self.audit_plan_hash,
            "model_tokenizer_identity_hash": self.model_tokenizer_identity_hash,
            "watermark_config_hash": self.watermark_config_hash,
            "watermark_condition_hash": self.watermark_condition_hash,
            "select_manifest_hash": self.select_manifest_hash,
            "audit_manifest_hash": self.audit_manifest_hash,
            "exclusion_hashes": self.exclusion_hashes,
            "cross_role_collision_count": self.cross_role_collision_count,
        }


@dataclass(frozen=True, slots=True)
class CalibrationIndependenceV3Result:
    select_candidates: tuple[CalibrationIndependenceV3Candidate, ...]
    audit_candidates: tuple[CalibrationIndependenceV3Candidate, ...]
    select_manifest: CalibrationIndependenceV3RoleManifest
    audit_manifest: CalibrationIndependenceV3RoleManifest
    exclusions: tuple[CalibrationIndependenceV3Exclusion, ...]
    artifact: CalibrationIndependenceV3PairArtifact


def _common_identity(
    select_candidates: Sequence[CalibrationIndependenceV3Candidate],
    audit_candidates: Sequence[CalibrationIndependenceV3Candidate],
) -> tuple[str, str, str]:
    values = tuple(select_candidates) + tuple(audit_candidates)
    if not values:
        raise CalibrationIndependenceV3Error("calibration candidate pools must not be empty")
    identities = {(item.model_tokenizer_identity_hash, item.watermark_config_hash, item.watermark_condition_hash) for item in values}
    if len(identities) != 1:
        raise CalibrationIndependenceV3Error("candidate pools mix immutable model or watermark identities")
    return next(iter(identities))


def _validate_role_candidates(
    role: CalibrationRole,
    candidates: Sequence[CalibrationIndependenceV3Candidate],
) -> tuple[CalibrationIndependenceV3Candidate, ...]:
    values = tuple(candidates)
    if not values:
        raise CalibrationIndependenceV3Error(f"{role.value} candidate pool must not be empty")
    if any(not isinstance(item, CalibrationIndependenceV3Candidate) for item in values):
        raise TypeError("candidate pools must contain CalibrationIndependenceV3Candidate values")
    if any(item.role is not role for item in values):
        raise CalibrationIndependenceV3Error(f"candidate role does not match {role.value}")
    for field in ("prompt_id", "sample_id", "sample_record_hash", "generation_seed"):
        seen: set[object] = set()
        for item in values:
            value = getattr(item, field)
            if value in seen:
                raise CalibrationIndependenceV3Error(f"{role.value} contains duplicate {field}")
            seen.add(value)
    return values


def _collision_kinds(left: CalibrationIndependenceV3Candidate, right: CalibrationIndependenceV3Candidate) -> tuple[CalibrationCollisionKind, ...]:
    values: list[CalibrationCollisionKind] = []
    if left.text_sha256 == right.text_sha256:
        values.append(CalibrationCollisionKind.TEXT_SHA256)
    if left.continuation_token_hash == right.continuation_token_hash:
        values.append(CalibrationCollisionKind.CONTINUATION_TOKEN_HASH)
    if left.text_token_pair == right.text_token_pair:
        values.append(CalibrationCollisionKind.EXACT_TEXT_TOKEN_PAIR)
    return tuple(sorted(set(values), key=lambda item: item.value))


def _exclusion(
    candidate: CalibrationIndependenceV3Candidate,
    ordinal: int,
    conflict: CalibrationIndependenceV3Candidate,
    conflict_ordinal: int,
    reason: str,
    kinds: tuple[CalibrationCollisionKind, ...],
) -> CalibrationIndependenceV3Exclusion:
    payload = {
        "role": candidate.role.value,
        "ordinal": ordinal,
        "prompt_id": candidate.prompt_id,
        "sample_id": candidate.sample_id,
        "reason": reason,
        "collision_kinds": tuple(item.value for item in kinds),
        "conflicting_role": conflict.role.value,
        "conflicting_ordinal": conflict_ordinal,
        "conflicting_prompt_id": conflict.prompt_id,
        "conflicting_sample_id": conflict.sample_id,
    }
    return CalibrationIndependenceV3Exclusion(
        role=candidate.role,
        ordinal=ordinal,
        prompt_id=candidate.prompt_id,
        sample_id=candidate.sample_id,
        reason=reason,
        collision_kinds=kinds,
        conflicting_role=conflict.role,
        conflicting_ordinal=conflict_ordinal,
        conflicting_prompt_id=conflict.prompt_id,
        conflicting_sample_id=conflict.sample_id,
        exclusion_hash=sha256_json(payload),
    )


def _deduplicate_role(
    candidates: tuple[CalibrationIndependenceV3Candidate, ...],
) -> tuple[tuple[CalibrationIndependenceV3Candidate, ...], tuple[CalibrationIndependenceV3Exclusion, ...]]:
    kept: list[CalibrationIndependenceV3Candidate] = []
    exclusions: list[CalibrationIndependenceV3Exclusion] = []
    by_text: dict[str, tuple[CalibrationIndependenceV3Candidate, int]] = {}
    by_token: dict[str, tuple[CalibrationIndependenceV3Candidate, int]] = {}
    for ordinal, candidate in enumerate(candidates):
        conflict_candidates: list[tuple[CalibrationIndependenceV3Candidate, int]] = []
        if candidate.text_sha256 in by_text:
            conflict_candidates.append(by_text[candidate.text_sha256])
        if candidate.continuation_token_hash in by_token:
            conflict_candidates.append(by_token[candidate.continuation_token_hash])
        if conflict_candidates:
            conflict, conflict_ordinal = min(conflict_candidates, key=lambda item: item[1])
            kinds = _collision_kinds(candidate, conflict)
            if candidate.text_sha256 in by_text and CalibrationCollisionKind.TEXT_SHA256 not in kinds:
                kinds = tuple(sorted((*kinds, CalibrationCollisionKind.TEXT_SHA256), key=lambda item: item.value))
            if candidate.continuation_token_hash in by_token and CalibrationCollisionKind.CONTINUATION_TOKEN_HASH not in kinds:
                kinds = tuple(sorted((*kinds, CalibrationCollisionKind.CONTINUATION_TOKEN_HASH), key=lambda item: item.value))
            exclusions.append(_exclusion(candidate, ordinal, conflict, conflict_ordinal, "WITHIN_ROLE_CONTENT_DUPLICATE", kinds))
        else:
            kept.append(candidate)
            by_text[candidate.text_sha256] = (candidate, ordinal)
            by_token[candidate.continuation_token_hash] = (candidate, ordinal)
    return tuple(kept), tuple(exclusions)


def _role_manifest(
    role: CalibrationRole,
    plan_hash: str,
    raw: tuple[CalibrationIndependenceV3Candidate, ...],
    independent: tuple[CalibrationIndependenceV3Candidate, ...],
    selected: tuple[CalibrationIndependenceV3Candidate, ...],
    exclusions: tuple[CalibrationIndependenceV3Exclusion, ...],
) -> CalibrationIndependenceV3RoleManifest:
    selected_payload = {
        "sample_ids": tuple(item.sample_id for item in selected),
        "record_hashes": tuple(item.sample_record_hash for item in selected),
        "text_sha256s": tuple(item.text_sha256 for item in selected),
        "continuation_token_hashes": tuple(item.continuation_token_hash for item in selected),
    }
    payload = {
        "role": role.value,
        "plan_hash": plan_hash,
        "raw_candidate_count": len(raw),
        "independent_candidate_count": len(independent),
        "selected_candidate_count": len(selected),
        "candidate_order_hash": sha256_json(tuple(item.payload() for item in raw)),
        "independent_sample_ids_hash": sha256_json(tuple(item.sample_id for item in independent)),
        "selected_sample_ids": selected_payload["sample_ids"],
        "selected_record_hashes": selected_payload["record_hashes"],
        "selected_text_sha256s": selected_payload["text_sha256s"],
        "selected_continuation_token_hashes": selected_payload["continuation_token_hashes"],
        "excluded_sample_ids": tuple(item.sample_id for item in exclusions),
        "exclusion_hashes": tuple(item.exclusion_hash for item in exclusions),
    }
    return CalibrationIndependenceV3RoleManifest(
        role=role,
        plan_hash=plan_hash,
        raw_candidate_count=payload["raw_candidate_count"],
        independent_candidate_count=payload["independent_candidate_count"],
        selected_candidate_count=payload["selected_candidate_count"],
        candidate_order_hash=payload["candidate_order_hash"],
        independent_sample_ids_hash=payload["independent_sample_ids_hash"],
        selected_sample_ids=payload["selected_sample_ids"],
        selected_record_hashes=payload["selected_record_hashes"],
        selected_text_sha256s=payload["selected_text_sha256s"],
        selected_continuation_token_hashes=payload["selected_continuation_token_hashes"],
        excluded_sample_ids=payload["excluded_sample_ids"],
        exclusion_hashes=payload["exclusion_hashes"],
        manifest_hash=sha256_json(payload),
    )


def build_calibration_independence_v3(
    select_candidates: Sequence[CalibrationIndependenceV3Candidate],
    audit_candidates: Sequence[CalibrationIndependenceV3Candidate],
    *,
    select_plan_hash: str,
    audit_plan_hash: str,
    required_count_per_role: int,
) -> CalibrationIndependenceV3Result:
    require_sha256("select_plan_hash", select_plan_hash)
    require_sha256("audit_plan_hash", audit_plan_hash)
    if select_plan_hash == audit_plan_hash:
        raise CalibrationIndependenceV3Error("CAL-SELECT and CAL-AUDIT plan hashes must differ")
    require_int("required_count_per_role", required_count_per_role)
    if required_count_per_role <= 0:
        raise ValueError("required_count_per_role must be positive")
    select_raw = _validate_role_candidates(CalibrationRole.SELECT, select_candidates)
    audit_raw = _validate_role_candidates(CalibrationRole.AUDIT, audit_candidates)
    identity = _common_identity(select_raw, audit_raw)
    select_unique, select_exclusions = _deduplicate_role(select_raw)
    audit_unique, audit_exclusions = _deduplicate_role(audit_raw)
    structural_fields = ("prompt_id", "sample_id", "sample_record_hash", "generation_seed")
    for field in structural_fields:
        select_values = {getattr(item, field): item for item in select_raw}
        audit_values = {getattr(item, field): item for item in audit_raw}
        overlap = set(select_values) & set(audit_values)
        if overlap:
            raise CalibrationIndependenceV3Error(f"CAL-SELECT and CAL-AUDIT {field} overlap")
    select_text = {item.text_sha256: (item, ordinal) for ordinal, item in enumerate(select_unique)}
    select_tokens = {item.continuation_token_hash: (item, ordinal) for ordinal, item in enumerate(select_unique)}
    audit_independent: list[CalibrationIndependenceV3Candidate] = []
    cross_exclusions: list[CalibrationIndependenceV3Exclusion] = []
    for ordinal, candidate in enumerate(audit_unique):
        conflicts: list[tuple[CalibrationIndependenceV3Candidate, int]] = []
        if candidate.text_sha256 in select_text:
            conflicts.append(select_text[candidate.text_sha256])
        if candidate.continuation_token_hash in select_tokens:
            conflicts.append(select_tokens[candidate.continuation_token_hash])
        if conflicts:
            conflict, conflict_ordinal = min(conflicts, key=lambda item: item[1])
            cross_exclusions.append(
                _exclusion(
                    candidate,
                    next(index for index, item in enumerate(audit_raw) if item.sample_id == candidate.sample_id),
                    conflict,
                    conflict_ordinal,
                    "CROSS_ROLE_CONTENT_COLLISION",
                    _collision_kinds(candidate, conflict),
                )
            )
            continue
        audit_independent.append(candidate)
    audit_independent_tuple = tuple(audit_independent)
    all_exclusions = tuple(
        sorted(
            (*select_exclusions, *audit_exclusions, *cross_exclusions),
            key=lambda item: (0 if item.role is CalibrationRole.SELECT else 1, item.ordinal, item.exclusion_hash),
        )
    )
    if len(select_unique) < required_count_per_role:
        raise CalibrationIndependenceV3InsufficientError(
            f"CAL-SELECT has {len(select_unique)} independent candidates; {required_count_per_role} required"
        )
    if len(audit_independent_tuple) < required_count_per_role:
        raise CalibrationIndependenceV3InsufficientError(
            f"CAL-AUDIT has {len(audit_independent_tuple)} independent candidates after {len(cross_exclusions)} cross-role exclusions; {required_count_per_role} required"
        )
    select_selected = select_unique[:required_count_per_role]
    audit_selected = audit_independent_tuple[:required_count_per_role]
    select_manifest = _role_manifest(CalibrationRole.SELECT, select_plan_hash, select_raw, select_unique, select_selected, tuple(item for item in all_exclusions if item.role is CalibrationRole.SELECT))
    audit_manifest = _role_manifest(CalibrationRole.AUDIT, audit_plan_hash, audit_raw, audit_independent_tuple, audit_selected, tuple(item for item in all_exclusions if item.role is CalibrationRole.AUDIT))
    artifact_payload = {
        "algorithm_version": MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION,
        "selection_rule": MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE,
        "required_count_per_role": required_count_per_role,
        "select_plan_hash": select_plan_hash,
        "audit_plan_hash": audit_plan_hash,
        "model_tokenizer_identity_hash": identity[0],
        "watermark_config_hash": identity[1],
        "watermark_condition_hash": identity[2],
        "select_manifest_hash": select_manifest.manifest_hash,
        "audit_manifest_hash": audit_manifest.manifest_hash,
        "exclusion_hashes": tuple(item.exclusion_hash for item in all_exclusions),
        "cross_role_collision_count": len(cross_exclusions),
    }
    artifact = CalibrationIndependenceV3PairArtifact(**artifact_payload, artifact_hash=sha256_json(artifact_payload))
    return CalibrationIndependenceV3Result(select_selected, audit_selected, select_manifest, audit_manifest, all_exclusions, artifact)


def build_calibration_independence_v3_from_samples(
    select_samples: Sequence[CorpusSample],
    audit_samples: Sequence[CorpusSample],
    *,
    select_plan_hash: str,
    audit_plan_hash: str,
    required_count_per_role: int,
) -> CalibrationIndependenceV3Result:
    select_candidates = tuple(
        CalibrationIndependenceV3Candidate.from_sample(sample, CalibrationRole.SELECT)
        for sample in select_samples
    )
    audit_candidates = tuple(
        CalibrationIndependenceV3Candidate.from_sample(sample, CalibrationRole.AUDIT)
        for sample in audit_samples
    )
    return build_calibration_independence_v3(
        select_candidates,
        audit_candidates,
        select_plan_hash=select_plan_hash,
        audit_plan_hash=audit_plan_hash,
        required_count_per_role=required_count_per_role,
    )
