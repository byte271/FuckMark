from dataclasses import replace
from pathlib import Path

import pytest

from confirmatory_helpers import calibration_materials, preregistration_inputs
from fuckmark.adapters import (
    DEEPMIND_REFERENCE_SOURCE_PIN,
    HUGGINGFACE_SYNTHID_SOURCE_PIN,
    DeepMindReferenceAdapter,
    DeepMindReferenceConfig,
)
from fuckmark.detectors import CalibrationScope, calibrate_detector
from fuckmark.detectors.bayesian import BayesianCheckpoint, load_bayesian_checkpoint
from fuckmark.detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from fuckmark.detectors.bayesian_calibration import bayesian_calibration_evidence
from fuckmark.detectors.bayesian_training import (
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
    BayesianValidationMetric,
    build_bayesian_confirmatory_readiness,
)
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_verification import (
    ConfirmatoryPreflightVerificationError,
    verify_confirmatory_preregistration,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.native_observations import build_native_observations


BAYESIAN_FIXTURE = Path(__file__).parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


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


def _trained_checkpoint() -> BayesianCheckpoint:
    source = load_bayesian_checkpoint(BAYESIAN_FIXTURE)
    payload = {
        "checkpoint_algorithm_version": source.checkpoint_algorithm_version,
        "source_id": source.source_id,
        "source_commit": source.source_commit,
        "watermarking_depth": source.watermarking_depth,
        "base_rate": source.base_rate,
        "beta": source.beta,
        "delta": source.delta,
        "fixture_kind": BAYESIAN_TRAINED_CHECKPOINT_KIND,
    }
    return BayesianCheckpoint(
        source.checkpoint_algorithm_version,
        source.source_id,
        source.source_commit,
        source.watermarking_depth,
        source.base_rate,
        source.beta,
        source.delta,
        BAYESIAN_TRAINED_CHECKPOINT_KIND,
        sha256_json(payload),
    )


def _bayesian_materials(model_tokenizer_hash: str):
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(11, 22, 33), context_history_size=8)
    )
    checkpoint = _trained_checkpoint()
    readiness_batch = build_native_observations(
        "bayesian-preflight-readiness",
        (1, 2, 3, 4, 5, 6, 7, 8),
        999,
        adapter,
    )
    provenance = BayesianTrainingProvenance.create(
        adapter_id=readiness_batch.adapter_id,
        adapter_config_hash=readiness_batch.adapter_config_hash,
        model_tokenizer_hash=model_tokenizer_hash,
        watermarking_depth=readiness_batch.depth,
        detector_train_prompt_families=("bayesian-train",),
        detector_validation_prompt_families=("bayesian-validation",),
        threshold_calibration_prompt_families=("bayesian-calibration",),
        attack_development_prompt_families=("bayesian-attack",),
        final_test_prompt_families=("bayesian-final",),
        train_dataset_hash=sha256_text("bayesian-preflight-train"),
        validation_dataset_hash=sha256_text("bayesian-preflight-validation"),
        init_seed=11,
        order_seed=22,
        epochs=250,
        learning_rate=0.001,
        minibatch_size=64,
        l2_weight=0.0,
        shuffle=True,
        validation_metric=BayesianValidationMetric.TPR_AT_FPR,
        validation_target_fpr=0.01,
        framework_id="jax-flax-optax",
        device="cpu",
        dtype="float32",
        training_history_hash=sha256_text("bayesian-preflight-history"),
        checkpoint_hash=checkpoint.checkpoint_hash,
        selected_epoch=17,
        selected_validation_value=-0.8,
    )
    sanity = BayesianSanityEvidence.create(
        provenance.provenance_hash,
        label_permutation_artifact_hash=sha256_text("bayesian-preflight-permutation"),
        label_permutation_near_chance_passed=True,
        zero_mask_artifact_hash=sha256_text("bayesian-preflight-zero-mask"),
        zero_mask_rejection_passed=True,
        shuffled_g_artifact_hash=sha256_text("bayesian-preflight-shuffled-g"),
        shuffled_g_signal_reduction_passed=True,
        calibration_artifact_hash=sha256_text("bayesian-preflight-calibration-check"),
        calibration_fpr_within_uncertainty_passed=True,
        leakage_audit_hash=sha256_text("bayesian-preflight-leakage"),
        leakage_audit_clean=True,
    )
    readiness = build_bayesian_confirmatory_readiness(
        readiness_batch,
        checkpoint,
        provenance,
        sanity,
        model_tokenizer_hash,
    )
    artifact = BayesianReadinessArtifactBundle.create(readiness, provenance, sanity, checkpoint)
    negatives = tuple(
        bayesian_calibration_evidence(
            build_native_observations(
                f"bayesian-preflight-negative-{index:03d}",
                tuple(value + index for value in (1, 2, 3, 4, 5, 6, 7, 8)),
                999,
                adapter,
            ),
            checkpoint,
            readiness,
        )
        for index in range(100)
    )
    scope = CalibrationScope.create(
        "bayesian-preflight-calibration",
        "negative-calibration",
        "confirmatory-length-stratified",
        "original-generation-token-ids",
        "continuation-only",
    )
    bundle = calibrate_detector(negatives, scope, target_fprs=(0.01,))
    return bundle, negatives, artifact


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


def test_bayesian_preregistration_requires_complete_readiness_artifact_replay() -> None:
    inputs = preregistration_inputs()
    bayesian_bundle, bayesian_negatives, artifact = _bayesian_materials(
        inputs.model_tokenizers[0].identity_hash
    )
    inputs = replace(
        inputs,
        calibration_bundles=inputs.calibration_bundles + (bayesian_bundle,),
    )
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    evidence_map = dict(evidence_map)
    evidence_map[bayesian_bundle.bundle_hash] = bayesian_negatives
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="requires complete readiness"):
        _verify(preregistration, inputs, evidence_map)
    _verify(
        preregistration,
        inputs,
        evidence_map,
        bayesian_readiness_artifacts={artifact.readiness.readiness_hash: artifact},
    )


def test_bayesian_preflight_rejects_artifact_map_key_drift() -> None:
    inputs = preregistration_inputs()
    bayesian_bundle, bayesian_negatives, artifact = _bayesian_materials(
        inputs.model_tokenizers[0].identity_hash
    )
    inputs = replace(
        inputs,
        calibration_bundles=inputs.calibration_bundles + (bayesian_bundle,),
    )
    preregistration = create_confirmatory_preregistration(inputs)
    _, evidence_map = calibration_materials()
    evidence_map = dict(evidence_map)
    evidence_map[bayesian_bundle.bundle_hash] = bayesian_negatives
    with pytest.raises(ConfirmatoryPreflightVerificationError, match="map key"):
        _verify(
            preregistration,
            inputs,
            evidence_map,
            bayesian_readiness_artifacts={sha256_text("wrong-readiness-key"): artifact},
        )
