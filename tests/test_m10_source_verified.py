from dataclasses import replace

import pytest

import fuckmark.experiments.m10_source_verified as m10_source_verified
from confirmatory_helpers import preregistration_inputs
from test_e20_source_verified_authorization import _raw_authorization
from test_m6_source_verified import _complete_inputs
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.e20_source_verified_authorization import (
    E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
    E20SourceVerifiedAuthorization,
)
from fuckmark.experiments.m10_release_v3 import (
    M10_RELEASE_ALGORITHM_VERSION,
    M10ReleaseManifest,
    M10ReleaseStatus,
)
from fuckmark.experiments.m10_source_verified import (
    M10_SOURCE_VERIFIED_ALGORITHM_VERSION,
    M10SourceVerifiedReleaseManifest,
    build_source_verified_m10_release_manifest,
    verify_source_verified_m10_release_manifest,
)
from fuckmark.experiments.m6_source_verified import build_source_verified_m6_readiness
from fuckmark.experiments.registry import default_development_experiment_registry
from fuckmark.hashing import sha256_json, sha256_text


def _fake_release(m6_readiness_hash: str, e20_authorization_hash: str) -> M10ReleaseManifest:
    digest = sha256_text("m10-source-verified-test")
    payload = {
        "algorithm_version": M10_RELEASE_ALGORITHM_VERSION,
        "release_code_commit": "a" * 40,
        "preregistration_hash": digest,
        "m6_readiness_hash": m6_readiness_hash,
        "detector_readiness_hash": digest,
        "test_key_manifest_hash": digest,
        "e20_corpus_manifest_hash": digest,
        "e20_authorization_hash": e20_authorization_hash,
        "e20_result_bundle_hash": digest,
        "e20_aggregate_hash": digest,
        "e20_inference_hash": digest,
        "e20_report_hash": digest,
        "e20_fidelity_summary_hash": digest,
        "e21_corpus_manifest_hash": digest,
        "e21_rerun_seal_hash": digest,
        "e21_authorization_hash": digest,
        "e21_result_bundle_hash": digest,
        "e21_analysis_hash": digest,
        "e21_inference_hash": digest,
        "e21_fidelity_summary_hash": digest,
        "e21_replication_hash": digest,
        "limitations": (),
        "status": M10ReleaseStatus.READY_COMPLETE.value,
    }
    return M10ReleaseManifest(
        M10_RELEASE_ALGORITHM_VERSION,
        "a" * 40,
        digest,
        m6_readiness_hash,
        digest,
        digest,
        digest,
        e20_authorization_hash,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        digest,
        (),
        M10ReleaseStatus.READY_COMPLETE,
        sha256_json(payload),
    )


def _e20_envelope(source_verified_m6, preregistration):
    raw = _raw_authorization(preregistration)
    payload = {
        "algorithm_version": E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        "preregistration_hash": preregistration.preregistration_hash,
        "m6_source_verified_bundle_hash": source_verified_m6.bundle_hash,
        "m6_readiness_hash": source_verified_m6.readiness.report_hash,
        "power_evidence_hash": source_verified_m6.power_evidence.evidence_hash,
        "authorization": raw,
    }
    return E20SourceVerifiedAuthorization(
        E20_SOURCE_VERIFIED_AUTHORIZATION_ALGORITHM_VERSION,
        preregistration.preregistration_hash,
        source_verified_m6.bundle_hash,
        source_verified_m6.readiness.report_hash,
        source_verified_m6.power_evidence.evidence_hash,
        raw,
        sha256_json(payload),
    )


def _fixture():
    registry = default_development_experiment_registry()
    experiments, power_input, power_result = _complete_inputs()
    source_verified_m6 = build_source_verified_m6_readiness(
        registry,
        experiments,
        power_input,
        power_result,
    )
    inputs = preregistration_inputs(final_n_per_core_cell=power_result.selected_sample_count)
    inputs = replace(inputs, power_analysis_hash=source_verified_m6.power_evidence.evidence_hash)
    preregistration = create_confirmatory_preregistration(inputs)
    e20_envelope = _e20_envelope(source_verified_m6, preregistration)
    return registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope


