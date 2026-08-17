from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import KeySplit, TinyDevCorpusArtifact
from ..hashing import sha256_json
from .e08_dose import E08DoseResponseResult
from .extended_analysis import ExtendedAnalysisResult, ExtendedAnalysisRow, verify_extended_analysis_result
from .m6_readiness import (
    M6EvidencePartition,
    M6ExperimentEvidence,
    M6PowerAnalysisEvidence,
    M6ReadinessReport,
    M6ReadinessStatus,
    build_m6_readiness,
    verify_m6_readiness,
)
from .power_analysis import (
    PowerAnalysisInput,
    PowerAnalysisResult,
    m6_power_evidence_from_result,
    verify_power_analysis,
)
from .registry import DevelopmentExperimentId, DevelopmentExperimentRegistry
from .schedule_analysis import E09RandomBaselineResult, E10SpacingComparisonResult, E11GreedyComparisonResult
from .transform_analysis import DevelopmentTransformRow, E07PredictorComparisonResult
from .verification import verify_e07_result, verify_e08_result, verify_e09_result, verify_e10_result, verify_e11_result


M6_SOURCE_VERIFIED_ALGORITHM_VERSION = "m6-source-verified-readiness-v1"
_REQUIRED_EXPERIMENTS = tuple(DevelopmentExperimentId)[5:18]


DevelopmentResult = (
    E07PredictorComparisonResult
    | E08DoseResponseResult
    | E09RandomBaselineResult
    | E10SpacingComparisonResult
    | E11GreedyComparisonResult
    | ExtendedAnalysisResult
)
DevelopmentRows = tuple[DevelopmentTransformRow, ...] | tuple[ExtendedAnalysisRow, ...]


@dataclass(frozen=True, slots=True)
class M6ExperimentReplayInput:
    result: DevelopmentResult
    rows: DevelopmentRows
    tiny_dev_artifact: TinyDevCorpusArtifact | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.result,
            (
                E07PredictorComparisonResult,
                E08DoseResponseResult,
                E09RandomBaselineResult,
                E10SpacingComparisonResult,
                E11GreedyComparisonResult,
                ExtendedAnalysisResult,
            ),
        ):
            raise TypeError("result must be an E07 through E19 development result")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise TypeError("rows must be a non-empty tuple")
        if isinstance(self.result, ExtendedAnalysisResult):
            if any(not isinstance(value, ExtendedAnalysisRow) for value in self.rows):
                raise TypeError("E12 through E19 replay rows must contain ExtendedAnalysisRow values")
            if self.tiny_dev_artifact is not None:
                raise ValueError("E12 through E19 replay does not accept a tiny-dev artifact")
        else:
            if any(not isinstance(value, DevelopmentTransformRow) for value in self.rows):
                raise TypeError("E07 through E11 replay rows must contain DevelopmentTransformRow values")
            if not isinstance(self.tiny_dev_artifact, TinyDevCorpusArtifact):
                raise TypeError("E07 through E11 replay requires a TinyDevCorpusArtifact")


