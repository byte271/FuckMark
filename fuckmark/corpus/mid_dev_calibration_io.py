from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .mid_dev_calibration import MidDevCalibrationArtifact
from .tiny_dev_io import _manifest, _mapping, _reject_constant, _unique_object


MID_DEV_CALIBRATION_JSON_MAX_BYTES = 256 * 1024 * 1024


class MidDevCalibrationJsonError(ValueError):
    pass


def _artifact(value: object) -> MidDevCalibrationArtifact:
    data = _mapping(
        "mid_dev_calibration_artifact",
        value,
        (
            "algorithm_version",
            "manifest",
            "target_lengths",
            "negatives_per_length",
            "source_profile_hash",
            "artifact_hash",
        ),
    )
    target_lengths = data["target_lengths"]
    if not isinstance(target_lengths, list):
        raise MidDevCalibrationJsonError("target_lengths must be a JSON array")
    return MidDevCalibrationArtifact(
        data["algorithm_version"],
        _manifest(data["manifest"]),
        tuple(target_lengths),
        data["negatives_per_length"],
        data["source_profile_hash"],
        data["artifact_hash"],
    )


def parse_mid_dev_calibration_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_JSON_MAX_BYTES:
        raise MidDevCalibrationJsonError("MidDev calibration JSON exceeds the size limit")
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except Exception as error:
        raise MidDevCalibrationJsonError("MidDev calibration JSON is not valid JSON") from error
    try:
        artifact = _artifact(decoded)
    except Exception as error:
        if isinstance(error, MidDevCalibrationJsonError):
            raise
        raise MidDevCalibrationJsonError("MidDev calibration JSON failed artifact validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCalibrationJsonError("MidDev calibration JSON is not canonical")
    return artifact


def load_mid_dev_calibration_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_JSON_MAX_BYTES:
        raise MidDevCalibrationJsonError("MidDev calibration JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCalibrationJsonError("MidDev calibration JSON must be UTF-8") from error
    return parse_mid_dev_calibration_json(text, require_canonical=require_canonical)
