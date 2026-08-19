from __future__ import annotations

from ..corpus.mid_dev_calibration import (
    MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
    MidDevCalibrationArtifact,
)
from ..corpus.schema import CorpusSplit, WatermarkLabel
from ..detector_calibration import PRIMARY_TARGET_FPR, text_only_weighted_evidence
from ..detectors import CalibrationScope, ComparisonOperator, calibrate_detector
from ..hashing import sha256_json
from .mid_dev_scored_schema import MidDevLengthCalibrationBinding


def build_mid_dev_length_calibrations(
    artifact: MidDevCalibrationArtifact,
    adapter,
) -> tuple[MidDevLengthCalibrationBinding, ...]:
    output = []
    for target_length in artifact.target_lengths:
        negatives = tuple(
            sorted(
                (
                    sample
                    for sample in artifact.manifest.samples
                    if sample.split is CorpusSplit.THRESHOLD_CALIBRATION
                    and sample.label is WatermarkLabel.UNWATERMARKED
                    and sample.target_length == target_length
                ),
                key=lambda value: value.sample_id,
            )
        )
        if len(negatives) != MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
            raise ValueError("MidDev length calibration requires exactly 100 negatives per stratum")
        evidence = tuple(text_only_weighted_evidence(sample, adapter) for sample in negatives)
        length_policy_id = f"target-{target_length}-text-only-unpadded-v1"
        scope = CalibrationScope.create(
            corpus_id=artifact.manifest.corpus_id,
            population_id=f"mid-dev-threshold-calibration-unwatermarked-{target_length}-v1",
            length_policy_id=length_policy_id,
            token_track="text_only",
            prompt_boundary_mode="continuation_only",
        )
        bundle = calibrate_detector(
            evidence,
            scope,
            target_fprs=(0.05, PRIMARY_TARGET_FPR),
            comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
            confidence_level=0.95,
        )
        threshold = next(
            value for value in bundle.thresholds if value.target_fpr == PRIMARY_TARGET_FPR
        )
        payload = {
            "algorithm_version": "mid-dev-length-calibration-binding-v1",
            "target_length": target_length,
            "calibration_bundle_hash": bundle.bundle_hash,
            "detector_identity_hash": bundle.detector_identity.identity_hash,
            "threshold_hash": threshold.threshold_hash,
            "threshold_value": threshold.value,
            "target_fpr": PRIMARY_TARGET_FPR,
            "calibration_count": len(negatives),
            "length_policy_id": length_policy_id,
        }
        output.append(
            MidDevLengthCalibrationBinding(
                target_length,
                bundle.bundle_hash,
                bundle.detector_identity.identity_hash,
                threshold.threshold_hash,
                threshold.value,
                PRIMARY_TARGET_FPR,
                len(negatives),
                length_policy_id,
                sha256_json(payload),
            )
        )
    return tuple(sorted(output, key=lambda value: value.target_length))
