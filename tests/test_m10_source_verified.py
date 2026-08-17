from dataclasses import replace
from functools import lru_cache

import pytest

import fuckmark.experiments.m10_source_verified as m10_source_verified
from confirmatory_helpers import preregistration_inputs
from test_e20_source_verified_authorization import _raw_authorization
from test_e21_source_verified_rerun import _raw_e21_authorization, _raw_rerun_seal
from test_m6_source_verified import _complete_inputs
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e20_source_verified_authorization import E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION, E20SourceVerifiedAuthorization
from fuckmark.experiments.e21_source_verified_rerun import (
    E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
    E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION,
    E21SourceVerifiedAuthorization,
    E21SourceVerifiedRerunSeal,
)
from fuckmark.experiments.m10_release_v3 import M10_RELEASE_ALGORITHM_VERSION, M10ReleaseManifest, M10ReleaseStatus
from fuckmark.experiments.m10_source_verified import M10_SOURCE_VERIFIED_ALGORITHM_VERSION, M10SourceVerifiedReleaseManifest, build_source_verified_m10_release_manifest, verify_source_verified_m10_release_manifest
from fuckmark.experiments.m6_source_verified import build_source_verified_m6_readiness
from fuckmark.experiments.registry import default_development_experiment_registry
from fuckmark.hashing import sha256_json, sha256_text


def _fake_release(m6_hash, e20_hash, e21_seal_hash, e21_auth_hash):
    digest = sha256_text("m10-source-verified-test")
    payload = {"algorithm_version": M10_RELEASE_ALGORITHM_VERSION, "release_code_commit": "a" * 40, "preregistration_hash": digest, "m6_readiness_hash": m6_hash, "detector_readiness_hash": digest, "test_key_manifest_hash": digest, "e20_corpus_manifest_hash": digest, "e20_authorization_hash": e20_hash, "e20_result_bundle_hash": digest, "e20_aggregate_hash": digest, "e20_inference_hash": digest, "e20_report_hash": digest, "e20_fidelity_summary_hash": digest, "e21_corpus_manifest_hash": digest, "e21_rerun_seal_hash": e21_seal_hash, "e21_authorization_hash": e21_auth_hash, "e21_result_bundle_hash": digest, "e21_analysis_hash": digest, "e21_inference_hash": digest, "e21_fidelity_summary_hash": digest, "e21_replication_hash": digest, "limitations": (), "status": M10ReleaseStatus.READY_COMPLETE.value}
    return M10ReleaseManifest(M10_RELEASE_ALGORITHM_VERSION, "a" * 40, digest, m6_hash, digest, digest, digest, e20_hash, digest, digest, digest, digest, digest, digest, e21_seal_hash, e21_auth_hash, digest, digest, digest, digest, digest, (), M10ReleaseStatus.READY_COMPLETE, sha256_json(payload))


def _e20_envelope(m6, preregistration):
    raw = _raw_authorization(preregistration)
    payload = {"algorithm_version": E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION, "preregistration_hash": preregistration.preregistration_hash, "m6_source_verified_bundle_hash": m6.bundle_hash, "m6_readiness_hash": m6.readiness.report_hash, "power_evidence_hash": m6.power_evidence.evidence_hash, "authorization": raw}
    return E20SourceVerifiedAuthorization(E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION, preregistration.preregistration_hash, m6.bundle_hash, m6.readiness.report_hash, m6.power_evidence.evidence_hash, raw, sha256_json(payload))


def _e21_chain(preregistration, e20):
    raw_seal = _raw_rerun_seal(preregistration, e20)
    seal_payload = {"algorithm_version": E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION, "preregistration_hash": preregistration.preregistration_hash, "e20_source_verified_authorization_hash": e20.envelope_hash, "e20_authorization_hash": e20.authorization.authorization_hash, "rerun_seal": raw_seal}
    seal = E21SourceVerifiedRerunSeal(E21_SOURCE_VERIFIED_RERUN_ALGORITHM_VERSION, preregistration.preregistration_hash, e20.envelope_hash, e20.authorization.authorization_hash, raw_seal, sha256_json(seal_payload))
    raw_auth = _raw_e21_authorization(preregistration, raw_seal)
    auth_payload = {"algorithm_version": E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION, "preregistration_hash": preregistration.preregistration_hash, "e20_source_verified_authorization_hash": e20.envelope_hash, "source_verified_rerun_seal_hash": seal.envelope_hash, "rerun_seal_hash": raw_seal.seal_hash, "authorization": raw_auth}
    auth = E21SourceVerifiedAuthorization(E21_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION, preregistration.preregistration_hash, e20.envelope_hash, seal.envelope_hash, raw_seal.seal_hash, raw_auth, sha256_json(auth_payload))
    return seal, auth


