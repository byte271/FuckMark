from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .mid_dev_calibration_merged import (
    MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION,
    MidDevCalibrationMergedArtifact,
)
from .mid_dev_calibration_shard_io import (
    MID_DEV_CALIBRATION_SHARD_JSON_MAX_BYTES,
    _merged_manifest,
)
from .mid_dev_calibration_shards import CalibrationRole
from .tiny_dev_io import (
    TinyDevCorpusJsonError,
    _array,
    _mapping,
    _reject_constant,
    _sample,
    _unique_object,
)


MID_DEV_CALIBRATION_MERGED_JSON_MAX_BYTES = 512 * 1024 * 1024


def _parse_json(text: str):
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except TinyDevCorpusJsonError:
        raise
    except Exception as error:
        raise TinyDevCorpusJsonError("merged calibration JSON is not valid JSON") from error


def parse_mid_dev_calibration_merged_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationMergedArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_MERGED_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("merged calibration JSON exceeds the size limit")
    try:
        data = _mapping(
            "mid_dev_calibration_merged_artifact",
            _parse_json(text),
            (
                "algorithm_version",
                "role",
                "readiness_hash",
                "plan_hash",
                "samples",
                "manifest",
                "artifact_hash",
            ),
        )
        artifact = MidDevCalibrationMergedArtifact(
            algorithm_version=data["algorithm_version"],
            role=CalibrationRole(data["role"]),
            readiness_hash=data["readiness_hash"],
            plan_hash=data["plan_hash"],
            samples=tuple(_sample(value) for value in _array("samples", data["samples"])),
            manifest=_merged_manifest(data["manifest"]),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("merged calibration artifact failed validation") from error
    if artifact.algorithm_version != MID_DEV_CALIBRATION_MERGED_ARTIFACT_VERSION:
        raise TinyDevCorpusJsonError("unsupported merged calibration artifact version")
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("merged calibration artifact JSON is not canonical")
    return artifact


def load_mid_dev_calibration_merged_artifact_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationMergedArtifact:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_MERGED_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("merged calibration JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TinyDevCorpusJsonError("merged calibration JSON must be UTF-8") from error
    return parse_mid_dev_calibration_merged_artifact_json(text, require_canonical=require_canonical)
