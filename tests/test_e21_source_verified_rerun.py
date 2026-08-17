from dataclasses import replace

import pytest

import fuckmark.experiments.e21_source_verified_rerun as strict_e21
from confirmatory_helpers import preregistration_inputs
from test_e20_source_verified_authorization import _raw_authorization
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e20_source_verified_authorization import (
    E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
    E20SourceVerifiedAuthorization,
)
from fuckmark.experiments.e21_rerun import (
    E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
    E21_EXPERIMENT_ID,
    E21_RERUN_SEAL_ALGORITHM_VERSION,
    E21ExecutionAuthorization,
    E21RerunSeal,
)
from fuckmark.experiments.e21_source_verified_rerun import (
    E21SourceVerifiedAuthorization,
    E21SourceVerifiedRerunError,
    authorize_source_verified_e21_execution,
    build_source_verified_e21_rerun_seal,
)
from fuckmark.hashing import sha256_json, sha256_text


def _e20_envelope(preregistration, *, m6_suffix="a"):
    raw = _raw_authorization(preregistration)
    m6_bundle_hash = sha256_text(f"e21-source-verified-m6-bundle:{m6_suffix}")
    m6_readiness_hash = sha256_text(f"e21-source-verified-m6-readiness:{m6_suffix}")
    power_evidence_hash = sha256_text(f"e21-source-verified-power:{m6_suffix}")
    payload = {
        "algorithm_version": E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "m6_source_verified_bundle_hash": m6_bundle_hash,
        "m6_readiness_hash": m6_readiness_hash,
        "power_evidence_hash": power_evidence_hash,
        "authorization": raw,
    }
    return E20SourceVerifiedAuthorization(
        E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        m6_bundle_hash,
        m6_readiness_hash,
        power_evidence_hash,
        raw,
        sha256_json(payload),
    )


def _raw_rerun_seal(preregistration, e20_envelope):
    payload = {
        "algorithm_version": E21_RERUN_SEAL_ALGORITHM_VERSION,
        "experiment_id": E21_EXPERIMENT_ID,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_execution_id": e20_envelope.authorization.execution_id,
        "e20_authorization_hash": e20_envelope.authorization.authorization_hash,
        "e20_completed_ledger_hash": sha256_text("e21-source-verified-e20-ledger"),
        "e20_result_bundle_hash": sha256_text("e21-source-verified-e20-result"),
        "e20_corpus_manifest_hash": sha256_text("e21-source-verified-e20-corpus"),
        "e21_corpus_manifest_hash": sha256_text("e21-source-verified-e21-corpus"),
        "test_key_manifest_hash": sha256_text("e21-source-verified-test-keys"),
        "structure_hash": sha256_text("e21-source-verified-structure"),
        "e20_seed_set_hash": sha256_text("e21-source-verified-e20-seeds"),
        "e21_seed_set_hash": sha256_text("e21-source-verified-e21-seeds"),
    }
    return E21RerunSeal(
        E21_RERUN_SEAL_ALGORITHM_VERSION,
        E21_EXPERIMENT_ID,
        payload["preregistration_hash"],
        payload["e20_execution_id"],
        payload["e20_authorization_hash"],
        payload["e20_completed_ledger_hash"],
        payload["e20_result_bundle_hash"],
        payload["e20_corpus_manifest_hash"],
        payload["e21_corpus_manifest_hash"],
        payload["test_key_manifest_hash"],
        payload["structure_hash"],
        payload["e20_seed_set_hash"],
        payload["e21_seed_set_hash"],
        sha256_json(payload),
    )


