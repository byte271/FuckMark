from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..adapters.base import WatermarkAdapter
from ..corpus import CorpusSplit, TinyDevCorpusArtifact, WatermarkLabel
from ..detectors import (
    BaselineStatus,
    CalibratedDetectorResult,
    CalibrationBundle,
    CalibrationScope,
    DetectorFamily,
    ExactBinomialInterval,
    PristineBaselineSummary,
    UncalibratedDetectorEvidence,
    apply_calibration,
    calibrate_detector,
    evaluate_pristine_baseline,
    exact_binomial_interval,
    mean_evidence,
    weighted_mean_evidence,
)
from ..detectors.calibration_identity import DetectorCalibrationIdentity
from ..hashing import sha256_json
from ..native_observations import build_native_observations


TINY_DEV_DETECTOR_EVIDENCE_ALGORITHM_VERSION = "tiny-dev-detector-evidence-v1"
TINY_DEV_THRESHOLD_EVALUATION_ALGORITHM_VERSION = "tiny-dev-threshold-evaluation-v1"
TINY_DEV_DETECTOR_FAMILY_ALGORITHM_VERSION = "tiny-dev-detector-family-evidence-v1"
TINY_DEV_HEADLINE_FPRS = (0.05, 0.01)
TINY_DEV_PRIMARY_FPR = 0.01
TINY_DEV_BASELINE_INTERPRETABILITY_FLOOR = 0.80
TINY_DEV_TOKEN_TRACK = "original-generation-token-ids"
TINY_DEV_PROMPT_BOUNDARY_MODE = "continuation-only"
TINY_DEV_DETECTOR_STATUS = "DEVELOPMENT_ONLY"


class TinyDevDetectorEvidenceError(ValueError):
    pass


