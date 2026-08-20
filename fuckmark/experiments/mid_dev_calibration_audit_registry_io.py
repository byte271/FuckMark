from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..detectors.calibration_types import ExactBinomialInterval
from .mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
    CalibrationAuditArtifact,
)
from .mid_dev_calibration_audit_registry import (
    MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION,
    MidDevCalibrationAuditRegistry,
)
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json
from ..corpus.tiny_dev_io import _array, _mapping


def _interval(value: object) -> ExactBinomialInterval:
    data = _mapping(
        "exact_binomial_interval",
        value,
        ("method", "confidence_level", "lower", "upper"),
    )
    return ExactBinomialInterval(**data)


def _audit_artifact(value: object) -> CalibrationAuditArtifact:
    data = _mapping(
        "calibration_audit_artifact",
        value,
        (
            "algorithm_version",
            "model_tokenizer_identity_hash",
            "detector_identity_hash",
            "calibration_regime_hash",
            "regime_id",
            "regime_decision_hash",
            "select_manifest_hash",
            "select_count",
            "threshold_hash",
            "threshold_value",
            "target_fpr",
            "comparison_operator",
            "select_false_positive_count",
            "select_fpr_interval",
            "audit_manifest_hash",
            "audit_count",
            "audit_false_positive_count",
            "audit_fpr",
            "audit_fpr_interval",
            "length_policy_id",
            "artifact_hash",
        ),
    )
    artifact = CalibrationAuditArtifact(
        algorithm_version=data["algorithm_version"],
        model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
        detector_identity_hash=data["detector_identity_hash"],
        calibration_regime_hash=data["calibration_regime_hash"],
        regime_id=data["regime_id"],
        regime_decision_hash=data["regime_decision_hash"],
        select_manifest_hash=data["select_manifest_hash"],
        select_count=data["select_count"],
        threshold_hash=data["threshold_hash"],
        threshold_value=data["threshold_value"],
        target_fpr=data["target_fpr"],
        comparison_operator=data["comparison_operator"],
        select_false_positive_count=data["select_false_positive_count"],
        select_fpr_interval=_interval(data["select_fpr_interval"]),
        audit_manifest_hash=data["audit_manifest_hash"],
        audit_count=data["audit_count"],
        audit_false_positive_count=data["audit_false_positive_count"],
        audit_fpr=data["audit_fpr"],
        audit_fpr_interval=_interval(data["audit_fpr_interval"]),
        length_policy_id=data["length_policy_id"],
        artifact_hash=data["artifact_hash"],
    )
    if artifact.algorithm_version != MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION:
        raise MidDevPlanJsonError("unsupported calibration audit artifact version")
    return artifact


def parse_mid_dev_calibration_audit_registry_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationAuditRegistry:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_calibration_audit_registry",
            decoded,
            (
                "algorithm_version",
                "threshold_registry_hash",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "select_manifest_hash",
                "audit_manifest_hash",
                "detector_identity_hash",
                "calibration_consistency_rule",
                "target_fpr",
                "artifacts",
                "consistency_pass",
                "unstable_regime_ids",
                "registry_hash",
            ),
        )
        unstable = data["unstable_regime_ids"]
        if not isinstance(unstable, list) or any(not isinstance(value, str) for value in unstable):
            raise TypeError("unstable_regime_ids must be a JSON array of strings")
        registry = MidDevCalibrationAuditRegistry(
            algorithm_version=data["algorithm_version"],
            threshold_registry_hash=data["threshold_registry_hash"],
            opportunity_audit_hash=data["opportunity_audit_hash"],
            regime_decision_hash=data["regime_decision_hash"],
            select_manifest_hash=data["select_manifest_hash"],
            audit_manifest_hash=data["audit_manifest_hash"],
            detector_identity_hash=data["detector_identity_hash"],
            calibration_consistency_rule=data["calibration_consistency_rule"],
            target_fpr=data["target_fpr"],
            artifacts=tuple(_audit_artifact(value) for value in _array("artifacts", data["artifacts"])),
            consistency_pass=data["consistency_pass"],
            unstable_regime_ids=tuple(unstable),
            registry_hash=data["registry_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("calibration audit registry failed validation") from error
    if registry.algorithm_version != MID_DEV_CALIBRATION_AUDIT_REGISTRY_VERSION:
        raise MidDevPlanJsonError("unsupported calibration audit registry version")
    if require_canonical:
        canonical = canonical_json_text(registry)
        if text not in (canonical, canonical + "\n"):
            raise MidDevPlanJsonError("calibration audit registry JSON is not canonical")
    return registry


def load_mid_dev_calibration_audit_registry_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationAuditRegistry:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("calibration audit registry JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevPlanJsonError("calibration audit registry JSON must be UTF-8") from error
    return parse_mid_dev_calibration_audit_registry_json(text, require_canonical=require_canonical)
