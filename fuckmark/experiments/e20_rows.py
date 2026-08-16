from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import KeySplit
from ..detectors import DetectorFamily
from ..hashing import sha256_json
from ..transforms import SchedulePolicy
from .e20_execution import E20_EXPERIMENT_ID


E20_OUTCOME_ROW_ALGORITHM_VERSION = "e20-outcome-row-v1"
E20_FAILURE_ROW_ALGORITHM_VERSION = "e20-failure-row-v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_IMMUTABLE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ALLOWED_E20_SCHEDULES = (
    SchedulePolicy.RANDOM_VALID,
    SchedulePolicy.EVEN_SPACING,
    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
)


class ExperimentReasonCode(str, Enum):
    OK = "OK"
    NO_ELIGIBLE_TRANSFORM = "NO_ELIGIBLE_TRANSFORM"
    REALIZED_BUDGET_EXCEEDED = "REALIZED_BUDGET_EXCEEDED"
    PROTECTED_SPAN_CONFLICT = "PROTECTED_SPAN_CONFLICT"
    HARD_INVARIANT_FAILURE = "HARD_INVARIANT_FAILURE"
    ALIGNMENT_AMBIGUOUS = "ALIGNMENT_AMBIGUOUS"
    TOKENIZATION_FAILURE = "TOKENIZATION_FAILURE"
    GENERATION_EARLY_EOS = "GENERATION_EARLY_EOS"
    DETECTOR_SCORE_NA = "DETECTOR_SCORE_NA"
    ZERO_VALID_OBSERVATIONS = "ZERO_VALID_OBSERVATIONS"
    CALIBRATION_MISSING = "CALIBRATION_MISSING"
    SOURCE_PIN_MISMATCH = "SOURCE_PIN_MISMATCH"
    SEALED_KEY_CONTAMINATION = "SEALED_KEY_CONTAMINATION"
    HUMAN_FIDELITY_MATERIAL_CHANGE = "HUMAN_FIDELITY_MATERIAL_CHANGE"
    UPSTREAM_API_CHANGED = "UPSTREAM_API_CHANGED"
    EXTERNAL_INTERFACE_UNAVAILABLE = "EXTERNAL_INTERFACE_UNAVAILABLE"


class E20HumanFidelityStatus(str, Enum):
    NOT_SELECTED = "NOT_SELECTED"
    EQUIVALENT_OR_MINOR = "EQUIVALENT_OR_MINOR"
    MATERIAL_CHANGE = "MATERIAL_CHANGE"
    CANNOT_JUDGE = "CANNOT_JUDGE"


class E20FailureStage(str, Enum):
    SOURCE = "SOURCE"
    SEALED_DATA = "SEALED_DATA"
    GENERATION = "GENERATION"
    TOKENIZATION = "TOKENIZATION"
    TRANSFORM = "TRANSFORM"
    FIDELITY = "FIDELITY"
    ALIGNMENT = "ALIGNMENT"
    OBSERVATION = "OBSERVATION"
    DETECTOR = "DETECTOR"
    CALIBRATION = "CALIBRATION"
    EXTERNAL = "EXTERNAL"


_OUTCOME_REASON_CODES = frozenset(
    {
        ExperimentReasonCode.OK,
        ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM,
        ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE,
    }
)


