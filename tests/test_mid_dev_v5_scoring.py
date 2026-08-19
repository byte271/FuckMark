from dataclasses import replace

import pytest

from fuckmark.detector_calibration import PRIMARY_TARGET_FPR
from fuckmark.detectors import ComparisonOperator
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_CONFIDENCE_LEVEL,
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    FrozenCalibrationThresholdRecord,
)
from fuckmark.experiments.mid_dev_v5_scoring import MidDevV5ScoreValue
from fuckmark.hashing import sha256_json, sha256_text


def _threshold_record() -> FrozenCalibrationThresholdRecord:
    interval = exact_binomial_interval(10, 1000, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
        "regime_id": "eligible-100-199",
        "calibration_regime_hash": sha256_text("regime"),
        "regime_decision_hash": sha256_text("decision"),
        "select_manifest_hash": sha256_text("select-manifest"),
        "select_count": 1000,
        "calibration_bundle_hash": sha256_text("bundle"),
        "detector_identity_hash": sha256_text("detector"),
        "threshold_hash": sha256_text("threshold"),
        "threshold_value": 0.25,
        "target_fpr": PRIMARY_TARGET_FPR,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": 10,
        "select_empirical_fpr": 0.01,
        "select_fpr_interval": interval,
        "length_policy_id": "vnext-actual-opportunity-test",
    }
    return FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))


def test_v5_score_value_binds_frozen_threshold_and_margin():
    record = _threshold_record()
    value = MidDevV5ScoreValue.create(
        text_hash=sha256_text("text"),
        token_hash=sha256_text("tokens"),
        eligibility_mask_hash=sha256_text("mask"),
        eligible_observation_count=123,
        record=record,
        raw_score=0.30,
        detector_identity_hash=record.detector_identity_hash,
    )
    assert value.regime_id == record.regime_id
    assert value.calibration_regime_hash == record.calibration_regime_hash
    assert value.threshold_record_hash == record.record_hash
    assert value.threshold_hash == record.threshold_hash
    assert value.threshold_value == 0.25
    assert value.raw_score == 0.30
    assert value.margin == pytest.approx(0.05)
    assert value.detected is True
    assert value.detector_identity_hash == record.detector_identity_hash


def test_v5_score_value_rejects_margin_and_detection_tampering():
    record = _threshold_record()
    value = MidDevV5ScoreValue.create(
        text_hash=sha256_text("text"),
        token_hash=sha256_text("tokens"),
        eligibility_mask_hash=sha256_text("mask"),
        eligible_observation_count=123,
        record=record,
        raw_score=0.20,
        detector_identity_hash=record.detector_identity_hash,
    )
    assert value.detected is False
    with pytest.raises(ValueError, match="margin"):
        replace(value, margin=0.0)
    with pytest.raises(ValueError, match="detected"):
        replace(value, detected=True)


def test_v5_score_value_requires_positive_eligible_observations():
    record = _threshold_record()
    with pytest.raises(ValueError, match="positive eligible"):
        MidDevV5ScoreValue.create(
            text_hash=sha256_text("text"),
            token_hash=sha256_text("tokens"),
            eligibility_mask_hash=sha256_text("mask"),
            eligible_observation_count=0,
            record=record,
            raw_score=0.20,
            detector_identity_hash=record.detector_identity_hash,
        )
