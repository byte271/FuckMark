from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .mid_dev_calibration_pair import MID_DEV_CALIBRATION_PAIR_VERSION, MidDevCalibrationPairArtifact
from .tiny_dev_io import TinyDevCorpusJsonError, _mapping, _reject_constant, _unique_object


MID_DEV_CALIBRATION_PAIR_JSON_MAX_BYTES = 4 * 1024 * 1024


def parse_mid_dev_calibration_pair_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationPairArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_PAIR_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("calibration pair JSON exceeds the size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "mid_dev_calibration_pair_artifact",
            decoded,
            tuple(MidDevCalibrationPairArtifact.__dataclass_fields__),
        )
        artifact = MidDevCalibrationPairArtifact(**data)
    except Exception as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("calibration pair artifact failed validation") from error
    if artifact.algorithm_version != MID_DEV_CALIBRATION_PAIR_VERSION:
        raise TinyDevCorpusJsonError("unsupported calibration pair artifact version")
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("calibration pair artifact JSON is not canonical")
    return artifact


def load_mid_dev_calibration_pair_artifact_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationPairArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_PAIR_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("calibration pair JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TinyDevCorpusJsonError("calibration pair JSON must be UTF-8") from error
    return parse_mid_dev_calibration_pair_artifact_json(text, require_canonical=require_canonical)