def _require_probability(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


@dataclass(frozen=True, slots=True)
class TinyDevThresholdEvaluation:
    algorithm_version: str
    target_fpr: float
    threshold_hash: str
    threshold_value: float
    achieved_calibration_fpr: float
    calibration_fpr_interval: ExactBinomialInterval
    positive_results: tuple[CalibratedDetectorResult, ...]
    negative_results: tuple[CalibratedDetectorResult, ...]
    pristine_baseline: PristineBaselineSummary
    attack_negative_detected_count: int
    attack_negative_fpr: float
    attack_negative_fpr_interval: ExactBinomialInterval
    evaluation_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_THRESHOLD_EVALUATION_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev threshold evaluation version")
        target = _require_probability("target_fpr", self.target_fpr)
        if target not in TINY_DEV_HEADLINE_FPRS:
            raise ValueError("target_fpr must be a frozen TinyDev headline FPR")
        object.__setattr__(self, "target_fpr", target)
        require_sha256("threshold_hash", self.threshold_hash)
        threshold_value = _require_probability("threshold_value", self.threshold_value)
        object.__setattr__(self, "threshold_value", threshold_value)
        achieved = _require_probability("achieved_calibration_fpr", self.achieved_calibration_fpr)
        object.__setattr__(self, "achieved_calibration_fpr", achieved)
        if not isinstance(self.calibration_fpr_interval, ExactBinomialInterval):
            raise TypeError("calibration_fpr_interval must be an ExactBinomialInterval")
        if not isinstance(self.positive_results, tuple) or not isinstance(self.negative_results, tuple):
            raise TypeError("threshold results must be tuples")
        if len(self.positive_results) != 4 or len(self.negative_results) != 4:
            raise ValueError("TinyDev threshold evaluation requires four positive and four negative attack rows")
        if any(not isinstance(value, CalibratedDetectorResult) for value in (*self.positive_results, *self.negative_results)):
            raise TypeError("threshold result tuples must contain CalibratedDetectorResult values")
        all_results = (*self.positive_results, *self.negative_results)
        if len({value.sample_id for value in all_results}) != 8:
            raise ValueError("TinyDev attack threshold results must use eight unique samples")
        for value in all_results:
            if value.target_fpr != target:
                raise ValueError("calibrated attack result target FPR does not match threshold evaluation")
            if value.threshold_hash != self.threshold_hash:
                raise ValueError("calibrated attack result threshold hash does not match threshold evaluation")
            if value.threshold_value != threshold_value:
                raise ValueError("calibrated attack result threshold value does not match threshold evaluation")
            if value.achieved_calibration_fpr != achieved:
                raise ValueError("calibrated attack result achieved FPR does not match threshold evaluation")
            if value.calibration_fpr_interval != self.calibration_fpr_interval:
                raise ValueError("calibrated attack result calibration interval does not match threshold evaluation")
        if tuple(sorted(self.positive_results, key=lambda value: value.sample_id)) != self.positive_results:
            raise ValueError("positive_results must use canonical sample ordering")
        if tuple(sorted(self.negative_results, key=lambda value: value.sample_id)) != self.negative_results:
            raise ValueError("negative_results must use canonical sample ordering")
        if not isinstance(self.pristine_baseline, PristineBaselineSummary):
            raise TypeError("pristine_baseline must be a PristineBaselineSummary")
        if self.pristine_baseline.threshold_hash != self.threshold_hash:
            raise ValueError("pristine baseline threshold does not match threshold evaluation")
        expected_positive_evidence = tuple(sorted(value.evidence_hash for value in self.positive_results))
        if self.pristine_baseline.evidence_manifest_hash != sha256_json(expected_positive_evidence):
            raise ValueError("pristine baseline evidence does not match positive attack results")
        require_int("attack_negative_detected_count", self.attack_negative_detected_count)
        detected = sum(value.decision for value in self.negative_results)
        if self.attack_negative_detected_count != detected:
            raise ValueError("attack_negative_detected_count does not match negative decisions")
        expected_fpr = detected / len(self.negative_results)
        attack_fpr = _require_probability("attack_negative_fpr", self.attack_negative_fpr)
        if attack_fpr != expected_fpr:
            raise ValueError("attack_negative_fpr does not match negative decisions")
        object.__setattr__(self, "attack_negative_fpr", attack_fpr)
        if not isinstance(self.attack_negative_fpr_interval, ExactBinomialInterval):
            raise TypeError("attack_negative_fpr_interval must be an ExactBinomialInterval")
        if self.attack_negative_fpr_interval != exact_binomial_interval(detected, len(self.negative_results)):
            raise ValueError("attack negative FPR interval does not match decisions")
        require_sha256("evaluation_hash", self.evaluation_hash)
        if self.evaluation_hash != sha256_json(self._payload()):
            raise ValueError("evaluation_hash does not match TinyDev threshold evaluation")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "target_fpr": self.target_fpr,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "achieved_calibration_fpr": self.achieved_calibration_fpr,
            "calibration_fpr_interval": self.calibration_fpr_interval,
            "positive_results": self.positive_results,
            "negative_results": self.negative_results,
            "pristine_baseline": self.pristine_baseline,
            "attack_negative_detected_count": self.attack_negative_detected_count,
            "attack_negative_fpr": self.attack_negative_fpr,
            "attack_negative_fpr_interval": self.attack_negative_fpr_interval,
        }


