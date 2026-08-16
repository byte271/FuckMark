from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus import CorpusSplit, TinyDevCorpusArtifact, WatermarkLabel
from ..detectors import (
    BaselineStatus,
    ExactBinomialInterval,
    UncalibratedDetectorEvidence,
    apply_calibration,
    evaluate_pristine_baseline,
    exact_binomial_interval,
)
from ..hashing import sha256_json
from .development_calibration import DevelopmentCalibrationBinding, DEVELOPMENT_TARGET_FPRS
from .registry import DevelopmentExperimentId, default_development_experiment_registry


E02_ALGORITHM_VERSION = "e02-pristine-detectability-v1"
E02_INTERPRETABILITY_FLOOR = 0.80


class E02Status(str, Enum):
    PASS = "PASS"
    UNDERPOWERED = "UNDERPOWERED"


class E02InputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E02OperatingPoint:
    target_fpr: float
    threshold_hash: str
    threshold_value: float
    positive_count: int
    positive_detected_count: int
    tpr: float
    tpr_interval: ExactBinomialInterval
    negative_count: int
    negative_detected_count: int
    evaluation_fpr: float
    evaluation_fpr_interval: ExactBinomialInterval
    baseline_status: BaselineStatus
    point_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("target_fpr", self.target_fpr),
            ("threshold_value", self.threshold_value),
            ("tpr", self.tpr),
            ("evaluation_fpr", self.evaluation_fpr),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, number)
        if self.target_fpr not in DEVELOPMENT_TARGET_FPRS:
            raise ValueError("E02 operating point must use a frozen development target FPR")
        require_sha256("threshold_hash", self.threshold_hash)
        for name, value in (
            ("positive_count", self.positive_count),
            ("positive_detected_count", self.positive_detected_count),
            ("negative_count", self.negative_count),
            ("negative_detected_count", self.negative_detected_count),
        ):
            require_int(name, value)
        if self.positive_count <= 0 or self.negative_count <= 0:
            raise ValueError("E02 operating point requires positive and negative samples")
        if not 0 <= self.positive_detected_count <= self.positive_count:
            raise ValueError("positive_detected_count is outside sample range")
        if not 0 <= self.negative_detected_count <= self.negative_count:
            raise ValueError("negative_detected_count is outside sample range")
        if self.tpr != self.positive_detected_count / self.positive_count:
            raise ValueError("tpr does not match positive detection count")
        if self.evaluation_fpr != self.negative_detected_count / self.negative_count:
            raise ValueError("evaluation_fpr does not match negative detection count")
        if not isinstance(self.tpr_interval, ExactBinomialInterval):
            raise TypeError("tpr_interval must be an ExactBinomialInterval")
        if not isinstance(self.evaluation_fpr_interval, ExactBinomialInterval):
            raise TypeError("evaluation_fpr_interval must be an ExactBinomialInterval")
        if not self.tpr_interval.lower <= self.tpr <= self.tpr_interval.upper:
            raise ValueError("tpr must lie inside its exact interval")
        if not self.evaluation_fpr_interval.lower <= self.evaluation_fpr <= self.evaluation_fpr_interval.upper:
            raise ValueError("evaluation_fpr must lie inside its exact interval")
        if not isinstance(self.baseline_status, BaselineStatus):
            raise TypeError("baseline_status must be a BaselineStatus")
        expected_status = BaselineStatus.PASS if self.tpr >= E02_INTERPRETABILITY_FLOOR else BaselineStatus.BELOW_FLOOR
        if self.baseline_status is not expected_status:
            raise ValueError("baseline_status does not match E02 interpretability floor")
        require_sha256("point_hash", self.point_hash)
        if self.point_hash != sha256_json(self._payload()):
            raise ValueError("point_hash does not match E02 operating point")

    def _payload(self) -> dict[str, object]:
        return {
            "target_fpr": self.target_fpr,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "positive_count": self.positive_count,
            "positive_detected_count": self.positive_detected_count,
            "tpr": self.tpr,
            "tpr_interval": self.tpr_interval,
            "negative_count": self.negative_count,
            "negative_detected_count": self.negative_detected_count,
            "evaluation_fpr": self.evaluation_fpr,
            "evaluation_fpr_interval": self.evaluation_fpr_interval,
            "baseline_status": self.baseline_status.value,
        }


