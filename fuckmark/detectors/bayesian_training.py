from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN
from ..hashing import sha256_json
from ..native_observations import NativeObservationBatch
from .bayesian import BayesianCheckpoint


BAYESIAN_TRAINING_PROVENANCE_VERSION = "deepmind-bayesian-training-provenance-v1"
BAYESIAN_SANITY_EVIDENCE_VERSION = "deepmind-bayesian-sanity-evidence-v1"
BAYESIAN_CONFIRMATORY_READINESS_VERSION = "deepmind-bayesian-confirmatory-readiness-v1"
BAYESIAN_SOURCE_PATH = "src/synthid_text/detector_bayesian.py"
BAYESIAN_REQUIRED_WATERMARK_MODE = "tournament"
BAYESIAN_REQUIRED_G_DISTRIBUTION = "bernoulli-0.5"
BAYESIAN_TRAINED_CHECKPOINT_KIND = "trained-source-compatible"
BAYESIAN_OPTIMIZER_ID = "optax.adam"
BAYESIAN_LR_SCHEDULE_ID = "constant"


class BayesianValidationMetric(str, Enum):
    TPR_AT_FPR = "TPR_AT_FPR"
    CROSS_ENTROPY = "CROSS_ENTROPY"


class BayesianConfirmatoryReadinessStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