@dataclass(frozen=True, slots=True)
class TinyDevDetectorFamilyEvidence:
    algorithm_version: str
    detector_family: DetectorFamily
    calibration_evidence: tuple[UncalibratedDetectorEvidence, ...]
    attack_evidence: tuple[UncalibratedDetectorEvidence, ...]
    calibration_bundle: CalibrationBundle
    threshold_evaluations: tuple[TinyDevThresholdEvaluation, ...]
    family_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_DETECTOR_FAMILY_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev detector-family evidence version")
        if self.detector_family not in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN):
            raise ValueError("TinyDev v1 real detector evidence supports Mean and Weighted Mean only")
        if not isinstance(self.calibration_evidence, tuple) or not isinstance(self.attack_evidence, tuple):
            raise TypeError("detector evidence rows must be tuples")
        if len(self.calibration_evidence) != 100:
            raise ValueError("TinyDev detector calibration requires exactly 100 negative rows")
        if len(self.attack_evidence) != 8:
            raise ValueError("TinyDev detector attack evaluation requires exactly eight rows")
        for values in (self.calibration_evidence, self.attack_evidence):
            if any(not isinstance(value, UncalibratedDetectorEvidence) for value in values):
                raise TypeError("detector evidence tuples must contain UncalibratedDetectorEvidence values")
            if tuple(sorted(values, key=lambda value: value.sample_id)) != values:
                raise ValueError("detector evidence rows must use canonical sample ordering")
            if len({value.sample_id for value in values}) != len(values):
                raise ValueError("detector evidence sample IDs must be unique")
            if any(value.detector_family is not self.detector_family for value in values):
                raise ValueError("detector evidence family does not match family container")
        if set(value.sample_id for value in self.calibration_evidence) & set(value.sample_id for value in self.attack_evidence):
            raise ValueError("calibration and attack evidence populations must be disjoint")
        if not isinstance(self.calibration_bundle, CalibrationBundle):
            raise TypeError("calibration_bundle must be a CalibrationBundle")
        if self.calibration_bundle.negative_count != 100:
            raise ValueError("calibration bundle must bind 100 TinyDev negatives")
        identity = DetectorCalibrationIdentity.from_evidence(self.calibration_evidence[0])
        if self.calibration_bundle.detector_identity != identity:
            raise ValueError("calibration bundle detector identity does not match calibration evidence")
        if any(DetectorCalibrationIdentity.from_evidence(value) != identity for value in (*self.calibration_evidence, *self.attack_evidence)):
            raise ValueError("TinyDev family evidence mixes detector identities")
        if tuple(value.target_fpr for value in self.calibration_bundle.thresholds) != TINY_DEV_HEADLINE_FPRS:
            raise ValueError("calibration bundle must contain the frozen 5% and 1% headline FPRs")
        if not isinstance(self.threshold_evaluations, tuple):
            raise TypeError("threshold_evaluations must be a tuple")
        if tuple(value.target_fpr for value in self.threshold_evaluations) != TINY_DEV_HEADLINE_FPRS:
            raise ValueError("threshold evaluations must use the frozen 5% and 1% FPR order")
        if any(not isinstance(value, TinyDevThresholdEvaluation) for value in self.threshold_evaluations):
            raise TypeError("threshold_evaluations must contain TinyDevThresholdEvaluation values")
        for evaluation, threshold in zip(self.threshold_evaluations, self.calibration_bundle.thresholds):
            if evaluation.threshold_hash != threshold.threshold_hash:
                raise ValueError("threshold evaluation does not match calibration bundle")
        require_sha256("family_hash", self.family_hash)
        if self.family_hash != sha256_json(self._payload()):
            raise ValueError("family_hash does not match TinyDev detector evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "detector_family": self.detector_family.value,
            "calibration_evidence": self.calibration_evidence,
            "attack_evidence": self.attack_evidence,
            "calibration_bundle": self.calibration_bundle,
            "threshold_evaluations": self.threshold_evaluations,
        }


