from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..environment import EnvironmentSnapshot
from ..hashing import sha256_json
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal, verify_confirmatory_corpus_seal
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .confirmatory_verification import verify_confirmatory_preregistration
from .e20_execution import (
    E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
    E20_EXPERIMENT_ID,
    E20_SEED_DERIVATION_ALGORITHM_VERSION,
    E20AuthorizationError,
    E20ExecutionAuthorization,
    E20RunLedger,
    E20VerificationError,
    _execution_id,
    _verify_test_key_material,
    verify_e20_run_history,
)


def authorize_sealed_e20_execution(
    preregistration: ConfirmatoryPreregistration,
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
    budget_config_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> E20ExecutionAuthorization:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_seal, ConfirmatoryCorpusSeal):
        raise TypeError("corpus_seal must be a ConfirmatoryCorpusSeal")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(test_key_manifest, ConfirmatoryTestKeyManifest):
        raise TypeError("test_key_manifest must be a ConfirmatoryTestKeyManifest")
    if not isinstance(environment, EnvironmentSnapshot):
        raise TypeError("environment must be an EnvironmentSnapshot")
    require_sha256("dependency_lock_hash", dependency_lock_hash)
    require_clean_string("worker_version", worker_version)
    require_int("shard_count", shard_count)
    if shard_count <= 0 or shard_count > 4096:
        raise E20AuthorizationError("shard_count must be between 1 and 4096")
    require_bool("dirty_worktree", dirty_worktree)
    require_bool("output_namespace_available", output_namespace_available)
    if dirty_worktree:
        raise E20AuthorizationError("E20 authorization requires a clean worktree in the sealed runner")
    if not output_namespace_available:
        raise E20AuthorizationError("E20 output namespace already exists; patch-and-continue is forbidden")
    if code_commit != preregistration.code_commit:
        raise E20AuthorizationError("runtime code commit does not match the sealed preregistration")
    try:
        verify_confirmatory_preregistration(
            preregistration,
            code_commit=code_commit,
            spec_revision_hash=spec_revision_hash,
            power_analysis_hash=power_analysis_hash,
            budget_config_hash=budget_config_hash,
            verification_test_hashes=verification_test_hashes,
            model_tokenizers=model_tokenizers,
            calibration_negative_evidence=calibration_negative_evidence,
            sealed_test_key_hash=test_key_manifest.manifest_hash,
            sealed_test_corpus_hash=corpus_manifest.manifest_hash,
            task29_lexical_evidence=task29_lexical_evidence,
            task29_syntax_evidence=task29_syntax_evidence,
            task29_tokenizers=task29_tokenizers,
            bayesian_readiness_artifacts=bayesian_readiness_artifacts,
        )
    except Exception as error:
        raise E20AuthorizationError("confirmatory preregistration preflight did not replay exactly") from error
    try:
        verify_confirmatory_corpus_seal(corpus_seal, preregistration, corpus_manifest, test_key_manifest)
    except Exception as error:
        raise E20AuthorizationError("confirmatory corpus seal did not replay exactly") from error
    _verify_test_key_material(test_key_manifest, serialized_test_key_material)
    previous = tuple(prior_ledgers)
    verify_e20_run_history(previous)
    execution_id = _execution_id(preregistration.preregistration_hash, corpus_seal.seal_hash)
    if any(value.execution_id == execution_id for value in previous):
        raise E20AuthorizationError(
            "this sealed E20 execution_id already has a run ledger and cannot be authorized again"
        )
    output_namespace = f"e20/{execution_id}"
    payload = {
        "algorithm_version": E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        "experiment_id": E20_EXPERIMENT_ID,
        "execution_id": execution_id,
        "preregistration_hash": preregistration.preregistration_hash,
        "corpus_seal_hash": corpus_seal.seal_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "code_commit": code_commit,
        "environment_snapshot_hash": environment.snapshot_hash,
        "dependency_lock_hash": dependency_lock_hash,
        "worker_version": worker_version,
        "shard_count": shard_count,
        "output_namespace": output_namespace,
        "seed_derivation_version": E20_SEED_DERIVATION_ALGORITHM_VERSION,
    }
    return E20ExecutionAuthorization(
        E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        E20_EXPERIMENT_ID,
        execution_id,
        preregistration.preregistration_hash,
        corpus_seal.seal_hash,
        corpus_manifest.manifest_hash,
        test_key_manifest.manifest_hash,
        code_commit,
        environment.snapshot_hash,
        dependency_lock_hash,
        worker_version,
        shard_count,
        output_namespace,
        E20_SEED_DERIVATION_ALGORITHM_VERSION,
        sha256_json(payload),
    )


def verify_sealed_e20_execution_authorization(
    authorization: E20ExecutionAuthorization,
    preregistration: ConfirmatoryPreregistration,
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
    budget_config_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> None:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    expected = authorize_sealed_e20_execution(
        preregistration,
        corpus_seal,
        corpus_manifest,
        test_key_manifest,
        environment,
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
        budget_config_hash=budget_config_hash,
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
            "sealed E20 execution authorization does not replay exactly from source inputs"
        )