def _raw_e21_authorization(preregistration, rerun_seal):
    execution_id = sha256_json(
        {"experiment_id": E21_EXPERIMENT_ID, "rerun_seal_hash": rerun_seal.seal_hash}
    )
    payload = {
        "algorithm_version": E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        "experiment_id": E21_EXPERIMENT_ID,
        "execution_id": execution_id,
        "rerun_seal_hash": rerun_seal.seal_hash,
        "preregistration_hash": preregistration.preregistration_hash,
        "e20_execution_id": rerun_seal.e20_execution_id,
        "e21_corpus_manifest_hash": rerun_seal.e21_corpus_manifest_hash,
        "test_key_manifest_hash": rerun_seal.test_key_manifest_hash,
        "code_commit": preregistration.code_commit,
        "environment_snapshot_hash": sha256_text("e21-source-verified-environment"),
        "dependency_lock_hash": sha256_text("e21-source-verified-lock"),
        "worker_version": "e21-source-verified-test-worker-v1",
        "shard_count": 1,
        "output_namespace": f"e21/{execution_id}",
    }
    return E21ExecutionAuthorization(
        E21_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        E21_EXPERIMENT_ID,
        execution_id,
        rerun_seal.seal_hash,
        preregistration.preregistration_hash,
        rerun_seal.e20_execution_id,
        rerun_seal.e21_corpus_manifest_hash,
        rerun_seal.test_key_manifest_hash,
        preregistration.code_commit,
        payload["environment_snapshot_hash"],
        payload["dependency_lock_hash"],
        payload["worker_version"],
        1,
        payload["output_namespace"],
        sha256_json(payload),
    )


def _fixture():
    preregistration = create_confirmatory_preregistration(preregistration_inputs())
    e20_envelope = _e20_envelope(preregistration)
    raw_seal = _raw_rerun_seal(preregistration, e20_envelope)
    raw_authorization = _raw_e21_authorization(preregistration, raw_seal)
    return preregistration, e20_envelope, raw_seal, raw_authorization


