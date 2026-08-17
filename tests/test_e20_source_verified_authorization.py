from dataclasses import replace

import pytest

import fuckmark.experiments.e20_source_verified_authorization as strict_e20
from confirmatory_helpers import preregistration_inputs
from test_m6_source_verified import _complete_inputs
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e20_execution import (
    E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
    E20_EXPERIMENT_ID,
    E20_SEED_DERIVATION_ALGORITHM_VERSION,
    E20ExecutionAuthorization,
    _execution_id,
)
from fuckmark.experiments.e20_source_verified_authorization import (
    E20SourceVerifiedAuthorization,
    E20SourceVerifiedAuthorizationError,
    authorize_source_verified_e20_execution,
)
from fuckmark.experiments.m6_source_verified import build_source_verified_m6_readiness
from fuckmark.experiments.registry import default_development_experiment_registry
from fuckmark.hashing import sha256_json, sha256_text


def _fixture():
    registry = default_development_experiment_registry()
    experiments, power_input, power_result = _complete_inputs()
    source_verified_m6 = build_source_verified_m6_readiness(
        registry,
        experiments,
        power_input,
        power_result,
    )
    inputs = preregistration_inputs(final_n_per_core_cell=source_verified_m6.power_evidence.final_n_per_core_cell)
    inputs = replace(inputs, power_analysis_hash=source_verified_m6.power_evidence.evidence_hash)
    preregistration = create_confirmatory_preregistration(inputs)
    return registry, experiments, power_input, power_result, source_verified_m6, preregistration


def _raw_authorization(preregistration):
    corpus_seal_hash = sha256_text("strict-e20-corpus-seal")
    execution_id = _execution_id(preregistration.preregistration_hash, corpus_seal_hash)
    payload = {
        "algorithm_version": E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        "experiment_id": E20_EXPERIMENT_ID,
        "execution_id": execution_id,
        "preregistration_hash": preregistration.preregistration_hash,
        "corpus_seal_hash": corpus_seal_hash,
        "corpus_manifest_hash": sha256_text("strict-e20-corpus-manifest"),
        "test_key_manifest_hash": sha256_text("strict-e20-test-key-manifest"),
        "code_commit": preregistration.code_commit,
        "environment_snapshot_hash": sha256_text("strict-e20-environment"),
        "dependency_lock_hash": sha256_text("strict-e20-lock"),
        "worker_version": "strict-e20-test-worker-v1",
        "shard_count": 1,
        "output_namespace": f"e20/{execution_id}",
        "seed_derivation_version": E20_SEED_DERIVATION_ALGORITHM_VERSION,
    }
    return E20ExecutionAuthorization(
        E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        E20_EXPERIMENT_ID,
        execution_id,
        preregistration.preregistration_hash,
        corpus_seal_hash,
        payload["corpus_manifest_hash"],
        payload["test_key_manifest_hash"],
        preregistration.code_commit,
        payload["environment_snapshot_hash"],
        payload["dependency_lock_hash"],
        payload["worker_version"],
        payload["shard_count"],
        payload["output_namespace"],
        E20_SEED_DERIVATION_ALGORITHM_VERSION,
        sha256_json(payload),
    )


