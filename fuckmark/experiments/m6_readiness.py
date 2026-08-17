from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .registry import (
    DevelopmentExperimentId,
    DevelopmentExperimentRegistry,
)


M6_READINESS_ALGORITHM_VERSION = "m6-development-readiness-v1"
_M6_REQUIRED_EXPERIMENTS = (
    DevelopmentExperimentId.E07,
    DevelopmentExperimentId.E08,
    DevelopmentExperimentId.E09,
    DevelopmentExperimentId.E10,
    DevelopmentExperimentId.E11,
    DevelopmentExperimentId.E12,
    DevelopmentExperimentId.E13,
    DevelopmentExperimentId.E14,
    DevelopmentExperimentId.E15,
    DevelopmentExperimentId.E16,
    DevelopmentExperimentId.E17,
    DevelopmentExperimentId.E18,
    DevelopmentExperimentId.E19,
)


class M6EvidencePartition(str, Enum):
    DEV = "DEV"
    VALIDATION = "VALIDATION"


class M6ReadinessStatus(str, Enum):
    READY = "READY"
    MISSING_EXPERIMENT_EVIDENCE = "MISSING_EXPERIMENT_EVIDENCE"
    MISSING_POWER_ANALYSIS = "MISSING_POWER_ANALYSIS"
    MISSING_EXPERIMENT_EVIDENCE_AND_POWER_ANALYSIS = "MISSING_EXPERIMENT_EVIDENCE_AND_POWER_ANALYSIS"


@dataclass(frozen=True, slots=True)
class M6ExperimentEvidence:
    experiment_id: DevelopmentExperimentId
    definition_hash: str
    partition: M6EvidencePartition
    artifact_hash: str
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.experiment_id not in _M6_REQUIRED_EXPERIMENTS:
            raise ValueError("M6 experiment evidence must target E07 through E19")
        require_sha256("definition_hash", self.definition_hash)
        if not isinstance(self.partition, M6EvidencePartition):
            raise TypeError("partition must be an M6EvidencePartition")
        require_sha256("artifact_hash", self.artifact_hash)
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match M6 experiment evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id.value,
            "definition_hash": self.definition_hash,
            "partition": self.partition.value,
            "artifact_hash": self.artifact_hash,
        }

    @classmethod
    def create(
        cls,
        experiment_id: DevelopmentExperimentId,
        definition_hash: str,
        partition: M6EvidencePartition,
        artifact_hash: str,
    ) -> M6ExperimentEvidence:
        payload = {
            "experiment_id": experiment_id.value,
            "definition_hash": definition_hash,
            "partition": partition.value,
            "artifact_hash": artifact_hash,
        }
        return cls(
            experiment_id,
            definition_hash,
            partition,
            artifact_hash,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class M6PowerAnalysisEvidence:
    method_id: str
    validation_input_hash: str
    analysis_artifact_hash: str
    final_n_per_core_cell: int
    evidence_hash: str

    def __post_init__(self) -> None:
        require_clean_string("method_id", self.method_id)
        require_sha256("validation_input_hash", self.validation_input_hash)
        require_sha256("analysis_artifact_hash", self.analysis_artifact_hash)
        require_int("final_n_per_core_cell", self.final_n_per_core_cell)
        if self.final_n_per_core_cell <= 0:
            raise ValueError("final_n_per_core_cell must be positive")
        require_sha256("evidence_hash", self.evidence_hash)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match M6 power analysis evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "method_id": self.method_id,
            "validation_input_hash": self.validation_input_hash,
            "analysis_artifact_hash": self.analysis_artifact_hash,
            "final_n_per_core_cell": self.final_n_per_core_cell,
        }

    @classmethod
    def create(
        cls,
        method_id: str,
        validation_input_hash: str,
        analysis_artifact_hash: str,
        final_n_per_core_cell: int,
    ) -> M6PowerAnalysisEvidence:
        payload = {
            "method_id": method_id,
            "validation_input_hash": validation_input_hash,
            "analysis_artifact_hash": analysis_artifact_hash,
            "final_n_per_core_cell": final_n_per_core_cell,
        }
        return cls(
            method_id,
            validation_input_hash,
            analysis_artifact_hash,
            final_n_per_core_cell,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class M6ReadinessReport:
    algorithm_version: str
    registry_hash: str
    evidence: tuple[M6ExperimentEvidence, ...]
    missing_experiments: tuple[DevelopmentExperimentId, ...]
    power_analysis: M6PowerAnalysisEvidence | None
    status: M6ReadinessStatus
    ready_for_m7: bool
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != M6_READINESS_ALGORITHM_VERSION:
            raise ValueError("unsupported M6 readiness algorithm version")
        require_sha256("registry_hash", self.registry_hash)
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        if any(not isinstance(value, M6ExperimentEvidence) for value in self.evidence):
            raise TypeError("evidence must contain M6ExperimentEvidence values")
        expected_evidence = tuple(sorted(self.evidence, key=lambda value: value.experiment_id.value))
        if self.evidence != expected_evidence:
            raise ValueError("M6 experiment evidence must be canonically ordered")
        ids = tuple(value.experiment_id for value in self.evidence)
        if len(set(ids)) != len(ids):
            raise ValueError("M6 experiment evidence must contain at most one row per experiment")
        if not isinstance(self.missing_experiments, tuple):
            raise TypeError("missing_experiments must be a tuple")
        expected_missing = tuple(value for value in _M6_REQUIRED_EXPERIMENTS if value not in ids)
        if self.missing_experiments != expected_missing:
            raise ValueError("missing_experiments does not match supplied evidence")
        if self.power_analysis is not None and not isinstance(self.power_analysis, M6PowerAnalysisEvidence):
            raise TypeError("power_analysis must be M6PowerAnalysisEvidence or None")
        missing_evidence = bool(self.missing_experiments)
        missing_power = self.power_analysis is None
        if missing_evidence and missing_power:
            expected_status = M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE_AND_POWER_ANALYSIS
        elif missing_evidence:
            expected_status = M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE
        elif missing_power:
            expected_status = M6ReadinessStatus.MISSING_POWER_ANALYSIS
        else:
            expected_status = M6ReadinessStatus.READY
        if self.status is not expected_status:
            raise ValueError("M6 readiness status does not match evidence completeness")
        expected_ready = expected_status is M6ReadinessStatus.READY
        if self.ready_for_m7 is not expected_ready:
            raise ValueError("ready_for_m7 does not match M6 readiness status")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match M6 readiness report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "registry_hash": self.registry_hash,
            "evidence": self.evidence,
            "missing_experiments": tuple(value.value for value in self.missing_experiments),
            "power_analysis": self.power_analysis,
            "status": self.status.value,
            "ready_for_m7": self.ready_for_m7,
        }


