from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..environment import EnvironmentSnapshot
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal
from .confirmatory_detector_readiness import (
    ConfirmatoryDetectorReadinessReport,
    verify_confirmatory_detector_readiness,
)
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import E20ExecutionAuthorization, E20RunLedger
from .e20_sealed_authorization import authorize_sealed_e20_execution
from .m6_readiness import M6ReadinessReport, verify_m6_readiness
from .registry import default_development_experiment_registry


class E20ReadinessGateError(ValueError):
    pass


def authorize_ready_e20_execution(
    preregistration: ConfirmatoryPreregistration,
    m6_readiness: M6ReadinessReport,
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
    bayesian_readiness_artifacts: Mapping[str, BayesianReadinessArtifactBundle] | None = None,
) -> E20ExecutionAuthorization:
    if not isinstance(m6_readiness, M6ReadinessReport):
        raise TypeError("m6_readiness must be an M6ReadinessReport")
    registry = default_development_experiment_registry()
    verify_m6_readiness(
        m6_readiness,
        registry,
        m6_readiness.evidence,
        m6_readiness.power_analysis,
    )
    if not m6_readiness.ready_for_m7:
        missing = ",".join(value.value for value in m6_readiness.missing_experiments)
        raise E20ReadinessGateError(
            f"M6 development readiness is incomplete: status={m6_readiness.status.value}; missing={missing}"
        )
    if m6_readiness.power_analysis is None:
        raise E20ReadinessGateError("M6 readiness cannot authorize E20 without power analysis evidence")
    if m6_readiness.power_analysis.evidence_hash != preregistration.power_analysis_hash:
        raise E20ReadinessGateError("M6 power analysis evidence does not match preregistration")
    if m6_readiness.power_analysis.final_n_per_core_cell != preregistration.final_n_per_core_cell:
        raise E20ReadinessGateError("M6 final N does not match preregistration")
    if power_analysis_hash != m6_readiness.power_analysis.evidence_hash:
        raise E20ReadinessGateError("authorization power analysis hash does not match M6 evidence")
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
    try:
        verify_e20_condition_plan(condition_plan, preregistration)
    except Exception as error:
        raise E20ReadinessGateError(
            "E20 condition plan did not replay exactly from the sealed preregistration"
        ) from error
    return authorize_sealed_e20_execution(
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
        bayesian_readiness_artifacts=bayesian_readiness_artifacts,
    )
