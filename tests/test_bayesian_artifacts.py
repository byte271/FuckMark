from pathlib import Path

import pytest

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors.bayesian import BayesianCheckpoint, load_bayesian_checkpoint
from fuckmark.detectors.bayesian_artifacts import (
    BayesianReadinessArtifactBundle,
    verify_bayesian_readiness_artifact_bundle,
)
from fuckmark.detectors.bayesian_training import (
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
    BayesianValidationMetric,
    build_bayesian_confirmatory_readiness,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.native_observations import build_native_observations


FIXTURE = Path(__file__).parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


def _batch():
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(11, 22, 33), context_history_size=8)
    )
    return build_native_observations(
        "bayesian-artifact-bundle-sample",
        (1, 2, 3, 4, 5, 6, 7, 8),
        999,
        adapter,
    )


def _checkpoint(trained: bool):
    source = load_bayesian_checkpoint(FIXTURE)
    if not trained:
        return source
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


def _chain(checkpoint):
    batch = _batch()
    model_hash = sha256_text("model-tokenizer")
    provenance = BayesianTrainingProvenance.create(
        adapter_id=batch.adapter_id,
        adapter_config_hash=batch.adapter_config_hash,
        model_tokenizer_hash=model_hash,
        watermarking_depth=batch.depth,
        detector_train_prompt_families=("train",),
        detector_validation_prompt_families=("validation",),
        threshold_calibration_prompt_families=("calibration",),
        attack_development_prompt_families=("attack",),
        final_test_prompt_families=("final",),
        train_dataset_hash=sha256_text("train-data"),
        validation_dataset_hash=sha256_text("validation-data"),
        init_seed=1,
        order_seed=2,
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
        training_history_hash=sha256_text("history"),
        checkpoint_hash=checkpoint.checkpoint_hash,
        selected_epoch=8,
        selected_validation_value=-0.7,
    )
    sanity = BayesianSanityEvidence.create(
        provenance.provenance_hash,
        label_permutation_artifact_hash=sha256_text("permutation"),
        label_permutation_near_chance_passed=True,
        zero_mask_artifact_hash=sha256_text("zero-mask"),
        zero_mask_rejection_passed=True,
        shuffled_g_artifact_hash=sha256_text("shuffled-g"),
        shuffled_g_signal_reduction_passed=True,
        calibration_artifact_hash=sha256_text("calibration-artifact"),
        calibration_fpr_within_uncertainty_passed=True,
        leakage_audit_hash=sha256_text("leakage"),
        leakage_audit_clean=True,
    )
    readiness = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        model_hash,
    )
    return readiness, provenance, sanity


def test_ready_artifact_bundle_replays_all_source_bound_hashes() -> None:
    checkpoint = _checkpoint(True)
    readiness, provenance, sanity = _chain(checkpoint)
    bundle = BayesianReadinessArtifactBundle.create(readiness, provenance, sanity, checkpoint)
    assert bundle.readiness.readiness_hash == readiness.readiness_hash
    assert bundle.provenance.provenance_hash == provenance.provenance_hash
    assert bundle.sanity.evidence_hash == sanity.evidence_hash
    assert bundle.checkpoint.checkpoint_hash == checkpoint.checkpoint_hash
    verify_bayesian_readiness_artifact_bundle(bundle)


def test_synthetic_checkpoint_cannot_enter_readiness_artifact_bundle() -> None:
    checkpoint = _checkpoint(False)
    readiness, provenance, sanity = _chain(checkpoint)
    assert readiness.ready is False
    with pytest.raises(ValueError, match="requires READY"):
        BayesianReadinessArtifactBundle.create(readiness, provenance, sanity, checkpoint)
