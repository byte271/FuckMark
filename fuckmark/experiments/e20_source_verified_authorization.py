from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .._validation import require_sha256
from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..environment import EnvironmentSnapshot
from ..hashing import sha256_json
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal
from .confirmatory_detector_readiness import ConfirmatoryDetectorReadinessReport
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization, E20RunLedger
from .e20_readiness_gate import authorize_ready_e20_execution as _authorize_ready_e20_execution
from .m6_source_verified import (
    M6ExperimentReplayInput,
    M6SourceVerifiedReadiness,
    verify_source_verified_m6_readiness,
)
from .power_analysis import PowerAnalysisInput, PowerAnalysisResult
from .registry import DevelopmentExperimentRegistry


E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION = "e20-source-verified-authorization-v1"


class E20SourceVerifiedAuthorizationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E20SourceVerifiedAuthorization:
    algorithm_version: str
    preregistration_hash: str
    m6_source_verified_bundle_hash: str
    m6_readiness_hash: str
    power_evidence_hash: str
    authorization: E20ExecutionAuthorization
    envelope_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION:
            raise ValueError("unsupported source-verified E20 authorization algorithm version")
        for name, value in (
            ("preregistration_hash", self.preregistration_hash),
            ("m6_source_verified_bundle_hash", self.m6_source_verified_bundle_hash),
            ("m6_readiness_hash", self.m6_readiness_hash),
            ("power_evidence_hash", self.power_evidence_hash),
            ("envelope_hash", self.envelope_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.authorization, E20ExecutionAuthorization):
            raise TypeError("authorization must be an E20ExecutionAuthorization")
        if self.authorization.preregistration_hash != self.preregistration_hash:
            raise ValueError("raw E20 authorization does not bind the source-verified preregistration")
        if self.envelope_hash != sha256_json(self._payload()):
            raise ValueError("envelope_hash does not match source-verified E20 authorization")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "preregistration_hash": self.preregistration_hash,
            "m6_source_verified_bundle_hash": self.m6_source_verified_bundle_hash,
            "m6_readiness_hash": self.m6_readiness_hash,
            "power_evidence_hash": self.power_evidence_hash,
            "authorization": self.authorization,
        }


def _verify_source_verified_m6_binding(
    preregistration: ConfirmatoryPreregistration,
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
) -> None:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(source_verified_m6, M6SourceVerifiedReadiness):
        raise TypeError("source_verified_m6 must be an M6SourceVerifiedReadiness")
    if not isinstance(registry, DevelopmentExperimentRegistry):
        raise TypeError("registry must be a DevelopmentExperimentRegistry")
    if not isinstance(m6_experiments, tuple):
        raise TypeError("m6_experiments must be a tuple")
    if any(not isinstance(value, M6ExperimentReplayInput) for value in m6_experiments):
        raise TypeError("m6_experiments must contain M6ExperimentReplayInput values")
    if not isinstance(power_input, PowerAnalysisInput):
        raise TypeError("power_input must be a PowerAnalysisInput")
    if not isinstance(power_result, PowerAnalysisResult):
        raise TypeError("power_result must be a PowerAnalysisResult")

    verify_source_verified_m6_readiness(
        source_verified_m6,
        registry,
        m6_experiments,
        power_input,
        power_result,
    )
    if preregistration.power_analysis_hash != source_verified_m6.power_evidence.evidence_hash:
        raise E20SourceVerifiedAuthorizationError(
            "confirmatory preregistration does not bind the source-verified power analysis evidence"
        )
    if preregistration.final_n_per_core_cell != source_verified_m6.power_evidence.final_n_per_core_cell:
        raise E20SourceVerifiedAuthorizationError(
            "confirmatory preregistration final N does not match source-verified power analysis"
        )


def authorize_source_verified_e20_execution(
    preregistration: ConfirmatoryPreregistration,
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    condition_plan: E20ConditionPlan,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    output_namespace_available: bool,
    prior_ledgers: Sequence[E20RunLedger],
    code_commit: str,
    spec_revision_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> E20SourceVerifiedAuthorization:
    _verify_source_verified_m6_binding(
        preregistration,
        source_verified_m6,
        registry,
        m6_experiments,
        power_input,
        power_result,
    )
    raw_authorization = _authorize_ready_e20_execution(
        preregistration,
        source_verified_m6.readiness,
        detector_readiness,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        environment,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        dirty_worktree=dirty_worktree,
        output_namespace_available=output_namespace_available,
        prior_ledgers=prior_ledgers,
        code_commit=code_commit,
        spec_revision_hash=spec_revision_hash,
        power_analysis_hash=source_verified_m6.power_evidence.evidence_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
        bayesian_readiness_artifacts=bayesian_readiness_artifacts,
    )
    if not isinstance(raw_authorization, E20ExecutionAuthorization):
        raise TypeError("existing E20 readiness gate must return an E20ExecutionAuthorization")
    payload = {
        "algorithm_version": E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "m6_source_verified_bundle_hash": source_verified_m6.bundle_hash,
        "m6_readiness_hash": source_verified_m6.readiness.report_hash,
        "power_evidence_hash": source_verified_m6.power_evidence.evidence_hash,
        "authorization": raw_authorization,
    }
    return E20SourceVerifiedAuthorization(
        E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        source_verified_m6.bundle_hash,
        source_verified_m6.readiness.report_hash,
        source_verified_m6.power_evidence.evidence_hash,
        raw_authorization,
        sha256_json(payload),
    )


def verify_source_verified_e20_execution_authorization(
    envelope: E20SourceVerifiedAuthorization,
    preregistration: ConfirmatoryPreregistration,
    source_verified_m6: M6SourceVerifiedReadiness,
    registry: DevelopmentExperimentRegistry,
    m6_experiments: tuple[M6ExperimentReplayInput, ...],
    power_input: PowerAnalysisInput,
    power_result: PowerAnalysisResult,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    condition_plan: E20ConditionPlan,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    output_namespace_available: bool,
    prior_ledgers: Sequence[E20RunLedger],
    code_commit: str,
    spec_revision_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> None:
    if not isinstance(envelope, E20SourceVerifiedAuthorization):
        raise TypeError("envelope must be an E20SourceVerifiedAuthorization")
    expected = authorize_source_verified_e20_execution(
        preregistration,
        source_verified_m6,
        registry,
        m6_experiments,
        power_input,
        power_result,
        detector_readiness,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        environment,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        dirty_worktree=dirty_worktree,
        output_namespace_available=output_namespace_available,
        prior_ledgers=prior_ledgers,
        code_commit=code_commit,
        spec_revision_hash=spec_revision_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
        bayesian_readiness_artifacts=bayesian_readiness_artifacts,
    )
    if envelope != expected:
        raise E20SourceVerifiedAuthorizationError(
            "E20 source-verified authorization envelope does not replay exactly"
        )
