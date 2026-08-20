from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.mid_dev_calibration_shards import CalibrationRole
from ..corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from ..hashing import sha256_json


MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION = "mid-dev-calibration-merge-provenance-v1"
MID_DEV_CALIBRATION_MERGE_PROVENANCE_MAX_BYTES = 4 * 1024 * 1024


class MidDevCalibrationMergeProvenanceError(ValueError):
    pass


def parse_mid_dev_calibration_merge_provenance_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_MERGE_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationMergeProvenanceError("calibration merge provenance exceeds size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "calibration_merge_provenance",
            decoded,
            (
                "algorithm_version",
                "readiness_hash",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "role",
                "plan_hash",
                "shard_provenance_hashes",
                "merged_manifest_hash",
                "merged_artifact_hash",
                "sample_count",
                "json_fsync_success",
                "github_run_id",
                "github_run_attempt",
                "github_event_name",
                "github_checkout_sha",
                "provenance_hash",
            ),
        )
    except Exception as error:
        raise MidDevCalibrationMergeProvenanceError("invalid calibration merge provenance JSON") from error
    if data["algorithm_version"] != MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION:
        raise MidDevCalibrationMergeProvenanceError("unsupported calibration merge provenance version")
    try:
        CalibrationRole(data["role"])
    except Exception as error:
        raise MidDevCalibrationMergeProvenanceError("invalid calibration merge provenance role") from error
    hashes = data["shard_provenance_hashes"]
    if not isinstance(hashes, list) or len(hashes) != 16 or len(set(hashes)) != 16:
        raise MidDevCalibrationMergeProvenanceError("merge provenance requires exactly 16 unique shard provenance hashes")
    if any(not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value) for value in hashes):
        raise MidDevCalibrationMergeProvenanceError("invalid shard provenance hash")
    for name in (
        "readiness_hash",
        "opportunity_audit_hash",
        "regime_decision_hash",
        "plan_hash",
        "merged_manifest_hash",
        "merged_artifact_hash",
        "provenance_hash",
    ):
        value = data[name]
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise MidDevCalibrationMergeProvenanceError(f"{name} must be a lowercase SHA-256 digest")
    if data["sample_count"] != 4000:
        raise MidDevCalibrationMergeProvenanceError("merged calibration provenance must bind exactly 4000 samples")
    if data["json_fsync_success"] is not True:
        raise MidDevCalibrationMergeProvenanceError("merged calibration provenance does not attest fsync")
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevCalibrationMergeProvenanceError("calibration merge provenance hash does not replay")
    if require_canonical:
        canonical = canonical_json_text(data)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCalibrationMergeProvenanceError("calibration merge provenance JSON is not canonical")
    return dict(data)


def load_mid_dev_calibration_merge_provenance_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_MERGE_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationMergeProvenanceError("calibration merge provenance exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCalibrationMergeProvenanceError("calibration merge provenance must be UTF-8") from error
    return parse_mid_dev_calibration_merge_provenance_json(text, require_canonical=require_canonical)
