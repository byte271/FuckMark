from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..transforms import CandidateEnumeration, KeyBlindScheduleInput, SchedulePolicy, ScheduleResult, TransformResult
from .transform_analysis import DevelopmentTransformRow


DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION = "development-transform-provenance-v1"


class TransformProvenanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedTransformProvenance:
    algorithm_version: str
    source_sample_id: str
    prompt_family_id: str
    source_text_hash: str
    transformed_text_hash: str
    enumeration_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    transform_result_hash: str
    trace_hash: str
    schedule_policy: SchedulePolicy
    schedule_seed: int
    budget: int
    budget_unit: str
    realized_edit_cost: int
    scheduler_covered_interval_size: int
    selected_candidate_ids: tuple[str, ...]
    provenance_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION:
            raise ValueError("unsupported development transform provenance version")
        require_clean_string("source_sample_id", self.source_sample_id)
        require_clean_string("prompt_family_id", self.prompt_family_id)
        for name, value in (
            ("source_text_hash", self.source_text_hash),
            ("transformed_text_hash", self.transformed_text_hash),
            ("enumeration_hash", self.enumeration_hash),
            ("scheduler_input_hash", self.scheduler_input_hash),
            ("schedule_result_hash", self.schedule_result_hash),
            ("transform_result_hash", self.transform_result_hash),
            ("trace_hash", self.trace_hash),
            ("provenance_hash", self.provenance_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.schedule_policy, SchedulePolicy):
            raise TypeError("schedule_policy must be a SchedulePolicy")
        require_int("schedule_seed", self.schedule_seed)
        if self.schedule_seed < 0 or self.schedule_seed >= 1 << 64:
            raise ValueError("schedule_seed must be between 0 and 2^64-1")
        require_int("budget", self.budget)
        require_int("realized_edit_cost", self.realized_edit_cost)
        require_int("scheduler_covered_interval_size", self.scheduler_covered_interval_size)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        if self.realized_edit_cost < 0 or self.realized_edit_cost > self.budget:
            raise ValueError("realized_edit_cost must lie inside budget")
        if self.scheduler_covered_interval_size < 0:
            raise ValueError("scheduler_covered_interval_size must be non-negative")
        require_clean_string("budget_unit", self.budget_unit)
        if not isinstance(self.selected_candidate_ids, tuple):
            raise TypeError("selected_candidate_ids must be a tuple")
        if len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_ids must be unique")
        for candidate_id in self.selected_candidate_ids:
            require_sha256("selected candidate ID", candidate_id)
        if bool(self.selected_candidate_ids) != (self.realized_edit_cost > 0):
            raise ValueError("selected candidates and realized edit cost disagree")
        if self.provenance_hash != sha256_json(self._payload()):
            raise ValueError("provenance_hash does not match verified transform provenance")

    @property
    def eligible(self) -> bool:
        return bool(self.selected_candidate_ids)

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "prompt_family_id": self.prompt_family_id,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
            "enumeration_hash": self.enumeration_hash,
            "scheduler_input_hash": self.scheduler_input_hash,
            "schedule_result_hash": self.schedule_result_hash,
            "transform_result_hash": self.transform_result_hash,
            "trace_hash": self.trace_hash,
            "schedule_policy": self.schedule_policy.value,
            "schedule_seed": self.schedule_seed,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "realized_edit_cost": self.realized_edit_cost,
            "scheduler_covered_interval_size": self.scheduler_covered_interval_size,
            "selected_candidate_ids": self.selected_candidate_ids,
        }


