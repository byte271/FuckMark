import pytest

from confirmatory_helpers import calibration_materials, preregistration_inputs
from fuckmark.adapters import DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_verification import (
    ConfirmatoryPreflightVerificationError,
    verify_confirmatory_preregistration,
)
from fuckmark.hashing import sha256_text


def _verify(preregistration, inputs, evidence_map, **overrides):
    arguments = {
        "code_commit": inputs.code_commit,
        "spec_revision_hash": inputs.spec_revision_hash,
        "power_analysis_hash": inputs.power_analysis_hash,
        "budget_config_hash": inputs.budget_config_hash,
        "verification_test_hashes": preregistration.verification_test_hashes,
        "model_tokenizers": inputs.model_tokenizers,
        "calibration_negative_evidence": evidence_map,
        "sealed_test_key_hash": inputs.sealed_test_key_hash,
        "sealed_test_corpus_hash": inputs.sealed_test_corpus_hash,
    }
    arguments.update(overrides)
    verify_confirmatory_preregistration(preregistration, **arguments)


def test_confirmatory_preflight_replays_frozen_sources_calibration_and_task29_gate() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    _verify(preregistration, inputs, evidence_map)
    assert preregistration.source_pins == tuple(
        sorted(
            (DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN),
            key=lambda value: (value.source_id, value.repository, value.commit),
        )
    )


def test_confirmatory_preflight_rejects_code_or_spec_drift() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="code commit"):
        _verify(preregistration, inputs, evidence_map, code_commit="e" * 40)
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="spec revision"):
        _verify(
            preregistration,
            inputs,
            evidence_map,
            spec_revision_hash=sha256_text("different-spec"),
        )


def test_confirmatory_preflight_requires_exact_runtime_model_identities() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="model/tokenizer"):
        _verify(
            preregistration,
            inputs,
            evidence_map,
            model_tokenizers=(inputs.model_tokenizers[0],),
        )


def test_confirmatory_preflight_requires_exact_calibration_replay() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    keys = tuple(evidence_map)
    swapped = {
        keys[0]: evidence_map[keys[1]],
        keys[1]: evidence_map[keys[0]],
    }
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="does not replay"):
        _verify(preregistration, inputs, swapped)


def test_confirmatory_preflight_requires_exact_bundle_coverage_and_test_hashes() -> None:
    inputs = preregistration_inputs()
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    first_key = next(iter(evidence_map))
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="exactly cover"):
        _verify(preregistration, inputs, {first_key: evidence_map[first_key]})
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="verification test hashes"):
        _verify(
            preregistration,
            inputs,
            evidence_map,
            verification_test_hashes=(sha256_text("different-tests"),),
        )
