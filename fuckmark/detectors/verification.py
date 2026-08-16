from __future__ import annotations

from ..native_observations import NativeObservationBatch
from .calibration_apply import apply_calibration
from .calibration_types import CalibratedDetectorResult, CalibrationBundle
from .mean import MEAN_ALGORITHM_VERSION, WEIGHTED_MEAN_ALGORITHM_VERSION, _evidence
from .types import DetectorFamily, UncalibratedDetectorEvidence


class DetectorArtifactVerificationError(ValueError):
    pass


def verify_uncalibrated_detector_evidence(
    batch: NativeObservationBatch,
    evidence: UncalibratedDetectorEvidence,
) -> None:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(evidence, UncalibratedDetectorEvidence):
        raise TypeError("evidence must be UncalibratedDetectorEvidence")
    if evidence.detector_family is DetectorFamily.MEAN:
        algorithm_version = MEAN_ALGORITHM_VERSION
        weights = (1.0,) * batch.depth
    elif evidence.detector_family is DetectorFamily.WEIGHTED_MEAN:
        algorithm_version = WEIGHTED_MEAN_ALGORITHM_VERSION
        weights = evidence.normalized_weights
    else:
        raise DetectorArtifactVerificationError(
            "detector evidence replay is not implemented for this detector family"
        )
    expected = _evidence(
        batch,
        evidence.detector_family,
        algorithm_version,
        weights,
    )
    if evidence != expected:
        raise DetectorArtifactVerificationError(
            "uncalibrated detector evidence does not replay exactly from the supplied observation batch"
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
