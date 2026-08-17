from dataclasses import replace

import pytest

from confirmatory_helpers import (
    calibration_materials,
    confirmatory_condition_plan,
    confirmatory_manifest,
    confirmatory_test_key_manifest,
    preregistration_inputs,
)
from fuckmark.environment import capture_environment
from fuckmark.experiments import build_confirmatory_corpus_seal
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_detector_readiness import build_confirmatory_detector_readiness
from fuckmark.experiments.e20_readiness_gate import (
    E20ReadinessGateError,
    authorize_ready_e20_execution,
)
from fuckmark.experiments.m6_readiness import (
    M6EvidencePartition,
    M6ExperimentEvidence,
    M6PowerAnalysisEvidence,
    build_m6_readiness,
)
from fuckmark.experiments.registry import DevelopmentExperimentId, default_development_experiment_registry
from fuckmark.hashing import sha256_text


def _m6_readiness(final_n_per_core_cell: int):
    registry = default_development_experiment_registry()
    evidence = tuple(
        M6ExperimentEvidence.create(
            experiment_id,
            registry.get(experiment_id).definition_hash,
            M6EvidencePartition.VALIDATION,
            sha256_text(f"m6-evidence-{experiment_id.value}"),
        )
        for experiment_id in tuple(DevelopmentExperimentId)[5:]
    )
    power = M6PowerAnalysisEvidence.create(
        "group-stratified-power-analysis-v1",
        sha256_text("m6-validation-inputs"),
        sha256_text("m6-power-analysis-artifact"),
        final_n_per_core_cell,
    )
    return build_m6_readiness(registry, evidence, power)


def _authorization_fixture():
    m6 = _m6_readiness(1)
    inputs = replace(
        preregistration_inputs(final_n_per_core_cell=1),
        power_analysis_hash=m6.power_analysis.evidence_hash,
    )
    condition_plan = confirmatory_condition_plan(calibration_bundles=inputs.calibration_bundles)
    corpus = confirmatory_manifest(inputs)
    keys = confirmatory_test_key_manifest(inputs)
    inputs = replace(
        inputs,
        sealed_test_key_hash=keys.manifest_hash,
        sealed_test_corpus_hash=corpus.manifest_hash,
    )
    preregistration = create_confirmatory_preregistration(inputs)
    seal = build_confirmatory_corpus_seal(preregistration, corpus, keys)
    detector_readiness = build_confirmatory_detector_readiness(preregistration)
    _, calibration_evidence = calibration_materials()
    secrets = {
        "test-key-0": b"secret-test-key-0",
        "test-key-1": b"secret-test-key-1",
    }
    serialized = {entry.entry_hash: secrets[entry.key_id] for entry in keys.entries}
    return (
        m6,
        preregistration,
        detector_readiness,
        condition_plan,
        seal,
        corpus,
        keys,
        serialized,
        calibration_evidence,
    )


def _authorize(fixture, m6_override=None):
    (
        m6,
        preregistration,
        detector_readiness,
        condition_plan,
        seal,
        corpus,
        keys,
        serialized,
        calibration_evidence,
    ) = fixture
    return authorize_ready_e20_execution(
        preregistration,
        m6 if m6_override is None else m6_override,
        detector_readiness,
        condition_plan,
        seal,
        corpus,
        keys,
        capture_environment(),
        serialized_test_key_material=serialized,
        dependency_lock_hash=sha256_text("readiness-gate-lock"),
        worker_version="e20-readiness-gate-test-v1",
        shard_count=2,
        dirty_worktree=False,
        output_namespace_available=True,
        prior_ledgers=(),
        code_commit=preregistration.code_commit,
        spec_revision_hash=preregistration.spec_revision_hash,
        power_analysis_hash=preregistration.power_analysis_hash,
        verification_test_hashes=preregistration.verification_test_hashes,
        model_tokenizers=preregistration.model_tokenizers,
        calibration_negative_evidence=calibration_evidence,
    )


def test_real_e20_authorization_is_blocked_when_m6_is_incomplete() -> None:
    fixture = _authorization_fixture()
    registry = default_development_experiment_registry()
    blocked = build_m6_readiness(registry, (), None)
    with pytest.raises(E20ReadinessGateError, match="M6 development readiness"):
        _authorize(fixture, blocked)


def test_real_e20_authorization_is_blocked_before_execution_when_required_detectors_are_missing() -> None:
    fixture = _authorization_fixture()
    with pytest.raises(E20ReadinessGateError, match="global_missing"):
        _authorize(fixture)


def test_real_e20_authorization_rejects_power_analysis_not_bound_to_preregistration() -> None:
    fixture = _authorization_fixture()
    m6 = fixture[0]
    replacement_power = M6PowerAnalysisEvidence.create(
        "group-stratified-power-analysis-v1",
        sha256_text("different-validation-inputs"),
        sha256_text("different-power-analysis-artifact"),
        1,
    )
    registry = default_development_experiment_registry()
    mismatched = build_m6_readiness(registry, m6.evidence, replacement_power)
    with pytest.raises(E20ReadinessGateError, match="does not match preregistration"):
        _authorize(fixture, mismatched)
