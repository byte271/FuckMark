from __future__ import annotations

import ast
import inspect

import pytest

from fuckmark.detectors import ComparisonOperator
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    CalibrationAuditArtifact,
    FrozenCalibrationThresholdRecord,
    audit_frozen_calibration_threshold_registry,
    build_frozen_calibration_threshold_registry,
)
from fuckmark.hashing import sha256_json


def _threshold_payload(false_positives: int = 10, count: int = 1000):
    return {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
        "regime_id": "nominal-128",
        "calibration_regime_hash": "a" * 64,
        "regime_decision_hash": "b" * 64,
        "select_manifest_hash": "c" * 64,
        "select_count": count,
        "calibration_bundle_hash": "d" * 64,
        "detector_identity_hash": "e" * 64,
        "threshold_hash": "f" * 64,
        "threshold_value": 0.5,
        "target_fpr": 0.01,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": false_positives,
        "select_empirical_fpr": false_positives / count,
        "select_fpr_interval": exact_binomial_interval(false_positives, count, 0.95),
        "length_policy_id": "vnext-nominal-test",
    }


def test_threshold_builder_has_no_cal_audit_input() -> None:
    parameters = inspect.signature(build_frozen_calibration_threshold_registry).parameters
    assert "audit_samples" not in parameters
    assert "audit_manifest" not in parameters


def test_audit_path_cannot_recalibrate_threshold() -> None:
    tree = ast.parse(inspect.getsource(audit_frozen_calibration_threshold_registry))
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "calibrate_detector" not in calls


def test_frozen_threshold_record_reproduces_exact_select_interval() -> None:
    payload = _threshold_payload()
    record = FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))
    assert record.select_fpr_interval == exact_binomial_interval(10, 1000, 0.95)
    bad = dict(payload)
    bad["select_fpr_interval"] = exact_binomial_interval(9, 1000, 0.95)
    with pytest.raises(ValueError):
        FrozenCalibrationThresholdRecord(**bad, record_hash=sha256_json(bad))


def test_frozen_threshold_record_rejects_subminimum_select_count() -> None:
    payload = _threshold_payload(false_positives=9, count=999)
    with pytest.raises(ValueError):
        FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))


def test_calibration_audit_artifact_reproduces_both_exact_intervals() -> None:
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
        "model_tokenizer_identity_hash": "1" * 64,
        "detector_identity_hash": "2" * 64,
        "calibration_regime_hash": "3" * 64,
        "regime_id": "nominal-128",
        "regime_decision_hash": "4" * 64,
        "select_manifest_hash": "5" * 64,
        "select_count": 1000,
        "threshold_hash": "6" * 64,
        "threshold_value": 0.5,
        "target_fpr": 0.01,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": 10,
        "select_fpr_interval": exact_binomial_interval(10, 1000, 0.95),
        "audit_manifest_hash": "7" * 64,
        "audit_count": 1000,
        "audit_false_positive_count": 12,
        "audit_fpr": 0.012,
        "audit_fpr_interval": exact_binomial_interval(12, 1000, 0.95),
        "length_policy_id": "vnext-nominal-test",
    }
    artifact = CalibrationAuditArtifact(**payload, artifact_hash=sha256_json(payload))
    assert artifact.audit_fpr_interval == exact_binomial_interval(12, 1000, 0.95)
