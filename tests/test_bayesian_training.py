from pathlib import Path

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors.bayesian import BayesianCheckpoint, load_bayesian_checkpoint
from fuckmark.detectors.bayesian_training import (
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianConfirmatoryReadinessStatus,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
    BayesianValidationMetric,
    build_bayesian_confirmatory_readiness,
    verify_bayesian_confirmatory_readiness,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.native_observations import build_native_observations


FIXTURE = Path(__file__).parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


def _batch():
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )
    return build_native_observations(
        "bayesian-training-sample",
        (1, 2, 3, 4, 5, 6, 7, 8),
        999,
        adapter,
    )


def _trained_checkpoint() -> BayesianCheckpoint:
    source = load_bayesian_checkpoint(FIXTURE)
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


def _provenance(checkpoint: BayesianCheckpoint, *, adapter_config_hash: str | None = None):
    batch = _batch()
    return BayesianTrainingProvenance.create(
        adapter_id=batch.adapter_id,
        adapter_config_hash=batch.adapter_config_hash if adapter_config_hash is None else adapter_config_hash,
        model_tokenizer_hash=sha256_text("model-tokenizer-v1"),
        watermarking_depth=checkpoint.watermarking_depth,
        detector_train_prompt_families=("train-a", "train-b"),
        detector_validation_prompt_families=("detector-validation-a",),
        threshold_calibration_prompt_families=("threshold-calibration-a",),
        attack_development_prompt_families=("attack-development-a",),
        final_test_prompt_families=("final-test-a",),
        train_dataset_hash=sha256_text("bayesian-train-data"),
        validation_dataset_hash=sha256_text("bayesian-validation-data"),
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
        training_history_hash=sha256_text("training-history"),
        checkpoint_hash=checkpoint.checkpoint_hash,
        selected_epoch=17,
        selected_validation_value=-0.81,
    )


def _sanity(provenance: BayesianTrainingProvenance, *, shuffled_passed: bool = True):
    return BayesianSanityEvidence.create(
        provenance.provenance_hash,
        label_permutation_artifact_hash=sha256_text("label-permutation"),
        label_permutation_near_chance_passed=True,
        zero_mask_artifact_hash=sha256_text("zero-mask"),
        zero_mask_rejection_passed=True,
        shuffled_g_artifact_hash=sha256_text("shuffled-g"),
        shuffled_g_signal_reduction_passed=shuffled_passed,
        calibration_artifact_hash=sha256_text("calibration-fpr"),
        calibration_fpr_within_uncertainty_passed=True,
        leakage_audit_hash=sha256_text("leakage-audit"),
        leakage_audit_clean=True,
    )


def test_training_provenance_rejects_prompt_family_overlap() -> None:
    batch = _batch()
    checkpoint = _trained_checkpoint()
    with pytest.raises(ValueError, match="pairwise disjoint"):
        BayesianTrainingProvenance.create(
            adapter_id=batch.adapter_id,
            adapter_config_hash=batch.adapter_config_hash,
            model_tokenizer_hash=sha256_text("model-tokenizer-v1"),
            watermarking_depth=checkpoint.watermarking_depth,
            detector_train_prompt_families=("shared",),
            detector_validation_prompt_families=("shared",),
            threshold_calibration_prompt_families=("threshold",),
            attack_development_prompt_families=("attack",),
            final_test_prompt_families=("final",),
            train_dataset_hash=sha256_text("train"),
            validation_dataset_hash=sha256_text("validation"),
            init_seed=0,
            order_seed=0,
            epochs=1,
            learning_rate=0.001,
            minibatch_size=1,
            l2_weight=0.0,
            shuffle=True,
            validation_metric=BayesianValidationMetric.TPR_AT_FPR,
            validation_target_fpr=0.01,
            framework_id="jax-flax-optax",
            device="cpu",
            dtype="float32",
            training_history_hash=sha256_text("history"),
            checkpoint_hash=checkpoint.checkpoint_hash,
            selected_epoch=1,
            selected_validation_value=-0.5,
        )


def test_existing_synthetic_checkpoint_cannot_become_confirmatory_ready() -> None:
    batch = _batch()
    checkpoint = load_bayesian_checkpoint(FIXTURE)
    provenance = _provenance(checkpoint)
    sanity = _sanity(provenance)
    readiness = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        provenance.model_tokenizer_hash,
    )
    assert readiness.status is BayesianConfirmatoryReadinessStatus.BLOCKED
    assert readiness.ready is False
    assert any("not marked as a trained" in value for value in readiness.blocking_reasons)


def test_failed_sanity_check_blocks_confirmatory_readiness() -> None:
    batch = _batch()
    checkpoint = _trained_checkpoint()
    provenance = _provenance(checkpoint)
    sanity = _sanity(provenance, shuffled_passed=False)
    readiness = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        provenance.model_tokenizer_hash,
    )
    assert readiness.status is BayesianConfirmatoryReadinessStatus.BLOCKED
    assert "one or more Bayesian sanity checks failed" in readiness.blocking_reasons


def test_config_or_model_mismatch_blocks_confirmatory_readiness() -> None:
    batch = _batch()
    checkpoint = _trained_checkpoint()
    provenance = _provenance(checkpoint, adapter_config_hash=sha256_text("wrong-config"))
    sanity = _sanity(provenance)
    readiness = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        sha256_text("wrong-model-tokenizer"),
    )
    assert readiness.status is BayesianConfirmatoryReadinessStatus.BLOCKED
    assert any("adapter configuration" in value for value in readiness.blocking_reasons)
    assert any("model/tokenizer" in value for value in readiness.blocking_reasons)


def test_source_bound_trained_evidence_chain_can_reach_metadata_readiness() -> None:
    batch = _batch()
    checkpoint = _trained_checkpoint()
    provenance = _provenance(checkpoint)
    sanity = _sanity(provenance)
    readiness = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        provenance.model_tokenizer_hash,
    )
    assert readiness.status is BayesianConfirmatoryReadinessStatus.READY
    assert readiness.ready is True
    assert readiness.blocking_reasons == ()
    verify_bayesian_confirmatory_readiness(
        readiness,
        batch,
        checkpoint,
        provenance,
        sanity,
        provenance.model_tokenizer_hash,
    )


def test_cross_entropy_selection_rejects_target_fpr() -> None:
    batch = _batch()
    checkpoint = _trained_checkpoint()
    with pytest.raises(ValueError, match="must not carry"):
        BayesianTrainingProvenance.create(
            adapter_id=batch.adapter_id,
            adapter_config_hash=batch.adapter_config_hash,
            model_tokenizer_hash=sha256_text("model-tokenizer-v1"),
            watermarking_depth=checkpoint.watermarking_depth,
            detector_train_prompt_families=("train",),
            detector_validation_prompt_families=("validation",),
            threshold_calibration_prompt_families=("calibration",),
            attack_development_prompt_families=("attack",),
            final_test_prompt_families=("final",),
            train_dataset_hash=sha256_text("train-data"),
            validation_dataset_hash=sha256_text("validation-data"),
            init_seed=0,
            order_seed=0,
            epochs=10,
            learning_rate=0.001,
            minibatch_size=64,
            l2_weight=0.0,
            shuffle=True,
            validation_metric=BayesianValidationMetric.CROSS_ENTROPY,
            validation_target_fpr=0.01,
            framework_id="jax-flax-optax",
            device="cpu",
            dtype="float32",
            training_history_hash=sha256_text("history"),
            checkpoint_hash=checkpoint.checkpoint_hash,
            selected_epoch=1,
            selected_validation_value=0.4,
        )