@dataclass(frozen=True, slots=True)
class E02PristineDetectabilityResult:
    algorithm_version: str
    experiment_definition_hash: str
    tiny_dev_artifact_hash: str
    calibration_binding_hash: str
    detector_identity_hash: str
    attack_sample_ids: tuple[str, ...]
    evidence_manifest_hash: str
    watermarked_scores: tuple[float, ...]
    unwatermarked_scores: tuple[float, ...]
    auc: float
    operating_points: tuple[E02OperatingPoint, ...]
    status: E02Status
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != E02_ALGORITHM_VERSION:
            raise ValueError("unsupported E02 algorithm version")
        for name, value in (
            ("experiment_definition_hash", self.experiment_definition_hash),
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("calibration_binding_hash", self.calibration_binding_hash),
            ("detector_identity_hash", self.detector_identity_hash),
            ("evidence_manifest_hash", self.evidence_manifest_hash),
            ("result_hash", self.result_hash),
        ):
            require_sha256(name, value)
        if not isinstance(self.attack_sample_ids, tuple):
            raise TypeError("attack_sample_ids must be a tuple")
        if self.attack_sample_ids != tuple(sorted(set(self.attack_sample_ids))):
            raise ValueError("attack_sample_ids must be unique and canonically ordered")
        if len(self.attack_sample_ids) != 8:
            raise ValueError("E02 tiny-dev run requires exactly eight attack-development samples")
        for sample_id in self.attack_sample_ids:
            require_clean_string("attack sample ID", sample_id)
        for name, values in (
            ("watermarked_scores", self.watermarked_scores),
            ("unwatermarked_scores", self.unwatermarked_scores),
        ):
            if not isinstance(values, tuple) or len(values) != 4:
                raise ValueError(f"{name} must contain exactly four scores")
            normalized = tuple(float(value) for value in values)
            if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in normalized):
                raise ValueError(f"{name} must contain finite scores in [0, 1]")
            if normalized != tuple(sorted(normalized)):
                raise ValueError(f"{name} must use canonical ascending order")
            object.__setattr__(self, name, normalized)
        if isinstance(self.auc, bool) or not isinstance(self.auc, (int, float)):
            raise TypeError("auc must be a real number")
        auc = float(self.auc)
        if not math.isfinite(auc) or auc < 0.0 or auc > 1.0:
            raise ValueError("auc must be in [0, 1]")
        object.__setattr__(self, "auc", auc)
        if not isinstance(self.operating_points, tuple):
            raise TypeError("operating_points must be a tuple")
        if any(not isinstance(value, E02OperatingPoint) for value in self.operating_points):
            raise TypeError("operating_points must contain E02OperatingPoint values")
        if tuple(value.target_fpr for value in self.operating_points) != DEVELOPMENT_TARGET_FPRS:
            raise ValueError("E02 result must contain frozen 5% and 1% operating points")
        if not isinstance(self.status, E02Status):
            raise TypeError("status must be an E02Status")
        primary = next(value for value in self.operating_points if value.target_fpr == 0.01)
        expected_status = E02Status.PASS if primary.baseline_status is BaselineStatus.PASS else E02Status.UNDERPOWERED
        if self.status is not expected_status:
            raise ValueError("E02 status does not match the 1% FPR pristine baseline gate")
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match E02 result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_definition_hash": self.experiment_definition_hash,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "calibration_binding_hash": self.calibration_binding_hash,
            "detector_identity_hash": self.detector_identity_hash,
            "attack_sample_ids": self.attack_sample_ids,
            "evidence_manifest_hash": self.evidence_manifest_hash,
            "watermarked_scores": self.watermarked_scores,
            "unwatermarked_scores": self.unwatermarked_scores,
            "auc": self.auc,
            "operating_points": self.operating_points,
            "status": self.status.value,
        }


def _auc(positive_scores: tuple[float, ...], negative_scores: tuple[float, ...]) -> float:
    wins = 0.0
    comparisons = len(positive_scores) * len(negative_scores)
    for positive in positive_scores:
        for negative in negative_scores:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / comparisons