def test_source_verified_e21_persists_e20_provenance_through_rerun_and_authorization(monkeypatch) -> None:
    preregistration, e20_envelope, raw_seal, raw_authorization = _fixture()
    monkeypatch.setattr(strict_e21, "_build_e21_rerun_seal", lambda *args, **kwargs: raw_seal)
    source_seal = build_source_verified_e21_rerun_seal(
        preregistration,
        e20_envelope,
        object(),
        object(),
        object(),
        object(),
    )
    assert source_seal.e20_source_verified_authorization_hash == e20_envelope.envelope_hash
    assert source_seal.e20_authorization_hash == e20_envelope.authorization.authorization_hash
    assert source_seal.rerun_seal == raw_seal

    monkeypatch.setattr(strict_e21, "_authorize_e21_execution", lambda *args, **kwargs: raw_authorization)
    source_authorization = authorize_source_verified_e21_execution(
        source_seal,
        preregistration,
        e20_envelope,
        object(),
        object(),
        object(),
        object(),
        object(),
        serialized_test_key_material={},
        dependency_lock_hash=sha256_text("e21-source-verified-lock"),
        worker_version="e21-source-verified-test-worker-v1",
        shard_count=1,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    assert isinstance(source_authorization, E21SourceVerifiedAuthorization)
    assert source_authorization.e20_source_verified_authorization_hash == e20_envelope.envelope_hash
    assert source_authorization.source_verified_rerun_seal_hash == source_seal.envelope_hash
    assert source_authorization.rerun_seal_hash == raw_seal.seal_hash
    assert source_authorization.authorization == raw_authorization


def test_source_verified_e21_rejects_naked_raw_e20_authorization_before_rerun_builder(monkeypatch) -> None:
    preregistration, e20_envelope, _, _ = _fixture()
    monkeypatch.setattr(
        strict_e21,
        "_build_e21_rerun_seal",
        lambda *args, **kwargs: pytest.fail("raw E21 rerun builder must not run"),
    )
    with pytest.raises(TypeError, match="E20SourceVerifiedAuthorization"):
        build_source_verified_e21_rerun_seal(
            preregistration,
            e20_envelope.authorization,
            object(),
            object(),
            object(),
            object(),
        )


def test_source_verified_e21_rejects_e20_envelope_from_different_preregistration(monkeypatch) -> None:
    preregistration, _, _, _ = _fixture()
    other = create_confirmatory_preregistration(
        replace(preregistration_inputs(), code_commit="f" * 40)
    )
    other_e20 = _e20_envelope(other, m6_suffix="other")
    monkeypatch.setattr(
        strict_e21,
        "_build_e21_rerun_seal",
        lambda *args, **kwargs: pytest.fail("raw E21 rerun builder must not run"),
    )
    with pytest.raises(E21SourceVerifiedRerunError, match="does not bind the E21 preregistration"):
        build_source_verified_e21_rerun_seal(
            preregistration,
            other_e20,
            object(),
            object(),
            object(),
            object(),
        )


def test_source_verified_e21_authorization_rejects_naked_raw_rerun_seal(monkeypatch) -> None:
    preregistration, e20_envelope, raw_seal, _ = _fixture()
    monkeypatch.setattr(
        strict_e21,
        "_authorize_e21_execution",
        lambda *args, **kwargs: pytest.fail("raw E21 authorization must not run"),
    )
    with pytest.raises(TypeError, match="E21SourceVerifiedRerunSeal"):
        authorize_source_verified_e21_execution(
            raw_seal,
            preregistration,
            e20_envelope,
            object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("e21-source-verified-lock"),
            worker_version="e21-source-verified-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            code_commit=preregistration.code_commit,
        )


def test_source_verified_e21_authorization_rejects_rerun_envelope_from_different_e20_chain(monkeypatch) -> None:
    preregistration, e20_envelope, raw_seal, _ = _fixture()
    monkeypatch.setattr(strict_e21, "_build_e21_rerun_seal", lambda *args, **kwargs: raw_seal)
    source_seal = build_source_verified_e21_rerun_seal(
        preregistration,
        e20_envelope,
        object(), object(), object(), object(),
    )
    other_e20 = _e20_envelope(preregistration, m6_suffix="other")
    monkeypatch.setattr(
        strict_e21,
        "_authorize_e21_execution",
        lambda *args, **kwargs: pytest.fail("raw E21 authorization must not run"),
    )
    with pytest.raises(E21SourceVerifiedRerunError, match="different source-verified E20 authorization"):
        authorize_source_verified_e21_execution(
            source_seal,
            preregistration,
            other_e20,
            object(), object(), object(), object(), object(),
            serialized_test_key_material={},
            dependency_lock_hash=sha256_text("e21-source-verified-lock"),
            worker_version="e21-source-verified-test-worker-v1",
            shard_count=1,
            dirty_worktree=False,
            output_namespace_available=True,
            code_commit=preregistration.code_commit,
        )


def test_source_verified_e21_authorization_envelope_rejects_provenance_tamper(monkeypatch) -> None:
    preregistration, e20_envelope, raw_seal, raw_authorization = _fixture()
    monkeypatch.setattr(strict_e21, "_build_e21_rerun_seal", lambda *args, **kwargs: raw_seal)
    source_seal = build_source_verified_e21_rerun_seal(
        preregistration,
        e20_envelope,
        object(), object(), object(), object(),
    )
    monkeypatch.setattr(strict_e21, "_authorize_e21_execution", lambda *args, **kwargs: raw_authorization)
    source_authorization = authorize_source_verified_e21_execution(
        source_seal,
        preregistration,
        e20_envelope,
        object(), object(), object(), object(), object(),
        serialized_test_key_material={},
        dependency_lock_hash=sha256_text("e21-source-verified-lock"),
        worker_version="e21-source-verified-test-worker-v1",
        shard_count=1,
        dirty_worktree=False,
        output_namespace_available=True,
        code_commit=preregistration.code_commit,
    )
    with pytest.raises(ValueError, match="envelope_hash"):
        replace(
            source_authorization,
            e20_source_verified_authorization_hash=sha256_text("different-e20-source-envelope"),
        )
