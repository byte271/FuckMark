from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from ..hashing import sha256_json


MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_VERSION = (
    "mid-dev-calibration-threshold-compacted-provenance-v1"
)
MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_MAX_BYTES = 4 * 1024 * 1024


class MidDevCalibrationThresholdCompactedProvenanceError(ValueError):
    pass


def _sha(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            f"{name} must be lowercase SHA-256"
        )
    return value


def parse_mid_dev_calibration_threshold_compacted_provenance_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationThresholdCompactedProvenanceError("threshold provenance exceeds size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "threshold_compacted_provenance",
            decoded,
            (
                "algorithm_version",
                "readiness_hash",
                "select_plan_hash",
                "select_compaction_provenance_hash",
                "select_artifact_hash",
                "select_manifest_hash",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "source_coverage_artifact_hash",
                "model_tokenizer_identity_hash",
                "detector_identity_hash",
                "threshold_registry_hash",
                "serious_regime_ids",
                "descriptive_regime_ids",
                "regime_count",
                "json_fsync_success",
                "cal_select_only",
                "github_run_id",
                "github_run_attempt",
                "github_event_name",
                "github_checkout_sha",
                "provenance_hash",
            ),
        )
    except Exception as error:
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "invalid compacted threshold provenance JSON"
        ) from error
    if data["algorithm_version"] != MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_VERSION:
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "unsupported compacted threshold provenance version"
        )
    for name in (
        "readiness_hash",
        "select_plan_hash",
        "select_compaction_provenance_hash",
        "select_artifact_hash",
        "select_manifest_hash",
        "opportunity_audit_hash",
        "regime_decision_hash",
        "source_coverage_artifact_hash",
        "model_tokenizer_identity_hash",
        "detector_identity_hash",
        "threshold_registry_hash",
        "provenance_hash",
    ):
        _sha(name, data[name])
    for name in ("serious_regime_ids", "descriptive_regime_ids"):
        values = data[name]
        if not isinstance(values, list) or values != sorted(set(values)):
            raise MidDevCalibrationThresholdCompactedProvenanceError(
                f"{name} must be sorted unique"
            )
        if any(not isinstance(value, str) or not value for value in values):
            raise MidDevCalibrationThresholdCompactedProvenanceError(
                f"{name} contains invalid regime id"
            )
    if set(data["serious_regime_ids"]) & set(data["descriptive_regime_ids"]):
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "serious/descriptive regimes overlap"
        )
    if data["regime_count"] != len(data["serious_regime_ids"]):
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "threshold regime count differs from serious regime set"
        )
    if data["json_fsync_success"] is not True or data["cal_select_only"] is not True:
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "threshold provenance must attest fsync and CAL-SELECT-only construction"
        )
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "threshold provenance hash does not replay"
        )
    if require_canonical:
        canonical = canonical_json_text(data)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCalibrationThresholdCompactedProvenanceError(
                "threshold provenance JSON is not canonical"
            )
    return dict(data)


def load_mid_dev_calibration_threshold_compacted_provenance_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_THRESHOLD_COMPACTED_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationThresholdCompactedProvenanceError("threshold provenance exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCalibrationThresholdCompactedProvenanceError(
            "threshold provenance must be UTF-8"
        ) from error
    return parse_mid_dev_calibration_threshold_compacted_provenance_json(
        text,
        require_canonical=require_canonical,
    )