def run_e02_pristine_detectability(
    artifact: TinyDevCorpusArtifact,
    calibration: DevelopmentCalibrationBinding,
    attack_evidence: Sequence[UncalibratedDetectorEvidence],
) -> E02PristineDetectabilityResult:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(calibration, DevelopmentCalibrationBinding):
        raise TypeError("calibration must be a DevelopmentCalibrationBinding")
    if calibration.tiny_dev_artifact_hash != artifact.artifact_hash:
        raise E02InputError("calibration binding does not belong to the supplied tiny-dev corpus")
    if not isinstance(attack_evidence, Sequence) or isinstance(attack_evidence, (str, bytes, bytearray)):
        raise TypeError("attack_evidence must be a sequence")
    evidence = tuple(attack_evidence)
    if any(not isinstance(value, UncalibratedDetectorEvidence) for value in evidence):
        raise TypeError("attack_evidence must contain UncalibratedDetectorEvidence values")
    attack_samples = tuple(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
    )
    sample_by_id = {sample.sample_id: sample for sample in attack_samples}
    expected_ids = tuple(sorted(sample_by_id))
    actual_ids = tuple(sorted(value.sample_id for value in evidence))
    if actual_ids != expected_ids:
        missing = tuple(sorted(set(expected_ids) - set(actual_ids)))
        unexpected = tuple(sorted(set(actual_ids) - set(expected_ids)))
        raise E02InputError(
            f"attack evidence does not exactly match tiny-dev attack split; missing={missing}, unexpected={unexpected}"
        )
    evidence_by_id = {value.sample_id: value for value in evidence}
    watermarked_ids = tuple(
        sorted(sample.sample_id for sample in attack_samples if sample.label is WatermarkLabel.WATERMARKED)
    )
    unwatermarked_ids = tuple(
        sorted(sample.sample_id for sample in attack_samples if sample.label is WatermarkLabel.UNWATERMARKED)
    )
    watermarked_scores = tuple(sorted(evidence_by_id[sample_id].raw_score for sample_id in watermarked_ids))
    unwatermarked_scores = tuple(sorted(evidence_by_id[sample_id].raw_score for sample_id in unwatermarked_ids))
    points: list[E02OperatingPoint] = []
    for target_fpr in DEVELOPMENT_TARGET_FPRS:
        positive_results = tuple(
            apply_calibration(evidence_by_id[sample_id], calibration.calibration_bundle, target_fpr)
            for sample_id in watermarked_ids
        )
        negative_results = tuple(
            apply_calibration(evidence_by_id[sample_id], calibration.calibration_bundle, target_fpr)
            for sample_id in unwatermarked_ids
        )
        baseline = evaluate_pristine_baseline(
            positive_results,
            interpretability_floor=E02_INTERPRETABILITY_FLOOR,
            confidence_level=0.95,
        )
        negative_detected_count = sum(value.decision for value in negative_results)
        evaluation_fpr = negative_detected_count / len(negative_results)
        evaluation_fpr_interval = exact_binomial_interval(
            negative_detected_count,
            len(negative_results),
            0.95,
        )
        threshold = next(
            value
            for value in calibration.calibration_bundle.thresholds
            if value.target_fpr == target_fpr
        )
        payload = {
            "target_fpr": target_fpr,
            "threshold_hash": threshold.threshold_hash,
            "threshold_value": threshold.value,
            "positive_count": baseline.sample_count,
            "positive_detected_count": baseline.detected_count,
            "tpr": baseline.tpr,
            "tpr_interval": baseline.tpr_interval,
            "negative_count": len(negative_results),
            "negative_detected_count": negative_detected_count,
            "evaluation_fpr": evaluation_fpr,
            "evaluation_fpr_interval": evaluation_fpr_interval,
            "baseline_status": baseline.status.value,
        }
        points.append(
            E02OperatingPoint(
                target_fpr,
                threshold.threshold_hash,
                threshold.value,
                baseline.sample_count,
                baseline.detected_count,
                baseline.tpr,
                baseline.tpr_interval,
                len(negative_results),
                negative_detected_count,
                evaluation_fpr,
                evaluation_fpr_interval,
                baseline.status,
                sha256_json(payload),
            )
        )
    point_tuple = tuple(points)
    primary = next(value for value in point_tuple if value.target_fpr == 0.01)
    status = E02Status.PASS if primary.baseline_status is BaselineStatus.PASS else E02Status.UNDERPOWERED
    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E02)
    evidence_manifest_hash = sha256_json(
        tuple(sha256_json(evidence_by_id[sample_id]) for sample_id in expected_ids)
    )
    result_payload = {
        "algorithm_version": E02_ALGORITHM_VERSION,
        "experiment_definition_hash": definition.definition_hash,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "calibration_binding_hash": calibration.binding_hash,
        "detector_identity_hash": calibration.calibration_bundle.detector_identity.identity_hash,
        "attack_sample_ids": expected_ids,
        "evidence_manifest_hash": evidence_manifest_hash,
        "watermarked_scores": watermarked_scores,
        "unwatermarked_scores": unwatermarked_scores,
        "auc": _auc(watermarked_scores, unwatermarked_scores),
        "operating_points": point_tuple,
        "status": status.value,
    }
    return E02PristineDetectabilityResult(
        E02_ALGORITHM_VERSION,
        definition.definition_hash,
        artifact.artifact_hash,
        calibration.binding_hash,
        calibration.calibration_bundle.detector_identity.identity_hash,
        expected_ids,
        evidence_manifest_hash,
        watermarked_scores,
        unwatermarked_scores,
        result_payload["auc"],
        point_tuple,
        status,
        sha256_json(result_payload),
    )
