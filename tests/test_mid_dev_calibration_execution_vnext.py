from __future__ import annotations

import ast
from pathlib import Path

from fuckmark.config import canonical_json_text
from fuckmark.detectors import ComparisonOperator
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
    CalibrationAuditArtifact,
    FrozenCalibrationThresholdRecord,
    FrozenCalibrationThresholdRegistry,
)
from fuckmark.experiments.mid_dev_calibration_audit_registry import (
    CALIBRATION_AUDIT_UNSTABLE_REASON,
    build_mid_dev_calibration_audit_registry,
)
from fuckmark.experiments.mid_dev_calibration_audit_registry_io import (
    parse_mid_dev_calibration_audit_registry_json,
)
from fuckmark.hashing import sha256_json


def _threshold_record() -> FrozenCalibrationThresholdRecord:
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
        "regime_id": "nominal-128",
        "calibration_regime_hash": "1" * 64,
        "regime_decision_hash": "2" * 64,
        "select_manifest_hash": "3" * 64,
        "select_count": 1000,
        "calibration_bundle_hash": "4" * 64,
        "detector_identity_hash": "5" * 64,
        "threshold_hash": "6" * 64,
        "threshold_value": 0.5,
        "target_fpr": 0.01,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": 10,
        "select_empirical_fpr": 0.01,
        "select_fpr_interval": exact_binomial_interval(10, 1000, 0.95),
        "length_policy_id": "vnext-nominal-test",
    }
    return FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))


def _threshold_registry(record: FrozenCalibrationThresholdRecord) -> FrozenCalibrationThresholdRegistry:
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        "regime_decision_hash": record.regime_decision_hash,
        "opportunity_audit_hash": "7" * 64,
        "select_manifest_hash": record.select_manifest_hash,
        "detector_identity_hash": record.detector_identity_hash,
        "record_hashes": (record.record_hash,),
    }
    return FrozenCalibrationThresholdRegistry(
        MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        record.regime_decision_hash,
        "7" * 64,
        record.select_manifest_hash,
        record.detector_identity_hash,
        (record,),
        sha256_json(payload),
    )


def _audit_artifact(record: FrozenCalibrationThresholdRecord, false_positives: int) -> CalibrationAuditArtifact:
    count = 1000
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
        "model_tokenizer_identity_hash": "8" * 64,
        "detector_identity_hash": record.detector_identity_hash,
        "calibration_regime_hash": record.calibration_regime_hash,
        "regime_id": record.regime_id,
        "regime_decision_hash": record.regime_decision_hash,
        "select_manifest_hash": record.select_manifest_hash,
        "select_count": record.select_count,
        "threshold_hash": record.threshold_hash,
        "threshold_value": record.threshold_value,
        "target_fpr": record.target_fpr,
        "comparison_operator": record.comparison_operator,
        "select_false_positive_count": record.select_false_positive_count,
        "select_fpr_interval": record.select_fpr_interval,
        "audit_manifest_hash": "9" * 64,
        "audit_count": count,
        "audit_false_positive_count": false_positives,
        "audit_fpr": false_positives / count,
        "audit_fpr_interval": exact_binomial_interval(false_positives, count, 0.95),
        "length_policy_id": record.length_policy_id,
    }
    return CalibrationAuditArtifact(**payload, artifact_hash=sha256_json(payload))


def _python_source(path: str) -> tuple[str, ast.AST]:
    source = Path(path).read_text(encoding="utf-8")
    return source, ast.parse(source)


def test_d2_passes_only_when_target_fpr_is_inside_every_audit_exact_interval() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    audit = _audit_artifact(record, 10)
    result = build_mid_dev_calibration_audit_registry(registry, (audit,))
    assert audit.audit_fpr_interval.lower <= 0.01 <= audit.audit_fpr_interval.upper
    assert result.consistency_pass is True
    assert result.unstable_regime_ids == ()
    assert result.reason_code is None


def test_d2_blocks_threshold_crossing_interpretation_when_audit_is_unstable() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    audit = _audit_artifact(record, 40)
    result = build_mid_dev_calibration_audit_registry(registry, (audit,))
    assert not (audit.audit_fpr_interval.lower <= 0.01 <= audit.audit_fpr_interval.upper)
    assert result.consistency_pass is False
    assert result.unstable_regime_ids == (record.regime_id,)
    assert result.reason_code == CALIBRATION_AUDIT_UNSTABLE_REASON


def test_calibration_audit_registry_strict_io_round_trip() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    value = build_mid_dev_calibration_audit_registry(registry, (_audit_artifact(record, 10),))
    text = canonical_json_text(value) + "\n"
    parsed = parse_mid_dev_calibration_audit_registry_json(text)
    assert parsed.registry_hash == value.registry_hash
    assert parsed.artifacts[0].artifact_hash == value.artifacts[0].artifact_hash


def test_threshold_cli_is_cal_select_only() -> None:
    source, tree = _python_source("fuckmark/mid_dev_calibration_threshold_hf.py")
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "--select-json" in constants
    assert "--audit-json" not in constants
    assert "audit_frozen_calibration_threshold_registry" not in source
    assert "CalibrationRole.AUDIT" not in source


def test_audit_cli_never_recalibrates_or_builds_threshold() -> None:
    source, tree = _python_source("fuckmark/mid_dev_calibration_audit_hf.py")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "calibrate_detector" not in names
    assert "build_frozen_calibration_threshold_registry" not in names
    assert "threshold_recalibration_performed" in source
    assert '"threshold_recalibration_performed": False' in source


def test_merge_and_pair_validation_are_detector_free() -> None:
    for path in (
        "fuckmark/mid_dev_calibration_merge.py",
        "fuckmark/mid_dev_calibration_pair_validate.py",
        "fuckmark/corpus/mid_dev_calibration_pair.py",
    ):
        source, tree = _python_source(path)
        imported_modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not any("adapter" in value.lower() or "detector" in value.lower() for value in imported_modules)
        assert not any("adapter" in value.lower() or "detector" in value.lower() for value in imported_names)
        assert "calibrate_detector" not in source
