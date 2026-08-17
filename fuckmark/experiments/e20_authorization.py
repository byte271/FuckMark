from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..environment import EnvironmentSnapshot
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal
from .confirmatory_corpus_tracks import verify_confirmatory_corpus_seal
from .confirmatory_detector_readiness import ConfirmatoryDetectorReadinessReport
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import (
    E20AuthorizationError,
    E20ExecutionAuthorization,
    E20RunLedger,
    E20VerificationError,
    authorize_e20_execution as _authorize_e20_execution_from_hash,
    verify_e20_execution_authorization as _verify_e20_execution_authorization_from_hash,
)
from .m6_readiness import M6ReadinessReport


def _verify_sealed_execution_inputs(
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    *,
    error_type,
) -> None:
    try:
        verify_e20_condition_plan(condition_plan, preregistration)
    except Exception as error:
        raise error_type(
            "E20 condition plan did not replay exactly from the sealed preregistration"
        ) from error
    try:
        verify_confirmatory_corpus_seal(
            corpus_seal,
            preregistration,
            corpus_manifest,
            test_key_manifest,
        )
    except Exception as error:
        raise error_type(
            "E20 corpus seal did not replay through the sealed watermark-track binding"
        ) from error


def _authorize_e20_execution_unchecked(
    preregistration: ConfirmatoryPreregistration,
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
    power_analysis_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
) -> E20ExecutionAuthorization:
    _verify_sealed_execution_inputs(
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        error_type=E20AuthorizationError,
    )
    return _authorize_e20_execution_from_hash(
        preregistration,
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
        power_analysis_hash=power_analysis_hash,
        budget_config_hash=condition_plan.plan_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
    )


def _verify_e20_execution_authorization_unchecked(
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
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
    code_commit: str,
    spec_revision_hash: str,
    power_analysis_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
) -> None:
    _verify_sealed_execution_inputs(
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        error_type=E20VerificationError,
    )
    _verify_e20_execution_authorization_from_hash(
        authorization,
        preregistration,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        environment,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        code_commit=code_commit,
        spec_revision_hash=spec_revision_hash,
        power_analysis_hash=power_analysis_hash,
        budget_config_hash=condition_plan.plan_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
    )


def authorize_e20_execution(
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    m6_readiness: M6ReadinessReport,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    output_namespace_available: bool,
    prior_ledgers: Sequence[E20RunLedger],
    code_commit: str,
    spec_revision_hash: str,
    power_analysis_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> E20ExecutionAuthorization:
    from .e20_readiness_gate import authorize_ready_e20_execution

    return authorize_ready_e20_execution(
        preregistration,
        m6_readiness,
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
        power_analysis_hash=power_analysis_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
        bayesian_readiness_artifacts=bayesian_readiness_artifacts,
    )


def verify_e20_execution_authorization(
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    m6_readiness: M6ReadinessReport,
    detector_readiness: ConfirmatoryDetectorReadinessReport,
    serialized_test_key_material: Mapping[str, bytes],
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    code_commit: str,
    spec_revision_hash: str,
    power_analysis_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> None:
    expected = authorize_e20_execution(
        preregistration,
        condition_plan,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        environment,
        m6_readiness=m6_readiness,
        detector_readiness=detector_readiness,
        serialized_test_key_material=serialized_test_key_material,
        dependency_lock_hash=dependency_lock_hash,
        worker_version=worker_version,
        shard_count=shard_count,
        dirty_worktree=False,
        output_namespace_available=True,
        prior_ledgers=(),
        code_commit=code_commit,
        spec_revision_hash=spec_revision_hash,
        power_analysis_hash=power_analysis_hash,
        verification_test_hashes=verification_test_hashes,
        model_tokenizers=model_tokenizers,
        calibration_negative_evidence=calibration_negative_evidence,
        task29_lexical_evidence=task29_lexical_evidence,
        task29_syntax_evidence=task29_syntax_evidence,
        task29_tokenizers=task29_tokenizers,
        bayesian_readiness_artifacts=bayesian_readiness_artifacts,
    )
    if authorization != expected:
        raise E20VerificationError(
            "E20 execution authorization does not replay exactly through the mandatory readiness gate"
        )
