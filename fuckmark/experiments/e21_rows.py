from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from .e20_execution import E20_EXPERIMENT_ID
from .e20_rows import (
    E20AlignmentFields,
    E20AuditFields,
    E20DetectorFields,
    E20FailureRow,
    E20FailureStage,
    E20FidelityFields,
    E20GValueFields,
    E20GenerationFields,
    E20HumanFidelityStatus,
    E20IdentityFields,
    E20ModelFields,
    E20ObservationFields,
    E20OutcomeRow,
    E20SourceFields,
    E20StatisticsFields,
    E20TextFields,
    E20TransformFields,
    E20WatermarkFields,
    ExperimentReasonCode,
)
from .e21_rerun import E21_EXPERIMENT_ID


E21_OUTCOME_ROW_ALGORITHM_VERSION = "e21-outcome-row-v1"
E21_FAILURE_ROW_ALGORITHM_VERSION = "e21-failure-row-v1"
E21SourceFields = E20SourceFields
E21ModelFields = E20ModelFields
E21WatermarkFields = E20WatermarkFields
E21GenerationFields = E20GenerationFields
E21TextFields = E20TextFields
E21TransformFields = E20TransformFields
E21FidelityFields = E20FidelityFields
E21AlignmentFields = E20AlignmentFields
E21ObservationFields = E20ObservationFields
E21GValueFields = E20GValueFields
E21DetectorFields = E20DetectorFields
E21StatisticsFields = E20StatisticsFields
E21AuditFields = E20AuditFields
E21HumanFidelityStatus = E20HumanFidelityStatus
E21FailureStage = E20FailureStage


@dataclass(frozen=True, slots=True)
class E21IdentityFields:
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
            raise ValueError("E21 run_id must equal the sealed execution_id")
        if self.experiment_id != E21_EXPERIMENT_ID:
            raise ValueError("E21 result identity must use experiment_id E21")
        for name, value in (
            ("condition_id", self.condition_id),
            ("sample_id", self.sample_id),
            ("pair_id", self.pair_id),
        ):
            require_clean_string(name, value)


def _e20_identity(identity: E21IdentityFields) -> E20IdentityFields:
    return E20IdentityFields(
        identity.execution_id,
        identity.run_id,
        E20_EXPERIMENT_ID,
        identity.condition_id,
        identity.sample_id,
        identity.pair_id,
    )


@dataclass(frozen=True, slots=True)
class E21OutcomeRow:
    algorithm_version: str
    identity: E21IdentityFields
    source: E21SourceFields
    model: E21ModelFields
    watermark: E21WatermarkFields
    generation: E21GenerationFields
    text: E21TextFields
    transform: E21TransformFields
    fidelity: E21FidelityFields
    alignment: E21AlignmentFields
    observation: E21ObservationFields
    gvalues: E21GValueFields
    detector: E21DetectorFields
    statistics: E21StatisticsFields
    audit: E21AuditFields
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_OUTCOME_ROW_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 outcome row algorithm version")
        if not isinstance(self.identity, E21IdentityFields):
            raise TypeError("identity must be an E21IdentityFields")
        E20OutcomeRow.create(
            _e20_identity(self.identity),
            self.source,
            self.model,
            self.watermark,
            self.generation,
            self.text,
            self.transform,
            self.fidelity,
            self.alignment,
            self.observation,
            self.gvalues,
            self.detector,
            self.statistics,
            self.audit,
        )
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E21 outcome row")

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
        identity: E21IdentityFields,
        source: E21SourceFields,
        model: E21ModelFields,
        watermark: E21WatermarkFields,
        generation: E21GenerationFields,
        text: E21TextFields,
        transform: E21TransformFields,
        fidelity: E21FidelityFields,
        alignment: E21AlignmentFields,
        observation: E21ObservationFields,
        gvalues: E21GValueFields,
        detector: E21DetectorFields,
        statistics: E21StatisticsFields,
        audit: E21AuditFields,
    ) -> E21OutcomeRow:
        payload = {
            "algorithm_version": E21_OUTCOME_ROW_ALGORITHM_VERSION,
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
            E21_OUTCOME_ROW_ALGORITHM_VERSION,
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
class E21FailureRow:
    algorithm_version: str
    identity: E21IdentityFields
    stage: E21FailureStage
    reason_code: ExperimentReasonCode
    source_sample_record_hash: str
    detail_hash: str
    audit: E21AuditFields
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_FAILURE_ROW_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 failure row algorithm version")
        if not isinstance(self.identity, E21IdentityFields):
            raise TypeError("identity must be an E21IdentityFields")
        E20FailureRow.create(
            _e20_identity(self.identity),
            self.stage,
            self.reason_code,
            self.source_sample_record_hash,
            self.detail_hash,
            self.audit,
        )
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self._payload()):
            raise ValueError("row_hash does not match E21 failure row")

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
        identity: E21IdentityFields,
        stage: E21FailureStage,
        reason_code: ExperimentReasonCode,
        source_sample_record_hash: str,
        detail_hash: str,
        audit: E21AuditFields,
    ) -> E21FailureRow:
        payload = {
            "algorithm_version": E21_FAILURE_ROW_ALGORITHM_VERSION,
            "identity": identity,
            "stage": stage.value if isinstance(stage, E20FailureStage) else stage,
            "reason_code": reason_code.value if isinstance(reason_code, ExperimentReasonCode) else reason_code,
            "source_sample_record_hash": source_sample_record_hash,
            "detail_hash": detail_hash,
            "audit": audit,
        }
        return cls(
            E21_FAILURE_ROW_ALGORITHM_VERSION,
            identity,
            stage,
            reason_code,
            source_sample_record_hash,
            detail_hash,
            audit,
            sha256_json(payload),
        )
