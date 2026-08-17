from pathlib import Path

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors.bayesian import BayesianCheckpoint, load_bayesian_checkpoint
from fuckmark.detectors.bayesian_training import (
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
    BayesianValidationMetric,
    build_bayesian_confirmatory_readiness,
)
from fuckmark.detectors.compatibility import evaluate_detector_compatibility
from fuckmark.detectors.types import CompatibilityStatus, DetectorFamily
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
        "bayesian-compatibility-sample",
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


def _ready_chain():
    batch = _batch()
    checkpoint = _trained_checkpoint()
    model_tokenizer_hash = sha256_text("model-tokenizer-v1")
    provenance = BayesianTrainingProvenance.create(
        adapter_id=batch.adapter_id,
        adapter_config_hash=batch.adapter_config_hash,
        model_tokenizer_hash=model_tokenizer_hash,
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
        selected_epoch=10,
        selected_validation_value=-0.8,
    )
    sanity = BayesianSanityEvidence.create(
        provenance.provenance_hash,
        label_permutation_artifact_hash=sha256_text("permutation"),
        label_permutation_near_chance_passed=True,
        zero_mask_artifact_hash=sha256_text("zero-mask"),
        zero_mask_rejection_passed=True,
        shuffled_g_artifact_hash=sha256_text("shuffle"),
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
        model_tokenizer_hash,
    )
    return batch, readiness


def test_bayesian_compatibility_remains_unverified_without_readiness() -> None:
    batch = _batch()
    compatibility = evaluate_detector_compatibility(batch, DetectorFamily.BAYESIAN)
    assert compatibility.status is CompatibilityStatus.UNVERIFIED
    assert compatibility.validated_by == ()


def test_ready_bayesian_evidence_promotes_only_the_matching_observation_configuration() -> None:
    batch, readiness = _ready_chain()
    compatibility = evaluate_detector_compatibility(
        batch,
        DetectorFamily.BAYESIAN,
        bayesian_readiness=readiness,
    )
    assert compatibility.status is CompatibilityStatus.SUPPORTED
    assert compatibility.validated_by == (readiness.readiness_hash,)


def test_bayesian_readiness_cannot_be_passed_to_mean_detector() -> None:
    batch, readiness = _ready_chain()
    try:
        evaluate_detector_compatibility(
            batch,
            DetectorFamily.MEAN,
            bayesian_readiness=readiness,
        )
    except ValueError as error:
        assert "Bayesian detector family" in str(error)
    else:
        raise AssertionError("Mean compatibility accepted Bayesian readiness evidence")