@lru_cache(maxsize=1)
def _fixture():
    registry = default_development_experiment_registry()
    experiments, power_input, power_result = _complete_inputs()
    m6 = build_source_verified_m6_readiness(registry, experiments, power_input, power_result)
    inputs = replace(preregistration_inputs(final_n_per_core_cell=power_result.selected_sample_count), power_analysis_hash=m6.power_evidence.evidence_hash)
    preregistration = create_confirmatory_preregistration(inputs)
    e20 = _e20_envelope(m6, preregistration)
    e21_seal, e21_auth = _e21_chain(preregistration, e20)
    return registry, experiments, power_input, power_result, m6, preregistration, e20, e21_seal, e21_auth


def _args():
    return _fixture()


def test_source_verified_m10_binds_complete_m6_e20_e21_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: _fake_release(m6.readiness.report_hash, e20.authorization.authorization_hash, e21_seal.rerun_seal.seal_hash, e21_auth.authorization.authorization_hash))
    manifest = build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, e21_auth)
    assert isinstance(manifest, M10SourceVerifiedReleaseManifest)
    assert manifest.algorithm_version == M10_SOURCE_VERIFIED_ALGORITHM_VERSION
    assert manifest.e20_source_verified_authorization_hash == e20.envelope_hash
    assert manifest.e21_source_verified_rerun_seal_hash == e21_seal.envelope_hash
    assert manifest.e21_source_verified_authorization_hash == e21_auth.envelope_hash
    verify_source_verified_m10_release_manifest(manifest, m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, e21_auth)


def test_source_verified_m10_rejects_naked_raw_e21_artifacts_before_release_builder(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run"))
    with pytest.raises(TypeError, match="E21SourceVerifiedRerunSeal"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal.rerun_seal, e21_auth)
    with pytest.raises(TypeError, match="E21SourceVerifiedAuthorization"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, e21_auth.authorization)


def test_source_verified_m10_rejects_e21_chain_from_different_e20_envelope(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run"))
    forged_e20 = replace(e20, m6_source_verified_bundle_hash=sha256_text("different-m6"), envelope_hash=sha256_json({"algorithm_version": e20.algorithm_version, "preregistration_hash": e20.preregistration_hash, "m6_source_verified_bundle_hash": sha256_text("different-m6"), "m6_readiness_hash": e20.m6_readiness_hash, "power_evidence_hash": e20.power_evidence_hash, "authorization": e20.authorization}))
    with pytest.raises(ValueError, match="verified M6 bundle"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, forged_e20, e21_seal, e21_auth)


def test_source_verified_m10_rejects_e21_authorization_from_different_rerun_envelope(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run"))
    forged_hash = sha256_text("different-source-verified-rerun")
    forged = replace(e21_auth, source_verified_rerun_seal_hash=forged_hash, envelope_hash=sha256_json({"algorithm_version": e21_auth.algorithm_version, "preregistration_hash": e21_auth.preregistration_hash, "e20_source_verified_authorization_hash": e21_auth.e20_source_verified_authorization_hash, "source_verified_rerun_seal_hash": forged_hash, "rerun_seal_hash": e21_auth.rerun_seal_hash, "authorization": e21_auth.authorization}))
    with pytest.raises(ValueError, match="verified rerun envelope"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, forged)


def test_source_verified_m10_rejects_low_level_manifest_outside_verified_e21_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: _fake_release(m6.readiness.report_hash, e20.authorization.authorization_hash, sha256_text("different-e21-seal"), e21_auth.authorization.authorization_hash))
    with pytest.raises(ValueError, match="outside the source-verified E21 rerun chain"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, e21_auth)


def test_source_verified_m10_rejects_low_level_manifest_outside_verified_e21_authorization_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, m6, prereg, e20, e21_seal, e21_auth = _args()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: _fake_release(m6.readiness.report_hash, e20.authorization.authorization_hash, e21_seal.rerun_seal.seal_hash, sha256_text("different-e21-authorization")))
    with pytest.raises(ValueError, match="outside the source-verified E21 authorization chain"):
        build_source_verified_m10_release_manifest(m6, registry, experiments, power_input, power_result, prereg, e20, e21_seal, e21_auth)