@dataclass(frozen=True, slots=True)
class M6SourceVerifiedExperimentEvidence:
    experiment_id: DevelopmentExperimentId
    definition_hash: str
    partition: M6EvidencePartition
    result_hash: str
    source_binding_hash: str
    readiness_evidence: M6ExperimentEvidence
    verified_hash: str

    def __post_init__(self) -> None:
        if self.experiment_id not in _REQUIRED_EXPERIMENTS:
            raise ValueError("source-verified M6 evidence must target E07 through E19")
        require_sha256("definition_hash", self.definition_hash)
        if not isinstance(self.partition, M6EvidencePartition):
            raise TypeError("partition must be an M6EvidencePartition")
        for name, value in (
            ("result_hash", self.result_hash),
            ("source_binding_hash", self.source_binding_hash),
            ("verified_hash", self.verified_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.readiness_evidence, M6ExperimentEvidence):
            raise TypeError("readiness_evidence must be an M6ExperimentEvidence")
        if (
            self.readiness_evidence.experiment_id is not self.experiment_id
            or self.readiness_evidence.definition_hash != self.definition_hash
            or self.readiness_evidence.partition is not self.partition
            or self.readiness_evidence.artifact_hash != self.result_hash
        ):
            raise ValueError("readiness_evidence does not bind the source-verified experiment result")
        if self.verified_hash != sha256_json(self._payload()):
            raise ValueError("verified_hash does not match source-verified M6 experiment evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": M6_SOURCE_VERIFIED_ALGORITHM_VERSION,
            "experiment_id": self.experiment_id.value,
            "definition_hash": self.definition_hash,
            "partition": self.partition.value,
            "result_hash": self.result_hash,
            "source_binding_hash": self.source_binding_hash,
            "readiness_evidence": self.readiness_evidence,
        }


@dataclass(frozen=True, slots=True)
class M6SourceVerifiedReadiness:
    algorithm_version: str
    registry_hash: str
    experiments: tuple[M6SourceVerifiedExperimentEvidence, ...]
    power_input_hash: str
    power_result_hash: str
    power_evidence: M6PowerAnalysisEvidence
    readiness: M6ReadinessReport
    bundle_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != M6_SOURCE_VERIFIED_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified M6 algorithm version")
        for name, value in (
            ("registry_hash", self.registry_hash),
            ("power_input_hash", self.power_input_hash),
            ("power_result_hash", self.power_result_hash),
            ("bundle_hash", self.bundle_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.experiments, tuple) or any(
            not isinstance(value, M6SourceVerifiedExperimentEvidence) for value in self.experiments
        ):
            raise TypeError("experiments must be a tuple of M6SourceVerifiedExperimentEvidence values")
        expected_ids = _REQUIRED_EXPERIMENTS
        if tuple(value.experiment_id for value in self.experiments) != expected_ids:
            raise ValueError("source-verified M6 must contain E07 through E19 exactly once in frozen order")
        if not isinstance(self.power_evidence, M6PowerAnalysisEvidence):
            raise TypeError("power_evidence must be an M6PowerAnalysisEvidence")
        if self.power_evidence.validation_input_hash != self.power_input_hash:
            raise ValueError("power evidence does not bind the verified power input")
        if self.power_evidence.analysis_artifact_hash != self.power_result_hash:
            raise ValueError("power evidence does not bind the verified power result")
        if not isinstance(self.readiness, M6ReadinessReport):
            raise TypeError("readiness must be an M6ReadinessReport")
        if self.readiness.registry_hash != self.registry_hash:
            raise ValueError("M6 readiness does not bind the verified registry")
        if self.readiness.status is not M6ReadinessStatus.READY or not self.readiness.ready_for_m7:
            raise ValueError("source-verified M6 bundle must be READY for M7")
        if self.readiness.evidence != tuple(value.readiness_evidence for value in self.experiments):
            raise ValueError("M6 readiness evidence does not match source-verified experiment evidence")
        if self.readiness.power_analysis != self.power_evidence:
            raise ValueError("M6 readiness power analysis does not match source-verified power evidence")
        if self.bundle_hash != sha256_json(self._payload()):
            raise ValueError("bundle_hash does not match source-verified M6 readiness")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "registry_hash": self.registry_hash,
            "experiments": self.experiments,
            "power_input_hash": self.power_input_hash,
            "power_result_hash": self.power_result_hash,
            "power_evidence": self.power_evidence,
            "readiness": self.readiness,
        }


def _experiment_id(result: DevelopmentResult) -> DevelopmentExperimentId:
    if isinstance(result, E07PredictorComparisonResult):
        return DevelopmentExperimentId.E07
    if isinstance(result, E08DoseResponseResult):
        return DevelopmentExperimentId.E08
    if isinstance(result, E09RandomBaselineResult):
        return DevelopmentExperimentId.E09
    if isinstance(result, E10SpacingComparisonResult):
        return DevelopmentExperimentId.E10
    if isinstance(result, E11GreedyComparisonResult):
        return DevelopmentExperimentId.E11
    if isinstance(result, ExtendedAnalysisResult):
        return result.experiment_id
    raise TypeError("unsupported development result type")


def _partition(rows: DevelopmentRows) -> M6EvidencePartition:
    key_splits = {value.key_split for value in rows}
    if KeySplit.TEST in key_splits:
        raise ValueError("source-verified M6 evidence cannot contain TEST_KEYS")
    if key_splits == {KeySplit.DEV}:
        return M6EvidencePartition.DEV
    if key_splits == {KeySplit.VALIDATION}:
        return M6EvidencePartition.VALIDATION
    raise ValueError("source-verified M6 experiment rows must use exactly one DEV or VALIDATION key partition")


def _source_binding(value: M6ExperimentReplayInput) -> str:
    artifact_hash = value.tiny_dev_artifact.artifact_hash if value.tiny_dev_artifact is not None else None
    return sha256_json(
        {
            "algorithm_version": M6_SOURCE_VERIFIED_ALGORITHM_VERSION,
            "experiment_id": _experiment_id(value.result).value,
            "tiny_dev_artifact_hash": artifact_hash,
            "row_hashes": tuple(sorted(row.row_hash for row in value.rows)),
        }
    )


def _verify_replay(value: M6ExperimentReplayInput) -> None:
    result = value.result
    if isinstance(result, E07PredictorComparisonResult):
        verify_e07_result(value.tiny_dev_artifact, value.rows, result)
        return
    if isinstance(result, E08DoseResponseResult):
        verify_e08_result(value.tiny_dev_artifact, value.rows, result)
        return
    if isinstance(result, E09RandomBaselineResult):
        verify_e09_result(value.tiny_dev_artifact, value.rows, result)
        return
    if isinstance(result, E10SpacingComparisonResult):
        verify_e10_result(value.tiny_dev_artifact, value.rows, result)
        return
    if isinstance(result, E11GreedyComparisonResult):
        verify_e11_result(value.tiny_dev_artifact, value.rows, result)
        return
    if isinstance(result, ExtendedAnalysisResult):
        verify_extended_analysis_result(result, value.rows)
        return
    raise TypeError("unsupported development result type")


def build_source_verified_experiment_evidence(
    registry: DevelopmentExperimentRegistry,
    value: M6ExperimentReplayInput,
) -> M6SourceVerifiedExperimentEvidence:
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(value, M6ExperimentReplayInput):
        raise TypeError("value must be an M6ExperimentReplayInput")
    _verify_replay(value)
    experiment_id = _experiment_id(value.result)
    if experiment_id not in _REQUIRED_EXPERIMENTS:
        raise ValueError("source-verified M6 evidence must target E07 through E19")
    definition = registry.get(experiment_id)
    if value.result.experiment_definition_hash != definition.definition_hash:
        raise ValueError("verified development result definition hash does not match the frozen registry")
    partition = _partition(value.rows)
    source_binding_hash = _source_binding(value)
    readiness_evidence = M6ExperimentEvidence.create(
        experiment_id,
        definition.definition_hash,
        partition,
        value.result.result_hash,
    )
    payload = {
        "algorithm_version": M6_SOURCE_VERIFIED_ALGORITHM_VERSION,
        "experiment_id": experiment_id.value,
        "definition_hash": definition.definition_hash,
        "partition": partition.value,
        "result_hash": value.result.result_hash,
        "source_binding_hash": source_binding_hash,
        "readiness_evidence": readiness_evidence,
    }
    return M6SourceVerifiedExperimentEvidence(
        experiment_id,
        definition.definition_hash,
        partition,
        value.result.result_hash,
        source_binding_hash,
        readiness_evidence,
        sha256_json(payload),
    )


def build_source_verified_m6_readiness(
    registry: DevelopmentExperimentRegistry,
    experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
) -> M6SourceVerifiedReadiness:
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(experiments, tuple):
        raise TypeError("experiments must be a tuple")
    if any(not isinstance(value, M6ExperimentReplayInput) for value in experiments):
        raise TypeError("experiments must contain M6ExperimentReplayInput values")
    by_id: dict[DevelopmentExperimentId, M6ExperimentReplayInput] = {}
    for value in experiments:
        experiment_id = _experiment_id(value.result)
        if experiment_id in by_id:
            raise ValueError("source-verified M6 experiment inputs must contain each experiment exactly once")
        by_id[experiment_id] = value
    if tuple(sorted(by_id, key=lambda value: value.value)) != _REQUIRED_EXPERIMENTS:
        missing = tuple(value.value for value in _REQUIRED_EXPERIMENTS if value not in by_id)
        extra = tuple(value.value for value in by_id if value not in _REQUIRED_EXPERIMENTS)
        raise ValueError(f"source-verified M6 requires complete E07-E19 evidence: missing={missing} extra={extra}")
    verified = tuple(build_source_verified_experiment_evidence(registry, by_id[value]) for value in _REQUIRED_EXPERIMENTS)
    if not isinstance(power_input, PowerAnalysisInput):
        raise TypeError("power_input must be a PowerAnalysisInput")
    if not isinstance(power_result, PowerAnalysisResult):
        raise TypeError("power_result must be a PowerAnalysisResult")
    verify_power_analysis(power_result, power_input)
    power_evidence = m6_power_evidence_from_result(power_result)
    readiness_evidence = tuple(value.readiness_evidence for value in verified)
    readiness = build_m6_readiness(registry, readiness_evidence, power_evidence)
    verify_m6_readiness(readiness, registry, readiness_evidence, power_evidence)
    if readiness.status is not M6ReadinessStatus.READY or not readiness.ready_for_m7:
        raise ValueError("source-verified M6 evidence did not reach READY after exact replay")
    payload = {
        "algorithm_version": M6_SOURCE_VERIFIED_ALGORITHM_VERSION,
        "registry_hash": registry.registry_hash,
        "experiments": verified,
        "power_input_hash": power_input.input_hash,
        "power_result_hash": power_result.result_hash,
        "power_evidence": power_evidence,
        "readiness": readiness,
    }
    return M6SourceVerifiedReadiness(
        M6_SOURCE_VERIFIED_ALGORITHM_VERSION,
        registry.registry_hash,
        verified,
        power_input.input_hash,
        power_result.result_hash,
        power_evidence,
        readiness,
        sha256_json(payload),
    )


def verify_source_verified_m6_readiness(
    bundle: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
) -> None:
    if not isinstance(bundle, M6SourceVerifiedReadiness):
        raise TypeError("bundle must be an M6SourceVerifiedReadiness")
    expected = build_source_verified_m6_readiness(registry, experiments, power_input, power_result)
    if bundle != expected:
        raise ValueError("source-verified M6 readiness does not replay exactly from development results and source evidence")
