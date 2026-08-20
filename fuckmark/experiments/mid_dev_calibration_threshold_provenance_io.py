from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from ..hashing import sha256_json


MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION = "mid-dev-calibration-threshold-provenance-v1"
MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_MAX_BYTES = 2 * 1024 * 1024


class MidDevCalibrationThresholdProvenanceError(ValueError):
    pass


def parse_mid_dev_calibration_threshold_provenance_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance exceeds size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "calibration_threshold_provenance",
            decoded,
            (
                "algorithm_version",
                "readiness_hash",
                "select_plan_hash",
                "select_merge_provenance_hash",
                "select_artifact_hash",
                "select_manifest_hash",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "model_tokenizer_identity_hash",
                "detector_identity_hash",
                "threshold_registry_hash",
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
        raise MidDevCalibrationThresholdProvenanceError("invalid threshold provenance JSON") from error
    if data["algorithm_version"] != MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION:
        raise MidDevCalibrationThresholdProvenanceError("unsupported threshold provenance version")
    for name in (
        "readiness_hash",
        "select_plan_hash",
        "select_merge_provenance_hash",
        "select_artifact_hash",
        "select_manifest_hash",
        "opportunity_audit_hash",
        "regime_decision_hash",
        "model_tokenizer_identity_hash",
        "detector_identity_hash",
        "threshold_registry_hash",
        "provenance_hash",
    ):
        value = data[name]
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise MidDevCalibrationThresholdProvenanceError(f"{name} must be a lowercase SHA-256 digest")
    if isinstance(data["regime_count"], bool) or not isinstance(data["regime_count"], int) or data["regime_count"] <= 0:
        raise MidDevCalibrationThresholdProvenanceError("regime_count must be positive")
    if data["json_fsync_success"] is not True:
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance does not attest fsync")
    if data["cal_select_only"] is not True:
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance must attest CAL-SELECT-only construction")
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance hash does not replay")
    if require_canonical:
        canonical = canonical_json_text(data)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCalibrationThresholdProvenanceError("threshold provenance JSON is not canonical")
    return dict(data)


def load_mid_dev_calibration_threshold_provenance_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCalibrationThresholdProvenanceError("threshold provenance must be UTF-8") from error
    return parse_mid_dev_calibration_threshold_provenance_json(text, require_canonical=require_canonical)