def _positive_float(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _nonnegative_float(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _finite_float(name: str, value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _prompt_family_partition(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{name} must be a non-empty tuple")
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be unique and canonically ordered")
    for value in values:
        require_clean_string(f"{name} value", value)
    return values


@dataclass(frozen=True, slots=True)
class BayesianTrainingProvenance:
    algorithm_version: str
    source_id: str
    source_commit: str
    source_path: str
    adapter_id: str
    adapter_config_hash: str
    model_tokenizer_hash: str
    watermarking_depth: int
    watermark_mode: str
    g_distribution: str
    detector_train_prompt_families: tuple[str, ...]
    detector_validation_prompt_families: tuple[str, ...]
    threshold_calibration_prompt_families: tuple[str, ...]
    attack_development_prompt_families: tuple[str, ...]
    final_test_prompt_families: tuple[str, ...]
    train_dataset_hash: str
    validation_dataset_hash: str
    init_seed: int
    order_seed: int
    epochs: int
    learning_rate: float
    minibatch_size: int
    l2_weight: float
    shuffle: bool
    optimizer_id: str
    lr_schedule_id: str
    validation_metric: BayesianValidationMetric
    validation_target_fpr: float | None
    framework_id: str
    device: str
    dtype: str
    training_history_hash: str
    checkpoint_hash: str
    checkpoint_kind: str
    selected_epoch: int
    selected_validation_value: float
    provenance_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != BAYESIAN_TRAINING_PROVENANCE_VERSION:
            raise ValueError("unsupported Bayesian training provenance version")
        if self.source_id != DEEPMIND_REFERENCE_SOURCE_PIN.source_id:
            raise ValueError("Bayesian training source_id must match the pinned DeepMind reference")
        if self.source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit:
            raise ValueError("Bayesian training source_commit must match the pinned DeepMind reference")
        if self.source_path != BAYESIAN_SOURCE_PATH:
            raise ValueError("Bayesian training source_path must match the pinned detector source")
        require_clean_string("adapter_id", self.adapter_id)
        require_sha256("adapter_config_hash", self.adapter_config_hash)
        require_sha256("model_tokenizer_hash", self.model_tokenizer_hash)
        require_int("watermarking_depth", self.watermarking_depth)
        if self.watermarking_depth <= 0:
            raise ValueError("watermarking_depth must be positive")
        if self.watermark_mode != BAYESIAN_REQUIRED_WATERMARK_MODE:
            raise ValueError("Bayesian training must bind the source-supported tournament watermark mode")
        if self.g_distribution != BAYESIAN_REQUIRED_G_DISTRIBUTION:
            raise ValueError("Bayesian training must bind Bernoulli(0.5) g-value distribution evidence")
        partitions = (
            _prompt_family_partition("detector_train_prompt_families", self.detector_train_prompt_families),
            _prompt_family_partition("detector_validation_prompt_families", self.detector_validation_prompt_families),
            _prompt_family_partition("threshold_calibration_prompt_families", self.threshold_calibration_prompt_families),
            _prompt_family_partition("attack_development_prompt_families", self.attack_development_prompt_families),
            _prompt_family_partition("final_test_prompt_families", self.final_test_prompt_families),
        )
        flattened = tuple(value for partition in partitions for value in partition)
        if len(set(flattened)) != len(flattened):
            raise ValueError("Bayesian prompt-family partitions must be pairwise disjoint")
        require_sha256("train_dataset_hash", self.train_dataset_hash)
        require_sha256("validation_dataset_hash", self.validation_dataset_hash)
        if self.train_dataset_hash == self.validation_dataset_hash:
            raise ValueError("Bayesian train and validation datasets must be independently hashed")
        for name, value in (("init_seed", self.init_seed), ("order_seed", self.order_seed)):
            require_int(name, value)
            if value < 0 or value >= 1 << 64:
                raise ValueError(f"{name} must be between 0 and 2^64-1")
        require_int("epochs", self.epochs)
        if self.epochs <= 0:
            raise ValueError("epochs must be positive")
        object.__setattr__(self, "learning_rate", _positive_float("learning_rate", self.learning_rate))
        require_int("minibatch_size", self.minibatch_size)
        if self.minibatch_size <= 0:
            raise ValueError("minibatch_size must be positive")
        object.__setattr__(self, "l2_weight", _nonnegative_float("l2_weight", self.l2_weight))
        require_bool("shuffle", self.shuffle)
        if self.optimizer_id != BAYESIAN_OPTIMIZER_ID:
            raise ValueError("Bayesian training optimizer must match the pinned source optimizer")
        if self.lr_schedule_id != BAYESIAN_LR_SCHEDULE_ID:
            raise ValueError("Bayesian training learning-rate schedule must match the pinned source path")
        if not isinstance(self.validation_metric, BayesianValidationMetric):
            raise TypeError("validation_metric must be a BayesianValidationMetric")
        if self.validation_metric is BayesianValidationMetric.TPR_AT_FPR:
            if self.validation_target_fpr is None:
                raise ValueError("TPR_AT_FPR checkpoint selection requires validation_target_fpr")
            target = _positive_float("validation_target_fpr", self.validation_target_fpr)
            if target >= 1.0:
                raise ValueError("validation_target_fpr must be below 1")
            object.__setattr__(self, "validation_target_fpr", target)
        elif self.validation_target_fpr is not None:
            raise ValueError("CROSS_ENTROPY checkpoint selection must not carry validation_target_fpr")
        for name, value in (
            ("framework_id", self.framework_id),
            ("device", self.device),
            ("dtype", self.dtype),
        ):
            require_clean_string(name, value)
        require_sha256("training_history_hash", self.training_history_hash)
        require_sha256("checkpoint_hash", self.checkpoint_hash)
        if self.checkpoint_kind != BAYESIAN_TRAINED_CHECKPOINT_KIND:
            raise ValueError("confirmatory Bayesian provenance must identify a trained source-compatible checkpoint")
        require_int("selected_epoch", self.selected_epoch)
        if self.selected_epoch <= 0 or self.selected_epoch > self.epochs:
            raise ValueError("selected_epoch must lie within the frozen training epoch range")
        object.__setattr__(
            self,
            "selected_validation_value",
            _finite_float("selected_validation_value", self.selected_validation_value),
        )
        require_sha256("provenance_hash", self.provenance_hash)
        if self.provenance_hash != sha256_json(self._payload()):
            raise ValueError("provenance_hash does not match Bayesian training provenance")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "source_path": self.source_path,
            "adapter_id": self.adapter_id,
            "adapter_config_hash": self.adapter_config_hash,
            "model_tokenizer_hash": self.model_tokenizer_hash,
            "watermarking_depth": self.watermarking_depth,
            "watermark_mode": self.watermark_mode,
            "g_distribution": self.g_distribution,
            "detector_train_prompt_families": self.detector_train_prompt_families,
            "detector_validation_prompt_families": self.detector_validation_prompt_families,
            "threshold_calibration_prompt_families": self.threshold_calibration_prompt_families,
            "attack_development_prompt_families": self.attack_development_prompt_families,
            "final_test_prompt_families": self.final_test_prompt_families,
            "train_dataset_hash": self.train_dataset_hash,
            "validation_dataset_hash": self.validation_dataset_hash,
            "init_seed": self.init_seed,
            "order_seed": self.order_seed,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "minibatch_size": self.minibatch_size,
            "l2_weight": self.l2_weight,
            "shuffle": self.shuffle,
            "optimizer_id": self.optimizer_id,
            "lr_schedule_id": self.lr_schedule_id,
            "validation_metric": self.validation_metric.value,
            "validation_target_fpr": self.validation_target_fpr,
            "framework_id": self.framework_id,
            "device": self.device,
            "dtype": self.dtype,
            "training_history_hash": self.training_history_hash,
            "checkpoint_hash": self.checkpoint_hash,
            "checkpoint_kind": self.checkpoint_kind,
            "selected_epoch": self.selected_epoch,
            "selected_validation_value": self.selected_validation_value,
        }

    @classmethod
    def create(
        cls,
        *,
        adapter_id: str,
        adapter_config_hash: str,
        model_tokenizer_hash: str,
        watermarking_depth: int,
        detector_train_prompt_families: tuple[str, ...],
        detector_validation_prompt_families: tuple[str, ...],
        threshold_calibration_prompt_families: tuple[str, ...],
        attack_development_prompt_families: tuple[str, ...],
        final_test_prompt_families: tuple[str, ...],
        train_dataset_hash: str,
        validation_dataset_hash: str,
        init_seed: int,
        order_seed: int,
        epochs: int,
        learning_rate: float,
        minibatch_size: int,
        l2_weight: float,
        shuffle: bool,
        validation_metric: BayesianValidationMetric,
        validation_target_fpr: float | None,
        framework_id: str,
        device: str,
        dtype: str,
        training_history_hash: str,
        checkpoint_hash: str,
        selected_epoch: int,
        selected_validation_value: float,
    ) -> BayesianTrainingProvenance:
        payload = {
            "algorithm_version": BAYESIAN_TRAINING_PROVENANCE_VERSION,
            "source_id": DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
            "source_commit": DEEPMIND_REFERENCE_SOURCE_PIN.commit,
            "source_path": BAYESIAN_SOURCE_PATH,
            "adapter_id": adapter_id,
            "adapter_config_hash": adapter_config_hash,
            "model_tokenizer_hash": model_tokenizer_hash,
            "watermarking_depth": watermarking_depth,
            "watermark_mode": BAYESIAN_REQUIRED_WATERMARK_MODE,
            "g_distribution": BAYESIAN_REQUIRED_G_DISTRIBUTION,
            "detector_train_prompt_families": detector_train_prompt_families,
            "detector_validation_prompt_families": detector_validation_prompt_families,
            "threshold_calibration_prompt_families": threshold_calibration_prompt_families,
            "attack_development_prompt_families": attack_development_prompt_families,
            "final_test_prompt_families": final_test_prompt_families,
            "train_dataset_hash": train_dataset_hash,
            "validation_dataset_hash": validation_dataset_hash,
            "init_seed": init_seed,
            "order_seed": order_seed,
            "epochs": epochs,
            "learning_rate": float(learning_rate),
            "minibatch_size": minibatch_size,
            "l2_weight": float(l2_weight),
            "shuffle": shuffle,
            "optimizer_id": BAYESIAN_OPTIMIZER_ID,
            "lr_schedule_id": BAYESIAN_LR_SCHEDULE_ID,
            "validation_metric": validation_metric.value,
            "validation_target_fpr": validation_target_fpr,
            "framework_id": framework_id,
            "device": device,
            "dtype": dtype,
            "training_history_hash": training_history_hash,
            "checkpoint_hash": checkpoint_hash,
            "checkpoint_kind": BAYESIAN_TRAINED_CHECKPOINT_KIND,
            "selected_epoch": selected_epoch,
            "selected_validation_value": float(selected_validation_value),
        }
        return cls(
            BAYESIAN_TRAINING_PROVENANCE_VERSION,
            DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
            DEEPMIND_REFERENCE_SOURCE_PIN.commit,
            BAYESIAN_SOURCE_PATH,
            adapter_id,
            adapter_config_hash,
            model_tokenizer_hash,
            watermarking_depth,
            BAYESIAN_REQUIRED_WATERMARK_MODE,
            BAYESIAN_REQUIRED_G_DISTRIBUTION,
            detector_train_prompt_families,
            detector_validation_prompt_families,
            threshold_calibration_prompt_families,
            attack_development_prompt_families,
            final_test_prompt_families,
            train_dataset_hash,
            validation_dataset_hash,
            init_seed,
            order_seed,
            epochs,
            float(learning_rate),
            minibatch_size,
            float(l2_weight),
            shuffle,
            BAYESIAN_OPTIMIZER_ID,
            BAYESIAN_LR_SCHEDULE_ID,
            validation_metric,
            validation_target_fpr,
            framework_id,
            device,
            dtype,
            training_history_hash,
            checkpoint_hash,
            BAYESIAN_TRAINED_CHECKPOINT_KIND,
            selected_epoch,
            float(selected_validation_value),
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class BayesianSanityEvidence:
    algorithm_version: str
    training_provenance_hash: str
    label_permutation_artifact_hash: str
    label_permutation_near_chance_passed: bool
    zero_mask_artifact_hash: str
    zero_mask_rejection_passed: bool
    shuffled_g_artifact_hash: str
    shuffled_g_signal_reduction_passed: bool
    calibration_artifact_hash: str
    calibration_fpr_within_uncertainty_passed: bool
    leakage_audit_hash: str
    leakage_audit_clean: bool
    evidence_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != BAYESIAN_SANITY_EVIDENCE_VERSION:
            raise ValueError("unsupported Bayesian sanity evidence version")
        for name, value in (
            ("training_provenance_hash", self.training_provenance_hash),
            ("label_permutation_artifact_hash", self.label_permutation_artifact_hash),
            ("zero_mask_artifact_hash", self.zero_mask_artifact_hash),
            ("shuffled_g_artifact_hash", self.shuffled_g_artifact_hash),
            ("calibration_artifact_hash", self.calibration_artifact_hash),
            ("leakage_audit_hash", self.leakage_audit_hash),
            ("evidence_hash", self.evidence_hash),
        ):
            require_sha256(name, value)
        for name, value in (
            ("label_permutation_near_chance_passed", self.label_permutation_near_chance_passed),
            ("zero_mask_rejection_passed", self.zero_mask_rejection_passed),
            ("shuffled_g_signal_reduction_passed", self.shuffled_g_signal_reduction_passed),
            ("calibration_fpr_within_uncertainty_passed", self.calibration_fpr_within_uncertainty_passed),
            ("leakage_audit_clean", self.leakage_audit_clean),
        ):
            require_bool(name, value)
        if self.evidence_hash != sha256_json(self._payload()):
            raise ValueError("evidence_hash does not match Bayesian sanity evidence")

    @property
    def all_passed(self) -> bool:
        return (
            self.label_permutation_near_chance_passed
            and self.zero_mask_rejection_passed
            and self.shuffled_g_signal_reduction_passed
            and self.calibration_fpr_within_uncertainty_passed
            and self.leakage_audit_clean
        )

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "training_provenance_hash": self.training_provenance_hash,
            "label_permutation_artifact_hash": self.label_permutation_artifact_hash,
            "label_permutation_near_chance_passed": self.label_permutation_near_chance_passed,
            "zero_mask_artifact_hash": self.zero_mask_artifact_hash,
            "zero_mask_rejection_passed": self.zero_mask_rejection_passed,
            "shuffled_g_artifact_hash": self.shuffled_g_artifact_hash,
            "shuffled_g_signal_reduction_passed": self.shuffled_g_signal_reduction_passed,
            "calibration_artifact_hash": self.calibration_artifact_hash,
            "calibration_fpr_within_uncertainty_passed": self.calibration_fpr_within_uncertainty_passed,
            "leakage_audit_hash": self.leakage_audit_hash,
            "leakage_audit_clean": self.leakage_audit_clean,
        }

    @classmethod
    def create(
        cls,
        training_provenance_hash: str,
        *,
        label_permutation_artifact_hash: str,
        label_permutation_near_chance_passed: bool,
        zero_mask_artifact_hash: str,
        zero_mask_rejection_passed: bool,
        shuffled_g_artifact_hash: str,
        shuffled_g_signal_reduction_passed: bool,
        calibration_artifact_hash: str,
        calibration_fpr_within_uncertainty_passed: bool,
        leakage_audit_hash: str,
        leakage_audit_clean: bool,
    ) -> BayesianSanityEvidence:
        payload = {
            "algorithm_version": BAYESIAN_SANITY_EVIDENCE_VERSION,
            "training_provenance_hash": training_provenance_hash,
            "label_permutation_artifact_hash": label_permutation_artifact_hash,
            "label_permutation_near_chance_passed": label_permutation_near_chance_passed,
            "zero_mask_artifact_hash": zero_mask_artifact_hash,
            "zero_mask_rejection_passed": zero_mask_rejection_passed,
            "shuffled_g_artifact_hash": shuffled_g_artifact_hash,
            "shuffled_g_signal_reduction_passed": shuffled_g_signal_reduction_passed,
            "calibration_artifact_hash": calibration_artifact_hash,
            "calibration_fpr_within_uncertainty_passed": calibration_fpr_within_uncertainty_passed,
            "leakage_audit_hash": leakage_audit_hash,
            "leakage_audit_clean": leakage_audit_clean,
        }
        return cls(
            BAYESIAN_SANITY_EVIDENCE_VERSION,
            training_provenance_hash,
            label_permutation_artifact_hash,
            label_permutation_near_chance_passed,
            zero_mask_artifact_hash,
            zero_mask_rejection_passed,
            shuffled_g_artifact_hash,
            shuffled_g_signal_reduction_passed,
            calibration_artifact_hash,
            calibration_fpr_within_uncertainty_passed,
            leakage_audit_hash,
            leakage_audit_clean,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class BayesianConfirmatoryReadiness:
    algorithm_version: str
    training_provenance_hash: str
    sanity_evidence_hash: str
    checkpoint_hash: str
    adapter_id: str
    adapter_config_hash: str
    model_tokenizer_hash: str
    watermarking_depth: int
    source_id: str
    source_commit: str
    source_path: str
    status: BayesianConfirmatoryReadinessStatus
    blocking_reasons: tuple[str, ...]
    readiness_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != BAYESIAN_CONFIRMATORY_READINESS_VERSION:
            raise ValueError("unsupported Bayesian confirmatory readiness version")
        for name, value in (
            ("training_provenance_hash", self.training_provenance_hash),
            ("sanity_evidence_hash", self.sanity_evidence_hash),
            ("checkpoint_hash", self.checkpoint_hash),
            ("adapter_config_hash", self.adapter_config_hash),
            ("model_tokenizer_hash", self.model_tokenizer_hash),
            ("readiness_hash", self.readiness_hash),
        ):
            require_sha256(name, value)
        require_clean_string("adapter_id", self.adapter_id)
        require_int("watermarking_depth", self.watermarking_depth)
        if self.watermarking_depth <= 0:
            raise ValueError("watermarking_depth must be positive")
        if self.source_id != DEEPMIND_REFERENCE_SOURCE_PIN.source_id:
            raise ValueError("Bayesian readiness source_id must match the pinned DeepMind reference")
        if self.source_commit != DEEPMIND_REFERENCE_SOURCE_PIN.commit:
            raise ValueError("Bayesian readiness source_commit must match the pinned DeepMind reference")
        if self.source_path != BAYESIAN_SOURCE_PATH:
            raise ValueError("Bayesian readiness source_path must match the pinned detector source")
        if not isinstance(self.status, BayesianConfirmatoryReadinessStatus):
            raise TypeError("status must be a BayesianConfirmatoryReadinessStatus")
        if not isinstance(self.blocking_reasons, tuple):
            raise TypeError("blocking_reasons must be a tuple")
        if self.blocking_reasons != tuple(sorted(set(self.blocking_reasons))):
            raise ValueError("blocking_reasons must be unique and canonically ordered")
        for value in self.blocking_reasons:
            require_clean_string("blocking reason", value)
        if self.status is BayesianConfirmatoryReadinessStatus.READY and self.blocking_reasons:
            raise ValueError("READY Bayesian readiness cannot contain blocking reasons")
        if self.status is BayesianConfirmatoryReadinessStatus.BLOCKED and not self.blocking_reasons:
            raise ValueError("BLOCKED Bayesian readiness must contain blocking reasons")
        if self.readiness_hash != sha256_json(self._payload()):
            raise ValueError("readiness_hash does not match Bayesian confirmatory readiness")

    @property
    def ready(self) -> bool:
        return self.status is BayesianConfirmatoryReadinessStatus.READY

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "training_provenance_hash": self.training_provenance_hash,
            "sanity_evidence_hash": self.sanity_evidence_hash,
            "checkpoint_hash": self.checkpoint_hash,
            "adapter_id": self.adapter_id,
            "adapter_config_hash": self.adapter_config_hash,
            "model_tokenizer_hash": self.model_tokenizer_hash,
            "watermarking_depth": self.watermarking_depth,
            "source_id": self.source_id,
            "source_commit": self.source_commit,
            "source_path": self.source_path,
            "status": self.status.value,
            "blocking_reasons": self.blocking_reasons,
        }


def build_bayesian_confirmatory_readiness(
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
    provenance: BayesianTrainingProvenance,
    sanity: BayesianSanityEvidence,
    model_tokenizer_hash: str,
) -> BayesianConfirmatoryReadiness:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(checkpoint, BayesianCheckpoint):
        raise TypeError("checkpoint must be a BayesianCheckpoint")
    if not isinstance(provenance, BayesianTrainingProvenance):
        raise TypeError("provenance must be BayesianTrainingProvenance")
    if not isinstance(sanity, BayesianSanityEvidence):
        raise TypeError("sanity must be BayesianSanityEvidence")
    require_sha256("model_tokenizer_hash", model_tokenizer_hash)
    reasons: list[str] = []
    if sanity.training_provenance_hash != provenance.provenance_hash:
        reasons.append("sanity evidence is not bound to training provenance")
    if not sanity.all_passed:
        reasons.append("one or more Bayesian sanity checks failed")
    if checkpoint.fixture_kind != BAYESIAN_TRAINED_CHECKPOINT_KIND:
        reasons.append("checkpoint is not marked as a trained source-compatible checkpoint")
    if checkpoint.checkpoint_hash != provenance.checkpoint_hash:
        reasons.append("checkpoint hash does not match training provenance")
    if checkpoint.watermarking_depth != provenance.watermarking_depth:
        reasons.append("checkpoint depth does not match training provenance")
    if batch.depth != provenance.watermarking_depth:
        reasons.append("observation depth does not match training provenance")
    if batch.adapter_id != provenance.adapter_id:
        reasons.append("adapter identity does not match training provenance")
    if batch.adapter_config_hash != provenance.adapter_config_hash:
        reasons.append("adapter configuration does not match training provenance")
    if model_tokenizer_hash != provenance.model_tokenizer_hash:
        reasons.append("model/tokenizer identity does not match training provenance")
    if checkpoint.source_id != provenance.source_id or checkpoint.source_commit != provenance.source_commit:
        reasons.append("checkpoint source identity does not match training provenance")
    blocking = tuple(sorted(set(reasons)))
    status = (
        BayesianConfirmatoryReadinessStatus.READY
        if not blocking
        else BayesianConfirmatoryReadinessStatus.BLOCKED
    )
    payload = {
        "algorithm_version": BAYESIAN_CONFIRMATORY_READINESS_VERSION,
        "training_provenance_hash": provenance.provenance_hash,
        "sanity_evidence_hash": sanity.evidence_hash,
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "adapter_id": batch.adapter_id,
        "adapter_config_hash": batch.adapter_config_hash,
        "model_tokenizer_hash": model_tokenizer_hash,
        "watermarking_depth": batch.depth,
        "source_id": provenance.source_id,
        "source_commit": provenance.source_commit,
        "source_path": provenance.source_path,
        "status": status.value,
        "blocking_reasons": blocking,
    }
    return BayesianConfirmatoryReadiness(
        BAYESIAN_CONFIRMATORY_READINESS_VERSION,
        provenance.provenance_hash,
        sanity.evidence_hash,
        checkpoint.checkpoint_hash,
        batch.adapter_id,
        batch.adapter_config_hash,
        model_tokenizer_hash,
        batch.depth,
        provenance.source_id,
        provenance.source_commit,
        provenance.source_path,
        status,
        blocking,
        sha256_json(payload),
    )


def verify_bayesian_confirmatory_readiness(
    readiness: BayesianConfirmatoryReadiness,
    batch: NativeObservationBatch,
    checkpoint: BayesianCheckpoint,
    provenance: BayesianTrainingProvenance,
    sanity: BayesianSanityEvidence,
    model_tokenizer_hash: str,
) -> None:
    if not isinstance(readiness, BayesianConfirmatoryReadiness):
        raise TypeError("readiness must be BayesianConfirmatoryReadiness")
    expected = build_bayesian_confirmatory_readiness(
        batch,
        checkpoint,
        provenance,
        sanity,
        model_tokenizer_hash,
    )
    if readiness != expected:
        raise ValueError("Bayesian confirmatory readiness does not replay exactly from frozen evidence")
