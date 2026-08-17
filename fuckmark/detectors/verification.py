from __future__ import annotations

from collections.abc import Sequence

from ..native_observations import NativeObservationBatch
from .bayesian_artifacts import (
    BayesianReadinessArtifactBundle,
    verify_bayesian_readiness_artifact_bundle,
)
from .bayesian_calibration import verify_bayesian_calibration_evidence
from .calibration_apply import apply_calibration
from .calibration_baseline import evaluate_pristine_baseline
from .calibration_build import calibrate_detector
from .calibration_types import (
    CalibratedDetectorResult,
    CalibrationBundle,
    PristineBaselineSummary,
)
from .mean import MEAN_ALGORITHM_VERSION, WEIGHTED_MEAN_ALGORITHM_VERSION, _evidence
from .types import DetectorFamily, UncalibratedDetectorEvidence


class DetectorArtifactVerificationError(ValueError):
    pass


def verify_uncalibrated_detector_evidence(
    batch: NativeObservationBatch,
    evidence: UncalibratedDetectorEvidence,
    *,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> None:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(evidence, UncalibratedDetectorEvidence):
        raise TypeError("evidence must be UncalibratedDetectorEvidence")
    if evidence.detector_family is DetectorFamily.MEAN:
        if bayesian_artifacts is not None:
            raise DetectorArtifactVerificationError(
                "Mean detector evidence cannot carry Bayesian readiness artifacts"
            )
        algorithm_version = MEAN_ALGORITHM_VERSION
        weights = (1.0,) * batch.depth
        expected = _evidence(
            batch,
            evidence.detector_family,
            algorithm_version,
            weights,
        )
    elif evidence.detector_family is DetectorFamily.WEIGHTED_MEAN:
        if bayesian_artifacts is not None:
            raise DetectorArtifactVerificationError(
                "Weighted Mean detector evidence cannot carry Bayesian readiness artifacts"
            )
        algorithm_version = WEIGHTED_MEAN_ALGORITHM_VERSION
        weights = evidence.normalized_weights
        expected = _evidence(
            batch,
            evidence.detector_family,
            algorithm_version,
            weights,
        )
    elif evidence.detector_family is DetectorFamily.BAYESIAN:
        if bayesian_artifacts is None:
            raise DetectorArtifactVerificationError(
                "Bayesian detector evidence replay requires the complete readiness artifact bundle"
            )
        try:
            verify_bayesian_readiness_artifact_bundle(bayesian_artifacts)
            verify_bayesian_calibration_evidence(
                evidence,
                batch,
                bayesian_artifacts.checkpoint,
                bayesian_artifacts.readiness,
            )
        except Exception as error:
            raise DetectorArtifactVerificationError(
                "Bayesian detector evidence does not replay from the supplied readiness artifacts"
            ) from error
        return
    else:
        raise DetectorArtifactVerificationError(
            "detector evidence replay is not implemented for this detector family"
        )
    if evidence != expected:
        raise DetectorArtifactVerificationError(
            "uncalibrated detector evidence does not replay exactly from the supplied observation batch"
        )


def verify_calibration_bundle(
    negative_evidence: Sequence[UncalibratedDetectorEvidence],
    bundle: CalibrationBundle,
) -> None:
    if not isinstance(bundle, CalibrationBundle):
        raise TypeError("bundle must be a CalibrationBundle")
    expected = calibrate_detector(
        negative_evidence,
        bundle.scope,
        target_fprs=tuple(threshold.target_fpr for threshold in bundle.thresholds),
        comparison_operator=bundle.comparison_operator,
        confidence_level=bundle.confidence_level,
    )
    if bundle != expected:
        raise DetectorArtifactVerificationError(
            "calibration bundle does not replay exactly from the supplied negative evidence"
        )


def verify_calibrated_detector_result(
    evidence: UncalibratedDetectorEvidence,
    bundle: CalibrationBundle,
    result: CalibratedDetectorResult,
) -> None:
    if not isinstance(evidence, UncalibratedDetectorEvidence):
        raise TypeError("evidence must be UncalibratedDetectorEvidence")
    if not isinstance(bundle, CalibrationBundle):
        raise TypeError("bundle must be a CalibrationBundle")
    if not isinstance(result, CalibratedDetectorResult):
        raise TypeError("result must be a CalibratedDetectorResult")
    expected = apply_calibration(evidence, bundle, result.target_fpr)
    if result != expected:
        raise DetectorArtifactVerificationError(
            "calibrated detector result does not replay exactly from the supplied evidence and calibration bundle"
        )


def verify_pristine_baseline_summary(
    results: Sequence[CalibratedDetectorResult],
    summary: PristineBaselineSummary,
) -> None:
    if not isinstance(summary, PristineBaselineSummary):
        raise TypeError("summary must be a PristineBaselineSummary")
    expected = evaluate_pristine_baseline(
        results,
        interpretability_floor=summary.interpretability_floor,
        confidence_level=summary.tpr_interval.confidence_level,
    )
    if summary != expected:
        raise DetectorArtifactVerificationError(
            "pristine baseline summary does not replay exactly from the supplied calibrated results"
        )
