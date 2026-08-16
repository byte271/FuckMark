from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..environment import EnvironmentSnapshot
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    authorize_e20_execution as _authorize_e20_execution_from_hash,
    verify_e20_execution_authorization as _verify_e20_execution_authorization_from_hash,
)


def authorize_e20_execution(
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
    verify_e20_condition_plan(condition_plan, preregistration)
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


def verify_e20_execution_authorization(
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
    verify_e20_condition_plan(condition_plan, preregistration)
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