def _probability(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


def _finite(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class E20IdentityFields:
    execution_id: str
    run_id: str
    experiment_id: str
    condition_id: str
    sample_id: str
    pair_id: str

    def __post_init__(self) -> None:
        require_sha256("execution_id", self.execution_id)
        require_sha256("run_id", self.run_id)
        if self.run_id != self.execution_id:
            raise ValueError("E20 run_id must equal the sealed execution_id")
        if self.experiment_id != E20_EXPERIMENT_ID:
            raise ValueError("E20 result identity must use experiment_id E20")
        for name, value in (
            ("condition_id", self.condition_id),
            ("sample_id", self.sample_id),
            ("pair_id", self.pair_id),
        ):
            require_clean_string(name, value)


@dataclass(frozen=True, slots=True)
class E20SourceFields:
    adapter_id: str
    source_commit: str
    adapter_config_hash: str

    def __post_init__(self) -> None:
        require_clean_string("adapter_id", self.adapter_id)
        if _GIT_SHA_RE.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be a full lowercase 40-character Git revision")
        require_sha256("adapter_config_hash", self.adapter_config_hash)


@dataclass(frozen=True, slots=True)
class E20ModelFields:
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str

    def __post_init__(self) -> None:
        require_clean_string("model_id", self.model_id)
        require_clean_string("tokenizer_id", self.tokenizer_id)
        if _IMMUTABLE_REVISION_RE.fullmatch(self.model_revision) is None:
            raise ValueError("model_revision must be an immutable lowercase hexadecimal revision")
        if _IMMUTABLE_REVISION_RE.fullmatch(self.tokenizer_revision) is None:
            raise ValueError("tokenizer_revision must be an immutable lowercase hexadecimal revision")


@dataclass(frozen=True, slots=True)
class E20WatermarkFields:
    watermark_config_hash: str
    key_split: KeySplit
    key_id: str

    def __post_init__(self) -> None:
        require_sha256("watermark_config_hash", self.watermark_config_hash)
        if self.key_split is not KeySplit.TEST:
            raise ValueError("E20 outcome rows must use TEST_KEYS")
        require_clean_string("key_id", self.key_id)


@dataclass(frozen=True, slots=True)
class E20GenerationFields:
    seed: int
    temperature: float
    top_k: int
    top_p: float
    realized_length: int

    def __post_init__(self) -> None:
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        temperature = _finite("temperature", self.temperature)
        if temperature < 0.0:
            raise ValueError("temperature must be non-negative")
        object.__setattr__(self, "temperature", temperature)
        require_int("top_k", self.top_k)
        if self.top_k < 0:
            raise ValueError("top_k must be non-negative")
        top_p = _probability("top_p", self.top_p)
        if top_p <= 0.0:
            raise ValueError("top_p must be positive")
        object.__setattr__(self, "top_p", top_p)
        require_int("realized_length", self.realized_length)
        if self.realized_length <= 0:
            raise ValueError("realized_length must be positive")


@dataclass(frozen=True, slots=True)
class E20TextFields:
    source_text_hash: str
    transformed_text_hash: str
    source_char_count: int
    transformed_char_count: int
    source_word_count: int
    transformed_word_count: int
    source_token_count: int
    transformed_token_count: int

    def __post_init__(self) -> None:
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        for name, value in (
            ("source_char_count", self.source_char_count),
            ("transformed_char_count", self.transformed_char_count),
            ("source_word_count", self.source_word_count),
            ("transformed_word_count", self.transformed_word_count),
            ("source_token_count", self.source_token_count),
            ("transformed_token_count", self.transformed_token_count),
        ):
            require_int(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class E20TransformFields:
    ruleset_hash: str
    schedule_policy: SchedulePolicy
    schedule_seed: int
    budget: int
    budget_unit: str
    realized_edit_cost: int
    candidate_pool_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    operation_trace_hash: str
    eligible: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("ruleset_hash", self.ruleset_hash),
            ("candidate_pool_hash", self.candidate_pool_hash),
            ("scheduler_input_hash", self.scheduler_input_hash),
            ("schedule_result_hash", self.schedule_result_hash),
            ("operation_trace_hash", self.operation_trace_hash),
        ):
            require_sha256(name, value)
        if self.schedule_policy not in _ALLOWED_E20_SCHEDULES:
            raise ValueError("E20 schedule_policy is not part of the frozen confirmatory schedule set")
        require_int("schedule_seed", self.schedule_seed)
        if self.schedule_seed < 0 or self.schedule_seed >= 1 << 64:
            raise ValueError("schedule_seed must be between 0 and 2^64-1")
        require_int("budget", self.budget)
        require_int("realized_edit_cost", self.realized_edit_cost)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        if self.realized_edit_cost < 0 or self.realized_edit_cost > self.budget:
            raise ValueError("realized_edit_cost must lie inside the requested budget")
        require_clean_string("budget_unit", self.budget_unit)
        require_bool("eligible", self.eligible)
        if self.eligible and self.realized_edit_cost <= 0:
            raise ValueError("eligible E20 outcomes must realize positive edit cost")
        if not self.eligible and self.realized_edit_cost != 0:
            raise ValueError("ineligible E20 outcomes must realize zero edit cost")


@dataclass(frozen=True, slots=True)
class E20FidelityFields:
    hard_pass: bool
    reason_codes: tuple[ExperimentReasonCode, ...]
    char_edit_distance: int
    word_edit_distance: int
    token_edit_distance: int
    human_status: E20HumanFidelityStatus
    human_adjudication_hash: str | None

    def __post_init__(self) -> None:
        require_bool("hard_pass", self.hard_pass)
        if not self.hard_pass:
            raise ValueError("complete E20 outcome rows require hard fidelity pass; failures use E20FailureRow")
        if not isinstance(self.reason_codes, tuple) or len(self.reason_codes) != 1:
            raise ValueError("complete E20 outcome rows require exactly one primary reason code")
        if not isinstance(self.reason_codes[0], ExperimentReasonCode):
            raise TypeError("reason_codes must contain ExperimentReasonCode values")
        if self.reason_codes[0] not in _OUTCOME_REASON_CODES:
            raise ValueError("this reason code requires an E20FailureRow rather than a complete outcome row")
        for name, value in (
            ("char_edit_distance", self.char_edit_distance),
            ("word_edit_distance", self.word_edit_distance),
            ("token_edit_distance", self.token_edit_distance),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.human_status, E20HumanFidelityStatus):
            raise TypeError("human_status must be an E20HumanFidelityStatus")
        if self.human_status is E20HumanFidelityStatus.NOT_SELECTED:
            if self.human_adjudication_hash is not None:
                raise ValueError("non-selected human fidelity rows cannot name an adjudication hash")
        else:
            if self.human_adjudication_hash is None:
                raise ValueError("reviewed human fidelity rows require an adjudication hash")
            require_sha256("human_adjudication_hash", self.human_adjudication_hash)
        material = self.human_status is E20HumanFidelityStatus.MATERIAL_CHANGE
        material_code = self.reason_codes[0] is ExperimentReasonCode.HUMAN_FIDELITY_MATERIAL_CHANGE
        if material != material_code:
            raise ValueError("human material-change status and reason code must agree")


@dataclass(frozen=True, slots=True)
class E20AlignmentFields:
    algorithm_version: str
    edit_script_hash: str
    ambiguity_count: int

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_sha256("edit_script_hash", self.edit_script_hash)
        require_int("ambiguity_count", self.ambiguity_count)
        if self.ambiguity_count != 0:
            raise ValueError("complete E20 outcome rows require unambiguous alignment")


@dataclass(frozen=True, slots=True)
class E20ObservationFields:
    original_valid_count: int
    transformed_valid_count: int
    preserved_count: int
    replaced_count: int
    dropped_count: int
    added_count: int
    original_masked_count: int
    transformed_masked_count: int

    def __post_init__(self) -> None:
        for name, value in (
            ("original_valid_count", self.original_valid_count),
            ("transformed_valid_count", self.transformed_valid_count),
            ("preserved_count", self.preserved_count),
            ("replaced_count", self.replaced_count),
            ("dropped_count", self.dropped_count),
            ("added_count", self.added_count),
            ("original_masked_count", self.original_masked_count),
            ("transformed_masked_count", self.transformed_masked_count),
        ):
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.original_valid_count <= 0 or self.transformed_valid_count <= 0:
            raise ValueError("complete E20 outcome rows require positive valid observation counts")
        if self.preserved_count + self.replaced_count + self.dropped_count != self.original_valid_count:
            raise ValueError("original valid observation accounting does not close")
        if self.preserved_count + self.replaced_count + self.added_count != self.transformed_valid_count:
            raise ValueError("transformed valid observation accounting does not close")

    @property
    def replacement_ratio(self) -> float:
        return self.replaced_count / self.original_valid_count


@dataclass(frozen=True, slots=True)
class E20GValueFields:
    depth: int
    per_depth_summary_hash: str
    matched_observation_count: int
    hamming_difference_count: int

    def __post_init__(self) -> None:
        require_int("depth", self.depth)
        require_int("matched_observation_count", self.matched_observation_count)
        require_int("hamming_difference_count", self.hamming_difference_count)
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if self.matched_observation_count < 0:
            raise ValueError("matched_observation_count must be non-negative")
        maximum = self.matched_observation_count * self.depth
        if self.hamming_difference_count < 0 or self.hamming_difference_count > maximum:
            raise ValueError("hamming_difference_count exceeds matched observation geometry")
        require_sha256("per_depth_summary_hash", self.per_depth_summary_hash)

    @property
    def matched_hamming_rate(self) -> float | None:
        denominator = self.matched_observation_count * self.depth
        if denominator == 0:
            return None
        return self.hamming_difference_count / denominator


@dataclass(frozen=True, slots=True)
class E20DetectorFields:
    detector_family: DetectorFamily
    detector_config_hash: str
    checkpoint_hash: str | None
    calibration_bundle_hash: str
    threshold_hash: str
    target_fpr: float
    threshold_value: float
    pristine_raw_score: float
    transformed_raw_score: float
    pristine_standardized_margin: float
    transformed_standardized_margin: float
    pristine_decision: bool
    transformed_decision: bool

    def __post_init__(self) -> None:
        if not isinstance(self.detector_family, DetectorFamily):
            raise TypeError("detector_family must be a DetectorFamily")
        for name, value in (
            ("detector_config_hash", self.detector_config_hash),
            ("calibration_bundle_hash", self.calibration_bundle_hash),
            ("threshold_hash", self.threshold_hash),
        ):
            require_sha256(name, value)
        if self.checkpoint_hash is not None:
            require_sha256("checkpoint_hash", self.checkpoint_hash)
        if self.detector_family is DetectorFamily.BAYESIAN and self.checkpoint_hash is None:
            raise ValueError("Bayesian E20 detector rows require a checkpoint hash")
        target = _probability("target_fpr", self.target_fpr)
        if target <= 0.0 or target >= 1.0:
            raise ValueError("target_fpr must be strictly between 0 and 1")
        object.__setattr__(self, "target_fpr", target)
        object.__setattr__(self, "threshold_value", _probability("threshold_value", self.threshold_value))
        object.__setattr__(self, "pristine_raw_score", _probability("pristine_raw_score", self.pristine_raw_score))
        object.__setattr__(self, "transformed_raw_score", _probability("transformed_raw_score", self.transformed_raw_score))
        object.__setattr__(self, "pristine_standardized_margin", _finite("pristine_standardized_margin", self.pristine_standardized_margin))
        object.__setattr__(self, "transformed_standardized_margin", _finite("transformed_standardized_margin", self.transformed_standardized_margin))
        require_bool("pristine_decision", self.pristine_decision)
        require_bool("transformed_decision", self.transformed_decision)


@dataclass(frozen=True, slots=True)
class E20StatisticsFields:
    stratum_id: str
    bootstrap_group: str
    hypothesis_class: str

    def __post_init__(self) -> None:
        require_clean_string("stratum_id", self.stratum_id)
        require_clean_string("bootstrap_group", self.bootstrap_group)
        require_clean_string("hypothesis_class", self.hypothesis_class)


@dataclass(frozen=True, slots=True)
class E20AuditFields:
    worker_version: str
    timestamp_utc: str
    environment_snapshot_hash: str
    authorization_hash: str
    ledger_hash: str
    artifact_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        require_clean_string("worker_version", self.worker_version)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", self.timestamp_utc) is None:
            raise ValueError("timestamp_utc must use canonical second-resolution UTC form")
        for name, value in (
            ("environment_snapshot_hash", self.environment_snapshot_hash),
            ("authorization_hash", self.authorization_hash),
            ("ledger_hash", self.ledger_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.artifact_hashes, tuple) or not self.artifact_hashes:
            raise TypeError("artifact_hashes must be a non-empty tuple")
        if self.artifact_hashes != tuple(sorted(self.artifact_hashes)):
            raise ValueError("artifact_hashes must be canonically ordered")
        if len(set(self.artifact_hashes)) != len(self.artifact_hashes):
            raise ValueError("artifact_hashes must be unique")
        for value in self.artifact_hashes:
            require_sha256("artifact_hash", value)


@dataclass(frozen=True, slots=True)
class E20OutcomeRow:
    algorithm_version: str
    identity: E20IdentityFields
    source: E20SourceFields
    model: E20ModelFields
    watermark: E20WatermarkFields
    generation: E20GenerationFields
    text: E20TextFields
    transform: E20TransformFields
    fidelity: E20FidelityFields
    alignment: E20AlignmentFields
    observation: E20ObservationFields
    gvalues: E20GValueFields
    detector: E20DetectorFields
    statistics: E20StatisticsFields
    audit: E20AuditFields
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_OUTCOME_ROW_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 outcome row algorithm version")
        groups = (
            ("identity", self.identity, E20IdentityFields),
            ("source", self.source, E20SourceFields),
            ("model", self.model, E20ModelFields),
            ("watermark", self.watermark, E20WatermarkFields),
            ("generation", self.generation, E20GenerationFields),
            ("text", self.text, E20TextFields),
            ("transform", self.transform, E20TransformFields),
            ("fidelity", self.fidelity, E20FidelityFields),
            ("alignment", self.alignment, E20AlignmentFields),
            ("observation", self.observation, E20ObservationFields),
            ("gvalues", self.gvalues, E20GValueFields),
            ("detector", self.detector, E20DetectorFields),
            ("statistics", self.statistics, E20StatisticsFields),
            ("audit", self.audit, E20AuditFields),
        )
        for name, value, expected_type in groups:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be an {expected_type.__name__}")
        reason = self.fidelity.reason_codes[0]
        if reason is ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM:
            if self.transform.eligible:
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows cannot be eligible")
            if self.text.source_text_hash != self.text.transformed_text_hash:
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve text")
            if (
                self.text.source_char_count != self.text.transformed_char_count
                or self.text.source_word_count != self.text.transformed_word_count
                or self.text.source_token_count != self.text.transformed_token_count
            ):
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve text counts")
            if any(
                value != 0
                for value in (
                    self.fidelity.char_edit_distance,
                    self.fidelity.word_edit_distance,
                    self.fidelity.token_edit_distance,
                    self.observation.replaced_count,
                    self.observation.dropped_count,
                    self.observation.added_count,
                )
            ):
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve edit and observation geometry")
            if self.observation.original_valid_count != self.observation.transformed_valid_count:
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve valid observation count")
            if self.observation.preserved_count != self.observation.original_valid_count:
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve every valid observation")
            if (
                self.detector.pristine_raw_score != self.detector.transformed_raw_score
                or self.detector.pristine_standardized_margin != self.detector.transformed_standardized_margin
                or self.detector.pristine_decision != self.detector.transformed_decision
            ):
                raise ValueError("NO_ELIGIBLE_TRANSFORM rows must preserve detector outcome")
        else:
            if not self.transform.eligible:
                raise ValueError("complete changed E20 outcomes must be eligible")
            if self.text.source_text_hash == self.text.transformed_text_hash:
                raise ValueError("eligible E20 outcomes must change text")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E20 outcome row")

    @property
    def observation_replacement_ratio(self) -> float:
        return self.observation.replacement_ratio

    @property
    def standardized_margin_drop(self) -> float:
        return self.detector.pristine_standardized_margin - self.detector.transformed_standardized_margin

    @property
    def decision_loss(self) -> bool:
        return self.detector.pristine_decision and not self.detector.transformed_decision

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "identity": self.identity,
            "source": self.source,
            "model": self.model,
            "watermark": self.watermark,
            "generation": self.generation,
            "text": self.text,
            "transform": self.transform,
            "fidelity": self.fidelity,
            "alignment": self.alignment,
            "observation": self.observation,
            "gvalues": self.gvalues,
            "detector": self.detector,
            "statistics": self.statistics,
            "audit": self.audit,
        }

    @classmethod
    def create(
        cls,
        identity: E20IdentityFields,
        source: E20SourceFields,
        model: E20ModelFields,
        watermark: E20WatermarkFields,
        generation: E20GenerationFields,
        text: E20TextFields,
        transform: E20TransformFields,
        fidelity: E20FidelityFields,
        alignment: E20AlignmentFields,
        observation: E20ObservationFields,
        gvalues: E20GValueFields,
        detector: E20DetectorFields,
        statistics: E20StatisticsFields,
        audit: E20AuditFields,
    ) -> E20OutcomeRow:
        payload = {
            "algorithm_version": E20_OUTCOME_ROW_ALGORITHM_VERSION,
            "identity": identity,
            "source": source,
            "model": model,
            "watermark": watermark,
            "generation": generation,
            "text": text,
            "transform": transform,
            "fidelity": fidelity,
            "alignment": alignment,
            "observation": observation,
            "gvalues": gvalues,
            "detector": detector,
            "statistics": statistics,
            "audit": audit,
        }
        return cls(
            E20_OUTCOME_ROW_ALGORITHM_VERSION,
            identity,
            source,
            model,
            watermark,
            generation,
            text,
            transform,
            fidelity,
            alignment,
            observation,
            gvalues,
            detector,
            statistics,
            audit,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E20FailureRow:
    algorithm_version: str
    identity: E20IdentityFields
    stage: E20FailureStage
    reason_code: ExperimentReasonCode
    source_sample_record_hash: str
    detail_hash: str
    audit: E20AuditFields
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_FAILURE_ROW_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 failure row algorithm version")
        if not isinstance(self.identity, E20IdentityFields):
            raise TypeError("identity must be E20IdentityFields")
        if not isinstance(self.stage, E20FailureStage):
            raise TypeError("stage must be an E20FailureStage")
        if not isinstance(self.reason_code, ExperimentReasonCode):
            raise TypeError("reason_code must be an ExperimentReasonCode")
        if self.reason_code in _OUTCOME_REASON_CODES:
            raise ValueError("complete outcome reason codes cannot be represented as E20FailureRow")
        require_sha256("source_sample_record_hash", self.source_sample_record_hash)
        require_sha256("detail_hash", self.detail_hash)
        if not isinstance(self.audit, E20AuditFields):
            raise TypeError("audit must be E20AuditFields")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E20 failure row")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "identity": self.identity,
            "stage": self.stage.value,
            "reason_code": self.reason_code.value,
            "source_sample_record_hash": self.source_sample_record_hash,
            "detail_hash": self.detail_hash,
            "audit": self.audit,
        }

    @classmethod
    def create(
        cls,
        identity: E20IdentityFields,
        stage: E20FailureStage,
        reason_code: ExperimentReasonCode,
        source_sample_record_hash: str,
        detail_hash: str,
        audit: E20AuditFields,
    ) -> E20FailureRow:
        payload = {
            "algorithm_version": E20_FAILURE_ROW_ALGORITHM_VERSION,
            "identity": identity,
            "stage": stage.value if isinstance(stage, E20FailureStage) else stage,
            "reason_code": reason_code.value if isinstance(reason_code, ExperimentReasonCode) else reason_code,
            "source_sample_record_hash": source_sample_record_hash,
            "detail_hash": detail_hash,
            "audit": audit,
        }
        return cls(
            E20_FAILURE_ROW_ALGORITHM_VERSION,
            identity,
            stage,
            reason_code,
            source_sample_record_hash,
            detail_hash,
            audit,
            sha256_json(payload),
        )
