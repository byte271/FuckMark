from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..environment import EnvironmentSnapshot
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal
from .confirmatory_detector_readiness import (
    ConfirmatoryDetectorReadinessReport,
    verify_confirmatory_detector_readiness,
)
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_authorization import authorize_e20_execution
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization, E20RunLedger


class E20ReadinessGateError(ValueError):
    pass


def authorize_ready_e20_execution(
    preregistration: ConfirmatoryPreregistration,
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
    power_analysis_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
) -> E20ExecutionAuthorization:
    if not isinstance(detector_readiness, ConfirmatoryDetectorReadinessReport):
        raise TypeError("detector_readiness must be a ConfirmatoryDetectorReadinessReport")
    verify_confirmatory_detector_readiness(detector_readiness, preregistration)
    if not detector_readiness.ready_for_e20:
        missing = ",".join(value.value for value in detector_readiness.global_missing_families)
        per_track = ";".join(
            f"{value.watermark_config_hash}:{','.join(family.value for family in value.missing_baseline_families)}"
            for value in detector_readiness.tracks
            if value.missing_baseline_families
        )
        raise E20ReadinessGateError(
            f"E20 detector readiness is incomplete: global_missing={missing}; per_track_missing={per_track}"
        )
    return authorize_e20_execution(
        preregistration,
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
    )
