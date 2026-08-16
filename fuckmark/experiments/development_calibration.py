from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..corpus import CorpusSplit, TinyDevCorpusArtifact, WatermarkLabel
from ..detectors import CalibrationBundle, CalibrationScope, ComparisonOperator, UncalibratedDetectorEvidence, calibrate_detector
from ..hashing import sha256_json


DEVELOPMENT_CALIBRATION_BINDING_VERSION = "development-calibration-binding-v1"
DEVELOPMENT_TARGET_FPRS = (0.05, 0.01)
DEVELOPMENT_CALIBRATION_POPULATION_ID = "tiny-dev-threshold-calibration-unwatermarked-v1"
DEVELOPMENT_LENGTH_POLICY_ID = "target-64-realized-unpadded-v1"
DEVELOPMENT_TOKEN_TRACK = "generation"
DEVELOPMENT_PROMPT_BOUNDARY_MODE = "continuation_only"


class DevelopmentCalibrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DevelopmentCalibrationBinding:
    algorithm_version: str
    corpus_id: str
    tiny_dev_artifact_hash: str
    calibration_sample_ids: tuple[str, ...]
    calibration_sample_id_hash: str
    calibration_bundle: CalibrationBundle
    binding_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != DEVELOPMENT_CALIBRATION_BINDING_VERSION:
            raise ValueError("unsupported development calibration binding version")
        require_clean_string("corpus_id", self.corpus_id)
        require_sha256("tiny_dev_artifact_hash", self.tiny_dev_artifact_hash)
        if not isinstance(self.calibration_sample_ids, tuple):
            raise TypeError("calibration_sample_ids must be a tuple")
        if self.calibration_sample_ids != tuple(sorted(set(self.calibration_sample_ids))):
            raise ValueError("calibration_sample_ids must be unique and canonically ordered")
        if len(self.calibration_sample_ids) != 100:
            raise ValueError("development calibration binding must contain exactly 100 negative sample IDs")
        for sample_id in self.calibration_sample_ids:
            require_clean_string("calibration sample ID", sample_id)
        require_sha256("calibration_sample_id_hash", self.calibration_sample_id_hash)
        if self.calibration_sample_id_hash != sha256_json(self.calibration_sample_ids):
            raise ValueError("calibration_sample_id_hash does not match sample IDs")
        if not isinstance(self.calibration_bundle, CalibrationBundle):
            raise TypeError("calibration_bundle must be a CalibrationBundle")
        if self.calibration_bundle.negative_count != len(self.calibration_sample_ids):
            raise ValueError("calibration bundle negative count does not match bound sample IDs")
        if self.calibration_bundle.scope.corpus_id != self.corpus_id:
            raise ValueError("calibration scope corpus_id does not match binding")
        if self.calibration_bundle.scope.population_id != DEVELOPMENT_CALIBRATION_POPULATION_ID:
            raise ValueError("calibration scope population does not match development policy")
        if self.calibration_bundle.scope.length_policy_id != DEVELOPMENT_LENGTH_POLICY_ID:
            raise ValueError("calibration scope length policy does not match development policy")
        if self.calibration_bundle.scope.token_track != DEVELOPMENT_TOKEN_TRACK:
            raise ValueError("calibration scope token track does not match development policy")
        if self.calibration_bundle.scope.prompt_boundary_mode != DEVELOPMENT_PROMPT_BOUNDARY_MODE:
            raise ValueError("calibration scope prompt boundary does not match development policy")
        targets = tuple(threshold.target_fpr for threshold in self.calibration_bundle.thresholds)
        if targets != DEVELOPMENT_TARGET_FPRS:
            raise ValueError("development calibration bundle must freeze 5% and 1% target FPR thresholds")
        if self.calibration_bundle.comparison_operator is not ComparisonOperator.GREATER_THAN_OR_EQUAL:
            raise ValueError("development calibration must use the frozen greater-than-or-equal operator")
        require_sha256("binding_hash", self.binding_hash)
        if self.binding_hash != sha256_json(self._payload()):
            raise ValueError("binding_hash does not match development calibration binding")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_id": self.corpus_id,
            "tiny_dev_artifact_hash": self.tiny_dev_artifact_hash,
            "calibration_sample_id_hash": self.calibration_sample_id_hash,
            "calibration_bundle_hash": self.calibration_bundle.bundle_hash,
        }


def _expected_calibration_sample_ids(artifact: TinyDevCorpusArtifact) -> tuple[str, ...]:
    return tuple(
        sorted(
            sample.sample_id
            for sample in artifact.manifest.samples
            if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
            and sample.label is WatermarkLabel.UNWATERMARKED
        )
    )


def calibrate_tiny_dev_detector(
    artifact: TinyDevCorpusArtifact,
    negative_evidence: Sequence[UncalibratedDetectorEvidence],
) -> DevelopmentCalibrationBinding:
    if not isinstance(artifact, TinyDevCorpusArtifact):
        raise TypeError("artifact must be a TinyDevCorpusArtifact")
    if not isinstance(negative_evidence, Sequence) or isinstance(negative_evidence, (str, bytes, bytearray)):
        raise TypeError("negative_evidence must be a sequence")
    evidence = tuple(negative_evidence)
    if any(not isinstance(value, UncalibratedDetectorEvidence) for value in evidence):
        raise TypeError("negative_evidence must contain UncalibratedDetectorEvidence values")
    expected_ids = _expected_calibration_sample_ids(artifact)
    actual_ids = tuple(sorted(value.sample_id for value in evidence))
    if actual_ids != expected_ids:
        missing = tuple(sorted(set(expected_ids) - set(actual_ids)))
        unexpected = tuple(sorted(set(actual_ids) - set(expected_ids)))
        raise DevelopmentCalibrationError(
            f"negative evidence does not exactly match the tiny-dev calibration split; missing={missing}, unexpected={unexpected}"
        )
    scope = CalibrationScope.create(
        corpus_id=artifact.manifest.corpus_id,
        population_id=DEVELOPMENT_CALIBRATION_POPULATION_ID,
        length_policy_id=DEVELOPMENT_LENGTH_POLICY_ID,
        token_track=DEVELOPMENT_TOKEN_TRACK,
        prompt_boundary_mode=DEVELOPMENT_PROMPT_BOUNDARY_MODE,
    )
    bundle = calibrate_detector(
        evidence,
        scope,
        target_fprs=DEVELOPMENT_TARGET_FPRS,
        comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
        confidence_level=0.95,
    )
    sample_id_hash = sha256_json(expected_ids)
    payload = {
        "algorithm_version": DEVELOPMENT_CALIBRATION_BINDING_VERSION,
        "corpus_id": artifact.manifest.corpus_id,
        "tiny_dev_artifact_hash": artifact.artifact_hash,
        "calibration_sample_id_hash": sample_id_hash,
        "calibration_bundle_hash": bundle.bundle_hash,
    }
    return DevelopmentCalibrationBinding(
        DEVELOPMENT_CALIBRATION_BINDING_VERSION,
        artifact.manifest.corpus_id,
        artifact.artifact_hash,
        expected_ids,
        sample_id_hash,
        bundle,
        sha256_json(payload),
    )
