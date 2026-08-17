from pathlib import Path

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.detectors.bayesian import BayesianCheckpoint, load_bayesian_checkpoint
from fuckmark.detectors.bayesian_calibration import (
    bayesian_calibration_evidence,
    verify_bayesian_calibration_evidence,
)
from fuckmark.detectors.bayesian_training import (
    BAYESIAN_TRAINED_CHECKPOINT_KIND,
    BayesianSanityEvidence,
    BayesianTrainingProvenance,
    BayesianValidationMetric,
    build_bayesian_confirmatory_readiness,
)
from fuckmark.detectors.calibration import calibrate_detector
from fuckmark.detectors.calibration_types import CalibrationScope, ComparisonOperator
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.native_observations import build_native_observations


FIXTURE = Path(__file__).parent / "fixtures" / "bayesian" / "deepmind-small-v1.json"


def _adapter():
    return DeepMindReferenceAdapter(
        DeepMindReferenceConfig(
            ngram_len=3,
            keys=(11, 22, 33),
            context_history_size=8,
        )
    )


def _batch(sample_id: str, offset: int = 0):
    return build_native_observations(
        sample_id,
        tuple(value + offset for value in (1, 2, 3, 4, 5, 6, 7, 8)),
        999,
        _adapter(),
    )


def _trained_checkpoint(base_rate: float = 0.35) -> BayesianCheckpoint:
    source = load_bayesian_checkpoint(FIXTURE)
    payload = {
        "checkpoint_algorithm_version": source.checkpoint_algorithm_version,
        "source_id": source.source_id,
        "source_commit": source.source_commit,
        "watermarking_depth": source.watermarking_depth,
        "base_rate": base_rate,
        "beta": source.beta,
        "delta": source.delta,
        "fixture_kind": BAYESIAN_TRAINED_CHECKPOINT_KIND,
    }
    return BayesianCheckpoint(
        source.checkpoint_algorithm_version,
        source.source_id,
        source.source_commit,
        source.watermarking_depth,
        base_rate,
        source.beta,
        source.delta,
        BAYESIAN_TRAINED_CHECKPOINT_KIND,
        sha256_json(payload),
    )


def _readiness(checkpoint: BayesianCheckpoint):
    batch = _batch("readiness-source")
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
        train_dataset_hash=sha256_text(f"train-{checkpoint.checkpoint_hash}"),
        validation_dataset_hash=sha256_text(f"validation-{checkpoint.checkpoint_hash}"),
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
        training_history_hash=sha256_text(f"history-{checkpoint.checkpoint_hash}"),
        checkpoint_hash=checkpoint.checkpoint_hash,
        selected_epoch=10,
        selected_validation_value=-0.8,
    )
    sanity = BayesianSanityEvidence.create(
        provenance.provenance_hash,
        label_permutation_artifact_hash=sha256_text(f"permutation-{checkpoint.checkpoint_hash}"),
        label_permutation_near_chance_passed=True,
        zero_mask_artifact_hash=sha256_text(f"zero-mask-{checkpoint.checkpoint_hash}"),
        zero_mask_rejection_passed=True,
        shuffled_g_artifact_hash=sha256_text(f"shuffle-{checkpoint.checkpoint_hash}"),
        shuffled_g_signal_reduction_passed=True,
        calibration_artifact_hash=sha256_text(f"calibration-{checkpoint.checkpoint_hash}"),
        calibration_fpr_within_uncertainty_passed=True,
        leakage_audit_hash=sha256_text(f"leakage-{checkpoint.checkpoint_hash}"),
        leakage_audit_clean=True,
    )
    return build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        model_tokenizer_hash,
    )


def test_bayesian_calibration_evidence_binds_checkpoint_and_readiness_hashes() -> None:
    checkpoint = _trained_checkpoint()
    readiness = _readiness(checkpoint)
    batch = _batch("bayesian-calibration-one")
    evidence = bayesian_calibration_evidence(batch, checkpoint, readiness)
    assert checkpoint.checkpoint_hash in evidence.detector_artifact_hashes
    assert readiness.readiness_hash in evidence.detector_artifact_hashes
    assert readiness.training_provenance_hash in evidence.detector_artifact_hashes
    assert readiness.sanity_evidence_hash in evidence.detector_artifact_hashes
    verify_bayesian_calibration_evidence(evidence, batch, checkpoint, readiness)


def test_different_bayesian_checkpoints_have_different_calibration_identities() -> None:
    first_checkpoint = _trained_checkpoint(0.35)
    second_checkpoint = _trained_checkpoint(0.45)
    batch = _batch("bayesian-calibration-identity")
    first = bayesian_calibration_evidence(batch, first_checkpoint, _readiness(first_checkpoint))
    second = bayesian_calibration_evidence(batch, second_checkpoint, _readiness(second_checkpoint))
    assert first.detector_config_hash != second.detector_config_hash
    assert first.detector_artifact_hashes != second.detector_artifact_hashes


def test_bayesian_evidence_can_use_existing_fixed_fpr_calibration_pipeline() -> None:
    checkpoint = _trained_checkpoint()
    readiness = _readiness(checkpoint)
    negatives = tuple(
        bayesian_calibration_evidence(
            _batch(f"negative-{index:03d}", offset=index),
            checkpoint,
            readiness,
        )
        for index in range(100)
    )
    scope = CalibrationScope.create(
        "bayesian-negative-corpus",
        "matched-unwatermarked",
        "frozen-length-policy",
        "deepmind-reference",
        "generated-only",
    )
    bundle = calibrate_detector(
        negatives,
        scope,
        target_fprs=(0.01,),
        comparison_operator=ComparisonOperator.GREATER_THAN,
    )
    assert bundle.detector_identity.detector_artifact_hashes == negatives[0].detector_artifact_hashes
    assert bundle.detector_identity.detector_config_hash == negatives[0].detector_config_hash
    assert bundle.thresholds[0].target_fpr == 0.01