@dataclass(frozen=True, slots=True)
class TinyDevDetectorEvidenceArtifact:
    algorithm_version: str
    tiny_dev_artifact_hash: str
    corpus_manifest_hash: str
    watermark_config_hash: str
    adapter_id: str
    adapter_algorithm_version: str
    adapter_config_hash: str
    adapter_source_id: str
    adapter_source_commit: str
    token_track: str
    prompt_boundary_mode: str
    headline_fprs: tuple[float, ...]
    primary_fpr: float
    baseline_interpretability_floor: float
    family_evidence: tuple[TinyDevDetectorFamilyEvidence, ...]
    scientific_status: str
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != TINY_DEV_DETECTOR_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev detector evidence artifact version")
        for name, value in (
            ("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("watermark_config_hash", self.watermark_config_hash),
            ("adapter_config_hash", self.adapter_config_hash),
            ("artifact_hash", self.artifact_hash),
        ):
            require_sha256(name, value)
        for name, value in (
            ("adapter_id", self.adapter_id),
            ("adapter_algorithm_version", self.adapter_algorithm_version),
            ("adapter_source_id", self.adapter_source_id),
            ("adapter_source_commit", self.adapter_source_commit),
            ("token_track", self.token_track),
            ("prompt_boundary_mode", self.prompt_boundary_mode),
            ("scientific_status", self.scientific_status),
        ):
            require_clean_string(name, value)
        if self.token_track != TINY_DEV_TOKEN_TRACK:
            raise ValueError("TinyDev detector evidence must use original generation token IDs")
        if self.prompt_boundary_mode != TINY_DEV_PROMPT_BOUNDARY_MODE:
            raise ValueError("TinyDev detector evidence must use continuation-only prompt boundaries")
        if self.headline_fprs != TINY_DEV_HEADLINE_FPRS:
            raise ValueError("headline_fprs do not match the frozen 5% and 1% profile")
        if self.primary_fpr != TINY_DEV_PRIMARY_FPR:
            raise ValueError("primary_fpr must be 1%")
        if self.baseline_interpretability_floor != TINY_DEV_BASELINE_INTERPRETABILITY_FLOOR:
            raise ValueError("baseline interpretability floor must be 80%")
        if self.scientific_status != TINY_DEV_DETECTOR_STATUS:
            raise ValueError("TinyDev detector evidence must remain development-only")
        if not isinstance(self.family_evidence, tuple):
            raise TypeError("family_evidence must be a tuple")
        if tuple(value.detector_family for value in self.family_evidence) != (
            DetectorFamily.MEAN,
            DetectorFamily.WEIGHTED_MEAN,
        ):
            raise ValueError("TinyDev detector artifact must contain Mean then Weighted Mean evidence")
        for family in self.family_evidence:
            if family.calibration_evidence[0].adapter_id != self.adapter_id:
                raise ValueError("detector family adapter identity does not match artifact")
            if family.calibration_evidence[0].adapter_algorithm_version != self.adapter_algorithm_version:
                raise ValueError("detector family adapter version does not match artifact")
            if family.calibration_evidence[0].adapter_config_hash != self.adapter_config_hash:
                raise ValueError("detector family adapter configuration does not match artifact")
            if family.calibration_evidence[0].source_id != self.adapter_source_id:
                raise ValueError("detector family adapter source does not match artifact")
            if family.calibration_evidence[0].source_commit != self.adapter_source_commit:
                raise ValueError("detector family adapter source commit does not match artifact")
        if self.artifact_hash != sha256_json(self._payload()):
            raise ValueError("artifact_hash does not match TinyDev detector evidence artifact")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "watermark_config_hash": self.watermark_config_hash,
            "adapter_id": self.adapter_id,
            "adapter_algorithm_version": self.adapter_algorithm_version,
            "adapter_config_hash": self.adapter_config_hash,
            "adapter_source_id": self.adapter_source_id,
            "adapter_source_commit": self.adapter_source_commit,
            "token_track": self.token_track,
            "prompt_boundary_mode": self.prompt_boundary_mode,
            "headline_fprs": self.headline_fprs,
            "primary_fpr": self.primary_fpr,
            "baseline_interpretability_floor": self.baseline_interpretability_floor,
            "family_evidence": self.family_evidence,
            "scientific_status": self.scientific_status,
        }


def _sample_populations(artifact: TinyDevCorpusArtifact):
    calibration = tuple(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
        and sample.label is WatermarkLabel.UNWATERMARKED
    )
    attack = tuple(
        sample
        for sample in artifact.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
    )
    if len(calibration) != 100 or len(attack) != 8:
        raise TinyDevDetectorEvidenceError("TinyDev corpus does not match the frozen detector-evidence populations")
    return calibration, attack


def _score_samples(samples, adapter: WatermarkAdapter, evidence_builder):
    rows: list[UncalibratedDetectorEvidence] = []
    for sample in samples:
        eos_token_id = sample.model.eos_token_id
        if eos_token_id is None:
            raise TinyDevDetectorEvidenceError("TinyDev model identity must define eos_token_id")
        batch = build_native_observations(
            sample.sample_id,
            sample.generation_tokens.continuation_token_ids,
            eos_token_id,
            adapter,
        )
        rows.append(evidence_builder(batch))
    return tuple(sorted(rows, key=lambda value: value.sample_id))