def verify_transform_provenance(
    source_sample_id: str,
    prompt_family_id: str,
    source_text: str,
    enumeration: CandidateEnumeration,
    scheduler_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
) -> VerifiedTransformProvenance:
    require_clean_string("source_sample_id", source_sample_id)
    require_clean_string("prompt_family_id", prompt_family_id)
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not isinstance(enumeration, CandidateEnumeration):
        raise TypeError("enumeration must be a CandidateEnumeration")
    if not isinstance(scheduler_input, KeyBlindScheduleInput):
        raise TypeError("scheduler_input must be a KeyBlindScheduleInput")
    if not isinstance(schedule_result, ScheduleResult):
        raise TypeError("schedule_result must be a ScheduleResult")
    if not isinstance(transform_result, TransformResult):
        raise TypeError("transform_result must be a TransformResult")
    source_hash = sha256_text(source_text)
    if enumeration.input_text != source_text or enumeration.input_hash != source_hash:
        raise TransformProvenanceError("candidate enumeration does not belong to source text")
    if scheduler_input.input_hash != enumeration.input_hash:
        raise TransformProvenanceError("scheduler input source hash does not match candidate enumeration")
    if scheduler_input.enumeration_hash != enumeration.enumeration_hash:
        raise TransformProvenanceError("scheduler input enumeration hash does not match candidate enumeration")
    if schedule_result.input_artifact_hash != scheduler_input.input_artifact_hash:
        raise TransformProvenanceError("schedule result does not belong to scheduler input")
    if transform_result.trace.input_hash != enumeration.input_hash:
        raise TransformProvenanceError("transform trace input hash does not match candidate enumeration")
    if transform_result.trace.enumeration_hash != enumeration.enumeration_hash:
        raise TransformProvenanceError("transform trace enumeration hash does not match candidate enumeration")
    if transform_result.trace.selected_candidate_ids != schedule_result.selected_candidate_ids:
        raise TransformProvenanceError("transform trace selected candidates do not match schedule result")
    if transform_result.trace.seed != schedule_result.seed:
        raise TransformProvenanceError("transform trace seed does not match schedule result")
    transformed_hash = sha256_text(transform_result.output_text)
    if transform_result.trace.output_hash != transformed_hash:
        raise TransformProvenanceError("transform trace output hash does not match transformed text")
    if bool(schedule_result.selected_candidate_ids) != (source_hash != transformed_hash):
        raise TransformProvenanceError("schedule selection does not match realized text change")
    payload = {
        "algorithm_version": DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION,
        "source_sample_id": source_sample_id,
        "prompt_family_id": prompt_family_id,
        "source_text_hash": source_hash,
        "transformed_text_hash": transformed_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "scheduler_input_hash": scheduler_input.input_artifact_hash,
        "schedule_result_hash": schedule_result.result_hash,
        "transform_result_hash": transform_result.result_hash,
        "trace_hash": transform_result.trace.trace_hash,
        "schedule_policy": schedule_result.policy.value,
        "schedule_seed": schedule_result.seed,
        "budget": schedule_result.budget,
        "budget_unit": scheduler_input.budget_unit,
        "realized_edit_cost": schedule_result.total_cost,
        "scheduler_covered_interval_size": schedule_result.covered_interval_size,
        "selected_candidate_ids": schedule_result.selected_candidate_ids,
    }
    return VerifiedTransformProvenance(
        DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION,
        source_sample_id,
        prompt_family_id,
        source_hash,
        transformed_hash,
        enumeration.enumeration_hash,
        scheduler_input.input_artifact_hash,
        schedule_result.result_hash,
        transform_result.result_hash,
        transform_result.trace.trace_hash,
        schedule_result.policy,
        schedule_result.seed,
        schedule_result.budget,
        scheduler_input.budget_unit,
        schedule_result.total_cost,
        schedule_result.covered_interval_size,
        schedule_result.selected_candidate_ids,
        sha256_json(payload),
    )


def build_verified_transform_row(
    provenance: VerifiedTransformProvenance,
    *,
    key_split,
    detector_identity_hash: str,
    threshold_hash: str,
    threshold_value: float,
    word_edit_count: int,
    word_count: int,
    observation_replacement_count: int,
    original_observation_count: int,
    pristine_score: float,
    transformed_score: float,
    secret_access_observed: bool = False,
) -> DevelopmentTransformRow:
    if not isinstance(provenance, VerifiedTransformProvenance):
        raise TypeError("provenance must be a VerifiedTransformProvenance")
    return DevelopmentTransformRow.create(
        source_sample_id=provenance.source_sample_id,
        prompt_family_id=provenance.prompt_family_id,
        source_text_hash=provenance.source_text_hash,
        transformed_text_hash=provenance.transformed_text_hash,
        key_split=key_split,
        detector_identity_hash=detector_identity_hash,
        threshold_hash=threshold_hash,
        threshold_value=threshold_value,
        candidate_pool_hash=provenance.enumeration_hash,
        scheduler_input_hash=provenance.scheduler_input_hash,
        schedule_result_hash=provenance.schedule_result_hash,
        schedule_policy=provenance.schedule_policy,
        schedule_seed=provenance.schedule_seed,
        budget=provenance.budget,
        budget_unit=provenance.budget_unit,
        realized_edit_cost=provenance.realized_edit_cost,
        scheduler_covered_interval_size=provenance.scheduler_covered_interval_size,
        word_edit_count=word_edit_count,
        word_count=word_count,
        observation_replacement_count=observation_replacement_count,
        original_observation_count=original_observation_count,
        pristine_score=pristine_score,
        transformed_score=transformed_score,
        eligible=provenance.eligible,
        secret_access_observed=secret_access_observed,
    )
