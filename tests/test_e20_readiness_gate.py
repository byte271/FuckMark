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
from fuckmark.hashing import sha256_text


def test_real_e20_authorization_is_blocked_before_execution_when_required_detectors_are_missing() -> None:
    inputs = preregistration_inputs(final_n_per_core_cell=1)
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
    readiness = build_confirmatory_detector_readiness(preregistration)
    _, calibration_evidence = calibration_materials()
    secrets = {
        "test-key-0": b"secret-test-key-0",
        "test-key-1": b"secret-test-key-1",
    }
    with pytest.raises(E20ReadinessGateError, match="global_missing"):
        authorize_ready_e20_execution(
            preregistration,
            readiness,
            condition_plan,
            seal,
            corpus,
            keys,
            capture_environment(),
            serialized_test_key_material={
                entry.entry_hash: secrets[entry.key_id] for entry in keys.entries
            },
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