def _threshold_evaluation(
    target_fpr: float,
    bundle: CalibrationBundle,
    attack_evidence: tuple[UncalibratedDetectorEvidence, ...],
    attack_labels: dict[str, WatermarkLabel],
) -> TinyDevThresholdEvaluation:
    calibrated = tuple(
        sorted(
            (apply_calibration(value, bundle, target_fpr) for value in attack_evidence),
            key=lambda value: value.sample_id,
        )
    )
    positives = tuple(value for value in calibrated if attack_labels[value.sample_id] is WatermarkLabel.WATERMARKED)
    negatives = tuple(value for value in calibrated if attack_labels[value.sample_id] is WatermarkLabel.UNWATERMARKED)
    baseline = evaluate_pristine_baseline(
        positives,
        interpretability_floor=TINY_DEV_BASELINE_INTERPRETABILITY_FLOOR,
    )
    threshold = next(value for value in bundle.thresholds if value.target_fpr == target_fpr)
    negative_detected = sum(value.decision for value in negatives)
    interval = exact_binomial_interval(negative_detected, len(negatives))
    payload = {
        "algorithm_version": TINY_DEV_THRESHOLD_EVALUATION_ALGORITHM_VERSION,
        "target_fpr": target_fpr,
        "threshold_hash": threshold.threshold_hash,
        "threshold_value": threshold.value,
        "achieved_calibration_fpr": threshold.achieved_fpr,
        "calibration_fpr_interval": threshold.fpr_interval,
        "positive_results": positives,
        "negative_results": negatives,
        "pristine_baseline": baseline,
        "attack_negative_detected_count": negative_detected,
        "attack_negative_fpr": negative_detected / len(negatives),
        "attack_negative_fpr_interval": interval,
    }
    return TinyDevThresholdEvaluation(
        algorithm_version=TINY_DEV_THRESHOLD_EVALUATION_ALGORITHM_VERSION,
        target_fpr=target_fpr,
        threshold_hash=threshold.threshold_hash,
        threshold_value=threshold.value,
        achieved_calibration_fpr=threshold.achieved_fpr,
        calibration_fpr_interval=threshold.fpr_interval,
        positive_results=positives,
        negative_results=negatives,
        pristine_baseline=baseline,
        attack_negative_detected_count=negative_detected,
        attack_negative_fpr=negative_detected / len(negatives),
        attack_negative_fpr_interval=interval,
        evaluation_hash=sha256_json(payload),
    )


def _family_evidence(
    family: DetectorFamily,
    calibration_samples,
    attack_samples,
    adapter: WatermarkAdapter,
) -> TinyDevDetectorFamilyEvidence:
    builder = mean_evidence if family is DetectorFamily.MEAN else weighted_mean_evidence
    calibration_rows = _score_samples(calibration_samples, adapter, builder)
    attack_rows = _score_samples(attack_samples, adapter, builder)
    scope = CalibrationScope.create(
        corpus_id="tiny-dev-real",
        population_id="threshold-calibration-unwatermarked",
        length_policy_id="generated-64",
        token_track=TINY_DEV_TOKEN_TRACK,
        prompt_boundary_mode=TINY_DEV_PROMPT_BOUNDARY_MODE,
    )
    bundle = calibrate_detector(
        calibration_rows,
        scope,
        target_fprs=TINY_DEV_HEADLINE_FPRS,
    )
    attack_labels = {sample.sample_id: sample.label for sample in attack_samples}
    evaluations = tuple(
        _threshold_evaluation(target, bundle, attack_rows, attack_labels)
        for target in TINY_DEV_HEADLINE_FPRS
    )
    payload = {
        "algorithm_version": TINY_DEV_DETECTOR_FAMILY_ALGORITHM_VERSION,
        "detector_family": family.value,
        "calibration_evidence": calibration_rows,
        "attack_evidence": attack_rows,
        "calibration_bundle": bundle,
        "threshold_evaluations": evaluations,
    }
    return TinyDevDetectorFamilyEvidence(
        algorithm_version=TINY_DEV_DETECTOR_FAMILY_ALGORITHM_VERSION,
        detector_family=family,
        calibration_evidence=calibration_rows,
        attack_evidence=attack_rows,
        calibration_bundle=bundle,
        threshold_evaluations=evaluations,
        family_hash=sha256_json(payload),
    )