def test_source_verified_m10_binds_verified_m6_and_e20_before_release_manifest(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()

    monkeypatch.setattr(
        m10_source_verified,
        "_build_m10_release_manifest",
        lambda received_preregistration, received_m6, *args, **kwargs: _fake_release(
            received_m6.report_hash,
            e20_envelope.authorization.authorization_hash,
        ),
    )

    manifest = build_source_verified_m10_release_manifest(
        source_verified_m6,
        registry,
        experiments,
        power_input,
        power_result,
        preregistration,
        e20_envelope,
    )

    assert isinstance(manifest, M10SourceVerifiedReleaseManifest)
    assert manifest.algorithm_version == M10_SOURCE_VERIFIED_ALGORITHM_VERSION
    assert manifest.m6_source_verified_bundle_hash == source_verified_m6.bundle_hash
    assert manifest.m6_readiness_hash == source_verified_m6.readiness.report_hash
    assert manifest.e20_source_verified_authorization_hash == e20_envelope.envelope_hash
    assert manifest.e20_authorization_hash == e20_envelope.authorization.authorization_hash
    assert manifest.release_manifest.m6_readiness_hash == source_verified_m6.readiness.report_hash
    assert manifest.release_manifest.e20_authorization_hash == e20_envelope.authorization.authorization_hash
    verify_source_verified_m10_release_manifest(
        manifest,
        source_verified_m6,
        registry,
        experiments,
        power_input,
        power_result,
        preregistration,
        e20_envelope,
    )


def test_source_verified_m10_rejects_raw_structural_m6_report(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run"))
    with pytest.raises(TypeError, match="M6SourceVerifiedReadiness"):
        build_source_verified_m10_release_manifest(source_verified_m6.readiness, registry, experiments, power_input, power_result, preregistration, e20_envelope)


def test_source_verified_m10_rejects_raw_e20_authorization_before_release_builder(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run"))
    with pytest.raises(TypeError, match="E20SourceVerifiedAuthorization"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, preregistration, e20_envelope.authorization)


def test_source_verified_m10_replays_m6_sources_before_release_builder(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run after failed M6 replay"))
    mismatched_first = replace(experiments[0], rows=experiments[1].rows)
    with pytest.raises(ValueError):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, (mismatched_first, *experiments[1:]), power_input, power_result, preregistration, e20_envelope)


def test_source_verified_m10_rejects_e20_envelope_from_different_m6_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run after E20 chain failure"))
    forged = replace(
        e20_envelope,
        m6_source_verified_bundle_hash=sha256_text("different-source-verified-m6"),
        envelope_hash=sha256_json(
            {
                "algorithm_version": e20_envelope.algorithm_version,
                "preregistration_hash": e20_envelope.preregistration_hash,
                "m6_source_verified_bundle_hash": sha256_text("different-source-verified-m6"),
                "m6_readiness_hash": e20_envelope.m6_readiness_hash,
                "power_evidence_hash": e20_envelope.power_evidence_hash,
                "authorization": e20_envelope.authorization,
            }
        ),
    )
    with pytest.raises(ValueError, match="verified M6 bundle"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, preregistration, forged)


def test_source_verified_m10_rejects_preregistration_from_different_power_analysis(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run after power binding failure"))
    wrong_inputs = preregistration_inputs(final_n_per_core_cell=power_result.selected_sample_count)
    wrong_inputs = replace(wrong_inputs, power_analysis_hash=sha256_text("different-power-analysis"))
    wrong_preregistration = create_confirmatory_preregistration(wrong_inputs)
    with pytest.raises(ValueError, match="power analysis evidence"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, wrong_preregistration, e20_envelope)


def test_source_verified_m10_rejects_preregistered_final_n_not_selected_by_power(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(m10_source_verified, "_build_m10_release_manifest", lambda *args, **kwargs: pytest.fail("low-level M10 builder must not run after final N binding failure"))
    wrong_inputs = preregistration_inputs(final_n_per_core_cell=power_result.selected_sample_count + 1)
    wrong_inputs = replace(wrong_inputs, power_analysis_hash=source_verified_m6.power_evidence.evidence_hash)
    wrong_preregistration = create_confirmatory_preregistration(wrong_inputs)
    with pytest.raises(ValueError, match="final N"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, wrong_preregistration, e20_envelope)


def test_source_verified_m10_rejects_low_level_manifest_outside_verified_m6_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(
        m10_source_verified,
        "_build_m10_release_manifest",
        lambda *args, **kwargs: _fake_release(sha256_text("different-m6-readiness"), e20_envelope.authorization.authorization_hash),
    )
    with pytest.raises(ValueError, match="outside the source-verified M6 chain"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, preregistration, e20_envelope)


def test_source_verified_m10_rejects_low_level_manifest_outside_verified_e20_chain(monkeypatch) -> None:
    registry, experiments, power_input, power_result, source_verified_m6, preregistration, e20_envelope = _fixture()
    monkeypatch.setattr(
        m10_source_verified,
        "_build_m10_release_manifest",
        lambda *args, **kwargs: _fake_release(source_verified_m6.readiness.report_hash, sha256_text("different-e20-authorization")),
    )
    with pytest.raises(ValueError, match="outside the source-verified E20 authorization chain"):
        build_source_verified_m10_release_manifest(source_verified_m6, registry, experiments, power_input, power_result, preregistration, e20_envelope)