def build_m6_readiness(
    registry: DevelopmentExperimentRegistry,
    evidence: tuple[M6ExperimentEvidence, ...],
    power_analysis: M6PowerAnalysisEvidence | None,
) -> M6ReadinessReport:
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(evidence, tuple):
        raise TypeError("evidence must be a tuple")
    if any(not isinstance(value, M6ExperimentEvidence) for value in evidence):
        raise TypeError("evidence must contain M6ExperimentEvidence values")
    by_id = {value.experiment_id: value for value in evidence}
    if len(by_id) != len(evidence):
        raise ValueError("M6 experiment evidence must contain at most one row per experiment")
    for experiment_id, row in by_id.items():
        definition = registry.get(experiment_id)
        if row.definition_hash != definition.definition_hash:
            raise ValueError("M6 experiment evidence definition hash does not match the frozen registry")
    ordered = tuple(by_id[value] for value in _M6_REQUIRED_EXPERIMENTS if value in by_id)
    missing = tuple(value for value in _M6_REQUIRED_EXPERIMENTS if value not in by_id)
    if missing and power_analysis is None:
        status = M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE_AND_POWER_ANALYSIS
    elif missing:
        status = M6ReadinessStatus.MISSING_EXPERIMENT_EVIDENCE
    elif power_analysis is None:
        status = M6ReadinessStatus.MISSING_POWER_ANALYSIS
    else:
        status = M6ReadinessStatus.READY
    ready = status is M6ReadinessStatus.READY
    payload = {
        "algorithm_version": M6_READINESS_ALGORITHM_VERSION,
        "registry_hash": registry.registry_hash,
        "evidence": ordered,
        "missing_experiments": tuple(value.value for value in missing),
        "power_analysis": power_analysis,
        "status": status.value,
        "ready_for_m7": ready,
    }
    return M6ReadinessReport(
        M6_READINESS_ALGORITHM_VERSION,
        registry.registry_hash,
        ordered,
        missing,
        power_analysis,
        status,
        ready,
        sha256_json(payload),
    )


def verify_m6_readiness(
    report: M6ReadinessReport,
    registry: DevelopmentExperimentRegistry,
    evidence: tuple[M6ExperimentEvidence, ...],
    power_analysis: M6PowerAnalysisEvidence | None,
) -> None:
    if not isinstance(report, M6ReadinessReport):
        raise TypeError("report must be an M6ReadinessReport")
    expected = build_m6_readiness(registry, evidence, power_analysis)
    if report != expected:
        raise ValueError("M6 readiness report does not replay exactly from frozen inputs")