def build_tiny_dev_detector_evidence(
    artifact: TinyDevCorpusArtifact,
    adapter: WatermarkAdapter,
    *,
    expected_watermark_config_hash: str,
) -> TinyDevDetectorEvidenceArtifact:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(adapter, WatermarkAdapter):
        raise TypeError("adapter must satisfy the WatermarkAdapter protocol")
    require_sha256("expected_watermark_config_hash", expected_watermark_config_hash)
    if artifact.watermark_condition_hash != artifact.manifest.samples[0].watermark.condition_hash:
        raise TinyDevDetectorEvidenceError("TinyDev artifact watermark condition does not match corpus samples")
    watermark_hashes = {sample.watermark.watermark_config_hash for sample in artifact.manifest.samples}
    if watermark_hashes != {expected_watermark_config_hash}:
        raise TinyDevDetectorEvidenceError("TinyDev corpus watermark configuration does not match the scoring adapter contract")
    if any(sample.generation_realized_length != 64 for sample in artifact.manifest.samples):
        raise TinyDevDetectorEvidenceError("TinyDev detector evidence requires exact 64-token generation tracks")
    calibration_samples, attack_samples = _sample_populations(artifact)
    families = tuple(
        _family_evidence(family, calibration_samples, attack_samples, adapter)
        for family in (DetectorFamily.MEAN, DetectorFamily.WEIGHTED_MEAN)
    )
    source_pin = adapter.source_pin
    payload = {
        "algorithm_version": TINY_DEV_DETECTOR_EVIDENCE_ALGORITHM_VERSION,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "corpus_manifest_hash": artifact.manifest.manifest_hash,
        "watermark_config_hash": expected_watermark_config_hash,
        "adapter_id": adapter.adapter_id,
        "adapter_algorithm_version": adapter.algorithm_version,
        "adapter_config_hash": adapter.configuration_fingerprint(),
        "adapter_source_id": source_pin.source_id,
        "adapter_source_commit": source_pin.commit,
        "token_track": TINY_DEV_TOKEN_TRACK,
        "prompt_boundary_mode": TINY_DEV_PROMPT_BOUNDARY_MODE,
        "headline_fprs": TINY_DEV_HEADLINE_FPRS,
        "primary_fpr": TINY_DEV_PRIMARY_FPR,
        "baseline_interpretability_floor": TINY_DEV_BASELINE_INTERPRETABILITY_FLOOR,
        "family_evidence": families,
        "scientific_status": TINY_DEV_DETECTOR_STATUS,
    }
    return TinyDevDetectorEvidenceArtifact(
        algorithm_version=TINY_DEV_DETECTOR_EVIDENCE_ALGORITHM_VERSION,
        tiny_dev_artifact_hash=artifact.artifact_hash,
        corpus_manifest_hash=artifact.manifest.manifest_hash,
        watermark_config_hash=expected_watermark_config_hash,
        adapter_id=adapter.adapter_id,
        adapter_algorithm_version=adapter.algorithm_version,
        adapter_config_hash=adapter.configuration_fingerprint(),
        adapter_source_id=source_pin.source_id,
        adapter_source_commit=source_pin.commit,
        token_track=TINY_DEV_TOKEN_TRACK,
        prompt_boundary_mode=TINY_DEV_PROMPT_BOUNDARY_MODE,
        headline_fprs=TINY_DEV_HEADLINE_FPRS,
        primary_fpr=TINY_DEV_PRIMARY_FPR,
        baseline_interpretability_floor=TINY_DEV_BASELINE_INTERPRETABILITY_FLOOR,
        family_evidence=families,
        scientific_status=TINY_DEV_DETECTOR_STATUS,
        artifact_hash=sha256_json(payload),
    )


def primary_baseline_statuses(
    artifact: TinyDevDetectorEvidenceArtifact,
) -> tuple[tuple[DetectorFamily, BaselineStatus], ...]:
    if not isinstance(artifact, TinyDevDetectorEvidenceArtifact):
        raise TypeError("artifact must be a TinyDevDetectorEvidenceArtifact")
    output = []
    for family in artifact.family_evidence:
        evaluation = next(
            value for value in family.threshold_evaluations
            if value.target_fpr == TINY_DEV_PRIMARY_FPR
        )
        output.append((family.detector_family, evaluation.pristine_baseline.status))
    return tuple(output)