def _authorize(monkeypatch, *, source_verified_m6=None, experiments=None, preregistration=None):
    registry, fixture_experiments, power_input, power_result, fixture_m6, fixture_preregistration = _fixture()
    selected_m6 = fixture_m6 if source_verified_m6 is None else source_verified_m6
    selected_experiments = fixture_experiments if experiments is None else experiments
    selected_preregistration = fixture_preregistration if preregistration is None else preregistration
    captured = {}
    raw = _raw_authorization(selected_preregistration)

    def fake_authorize(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return raw

    monkeypatch.setattr(strict_e20, "_authorize_ready_e20_execution", fake_authorize)
    result = authorize_source_verified_e20_execution(
        selected_preregistration,
        selected_m6,
        registry,
        selected_experiments,
        power_input,
        power_result,
        object(),
        object(),
        object(),
        object(),
        object(),
        object(),
        serialized_test_key_material={},
        dependency_lock_hash=sha256_text("strict-e20-lock"),
        worker_version="strict-e20-test-worker-v1",
        shard_count=1,
        dirty_worktree=False,
        output_namespace_available=True,
        prior_ledgers=(),
        code_commit=selected_preregistration.code_commit,
        spec_revision_hash=selected_preregistration.spec_revision_hash,
        verification_test_hashes=selected_preregistration.verification_test_hashes,
        model_tokenizers=selected_preregistration.model_tokenizers,
        calibration_negative_evidence={},
    )
    return result, raw, captured, fixture_m6


def test_source_verified_e20_replays_m6_before_delegating_and_preserves_provenance(monkeypatch) -> None:
    envelope, raw, captured, source_verified_m6 = _authorize(monkeypatch)
    assert isinstance(envelope, E20SourceVerifiedAuthorization)
    assert envelope.authorization == raw
    assert envelope.m6_source_verified_bundle_hash == source_verified_m6.bundle_hash
    assert envelope.m6_readiness_hash == source_verified_m6.readiness.report_hash
    assert envelope.power_evidence_hash == source_verified_m6.power_evidence.evidence_hash
    assert captured["args"][1] == source_verified_m6.readiness
    assert captured["kwargs"]["power_analysis_hash"] == source_verified_m6.power_evidence.evidence_hash


def test_source_verified_e20_envelope_rejects_provenance_substitution(monkeypatch) -> None:
    envelope, _, _, _ = _authorize(monkeypatch)
    with pytest.raises(ValueError, match="envelope_hash"):
        replace(envelope, m6_source_verified_bundle_hash=sha256_text("different-m6-bundle"))
    with pytest.raises(ValueError, match="source-verified preregistration"):
        replace(envelope, authorization=_raw_authorization(create_confirmatory_preregistration(preregistration_inputs())))


def test_source_verified_e20_rejects_raw_structural_m6_report_before_delegate(monkeypatch) -> None:
    _, _, _, _, source_verified_m6, _ = _fixture()
    monkeypatch.setattr(
        strict_e20,
        "_authorize_ready_e20_execution",
        lambda *args, **kwargs: pytest.fail("existing readiness gate must not run"),
    )
    registry, experiments, power_input, power_result, _, preregistration = _fixture()
    with pytest.raises(TypeError, match="M6SourceVerifiedReadiness"):
        authorize_source_verified_e20_execution(
            preregistration,
            source_verified_m6.readiness,
            registry,
            experiments,
            power_input,
            power_result,
            object(), object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("strict-e20-lock"),
            worker_version="strict-e20-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            prior_ledgers=(),
            code_commit=preregistration.code_commit,
            spec_revision_hash=preregistration.spec_revision_hash,
            verification_test_hashes=preregistration.verification_test_hashes,
            model_tokenizers=preregistration.model_tokenizers,
            calibration_negative_evidence={},
        )


def test_source_verified_e20_rejects_mismatched_source_rows_before_delegate(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration = _fixture()
    mismatched_first = replace(experiments[0], rows=experiments[1].rows)
    monkeypatch.setattr(
        strict_e20,
        "_authorize_ready_e20_execution",
        lambda *args, **kwargs: pytest.fail("existing readiness gate must not run after M6 replay failure"),
    )
    with pytest.raises(ValueError):
        authorize_source_verified_e20_execution(
            preregistration,
            source_verified_m6,
            registry,
            (mismatched_first, *experiments[1:]),
            power_input,
            power_result,
            object(), object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("strict-e20-lock"),
            worker_version="strict-e20-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            prior_ledgers=(),
            code_commit=preregistration.code_commit,
            spec_revision_hash=preregistration.spec_revision_hash,
            verification_test_hashes=preregistration.verification_test_hashes,
            model_tokenizers=preregistration.model_tokenizers,
            calibration_negative_evidence={},
        )


def test_source_verified_e20_rejects_preregistration_power_evidence_mismatch(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, _ = _fixture()
    wrong_inputs = preregistration_inputs(final_n_per_core_cell=source_verified_m6.power_evidence.final_n_per_core_cell)
    wrong_inputs = replace(wrong_inputs, power_analysis_hash=sha256_text("different-power-evidence"))
    wrong_preregistration = create_confirmatory_preregistration(wrong_inputs)
    monkeypatch.setattr(
        strict_e20,
        "_authorize_ready_e20_execution",
        lambda *args, **kwargs: pytest.fail("existing readiness gate must not run after power binding failure"),
    )
    with pytest.raises(E20SourceVerifiedAuthorizationError, match="power analysis evidence"):
        authorize_source_verified_e20_execution(
            wrong_preregistration,
            source_verified_m6,
            registry,
            experiments,
            power_input,
            power_result,
            object(), object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("strict-e20-lock"),
            worker_version="strict-e20-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            prior_ledgers=(),
            code_commit=wrong_preregistration.code_commit,
            spec_revision_hash=wrong_preregistration.spec_revision_hash,
            verification_test_hashes=wrong_preregistration.verification_test_hashes,
            model_tokenizers=wrong_preregistration.model_tokenizers,
            calibration_negative_evidence={},
        )


def test_source_verified_e20_rejects_preregistered_final_n_not_selected_by_power(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, _ = _fixture()
    wrong_inputs = preregistration_inputs(final_n_per_core_cell=source_verified_m6.power_evidence.final_n_per_core_cell + 1)
    wrong_inputs = replace(wrong_inputs, power_analysis_hash=source_verified_m6.power_evidence.evidence_hash)
    wrong_preregistration = create_confirmatory_preregistration(wrong_inputs)
    monkeypatch.setattr(
        strict_e20,
        "_authorize_ready_e20_execution",
        lambda *args, **kwargs: pytest.fail("existing readiness gate must not run after final N binding failure"),
    )
    with pytest.raises(E20SourceVerifiedAuthorizationError, match="final N"):
        authorize_source_verified_e20_execution(
            wrong_preregistration,
            source_verified_m6,
            registry,
            experiments,
            power_input,
            power_result,
            object(), object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("strict-e20-lock"),
            worker_version="strict-e20-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            prior_ledgers=(),
            code_commit=wrong_preregistration.code_commit,
            spec_revision_hash=wrong_preregistration.spec_revision_hash,
            verification_test_hashes=wrong_preregistration.verification_test_hashes,
            model_tokenizers=wrong_preregistration.model_tokenizers,
            calibration_negative_evidence={},
        )
