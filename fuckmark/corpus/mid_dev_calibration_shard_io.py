from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from .mid_dev_calibration_shards import (
    CalibrationRole,
    MidDevCalibrationMergedManifest,
    MidDevCalibrationShardOutputManifest,
    MidDevGeneratedCalibrationShard,
)
from .tiny_dev_io import TINY_DEV_JSON_MAX_BYTES, TinyDevCorpusJsonError, _array, _mapping, _sample
from ..experiments.mid_dev_plan_io import _parse_json


MID_DEV_CALIBRATION_SHARD_JSON_MAX_BYTES = 256 * 1024 * 1024


def _tuple_ints(name: str, value: object) -> tuple[int, ...]:
    values = _array(name, value)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
        raise TinyDevCorpusJsonError(f"{name} must contain integers")
    return tuple(values)


def _tuple_strings(name: str, value: object) -> tuple[str, ...]:
    values = _array(name, value)
    if any(not isinstance(item, str) for item in values):
        raise TinyDevCorpusJsonError(f"{name} must contain strings")
    return tuple(values)


def _output_manifest(value: object) -> MidDevCalibrationShardOutputManifest:
    data = _mapping(
        "calibration_shard_output_manifest",
        value,
        (
            "algorithm_version",
            "role",
            "plan_hash",
            "shard_id",
            "shard_spec_hash",
            "target_length",
            "source_indices",
            "prompt_ids",
            "sample_ids",
            "sample_record_hashes",
            "text_sha256s",
            "continuation_token_hashes",
            "model_tokenizer_identity_hash",
            "watermark_config_hash",
            "watermark_condition_hash",
            "output_hash",
        ),
    )
    return MidDevCalibrationShardOutputManifest(
        algorithm_version=data["algorithm_version"],
        role=CalibrationRole(data["role"]),
        plan_hash=data["plan_hash"],
        shard_id=data["shard_id"],
        shard_spec_hash=data["shard_spec_hash"],
        target_length=data["target_length"],
        source_indices=_tuple_ints("source_indices", data["source_indices"]),
        prompt_ids=_tuple_strings("prompt_ids", data["prompt_ids"]),
        sample_ids=_tuple_strings("sample_ids", data["sample_ids"]),
        sample_record_hashes=_tuple_strings("sample_record_hashes", data["sample_record_hashes"]),
        text_sha256s=_tuple_strings("text_sha256s", data["text_sha256s"]),
        continuation_token_hashes=_tuple_strings("continuation_token_hashes", data["continuation_token_hashes"]),
        model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
        watermark_config_hash=data["watermark_config_hash"],
        watermark_condition_hash=data["watermark_condition_hash"],
        output_hash=data["output_hash"],
    )


def parse_mid_dev_generated_calibration_shard_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevGeneratedCalibrationShard:
    decoded = _parse_json(text)
    try:
        data = _mapping("generated_calibration_shard", decoded, ("samples", "manifest"))
        shard = MidDevGeneratedCalibrationShard(
            samples=tuple(_sample(value) for value in _array("samples", data["samples"])),
            manifest=_output_manifest(data["manifest"]),
        )
    except Exception as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("generated calibration shard failed validation") from error
    if require_canonical:
        canonical = canonical_json_text(shard)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("generated calibration shard JSON is not canonical")
    return shard


def _merged_manifest(value: object) -> MidDevCalibrationMergedManifest:
    data = _mapping(
        "calibration_merged_manifest",
        value,
        (
            "algorithm_version",
            "role",
            "plan_hash",
            "prompt_manifest_hash",
            "shard_output_hashes",
            "prompt_ids",
            "sample_ids",
            "sample_record_hashes",
            "text_sha256s",
            "continuation_token_hashes",
            "model_tokenizer_identity_hash",
            "watermark_config_hash",
            "watermark_condition_hash",
            "manifest_hash",
        ),
    )
    return MidDevCalibrationMergedManifest(
        algorithm_version=data["algorithm_version"],
        role=CalibrationRole(data["role"]),
        plan_hash=data["plan_hash"],
        prompt_manifest_hash=data["prompt_manifest_hash"],
        shard_output_hashes=_tuple_strings("shard_output_hashes", data["shard_output_hashes"]),
        prompt_ids=_tuple_strings("prompt_ids", data["prompt_ids"]),
        sample_ids=_tuple_strings("sample_ids", data["sample_ids"]),
        sample_record_hashes=_tuple_strings("sample_record_hashes", data["sample_record_hashes"]),
        text_sha256s=_tuple_strings("text_sha256s", data["text_sha256s"]),
        continuation_token_hashes=_tuple_strings("continuation_token_hashes", data["continuation_token_hashes"]),
        model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
        watermark_config_hash=data["watermark_config_hash"],
        watermark_condition_hash=data["watermark_condition_hash"],
        manifest_hash=data["manifest_hash"],
    )


def parse_mid_dev_calibration_merged_manifest_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevCalibrationMergedManifest:
    decoded = _parse_json(text)
    try:
        manifest = _merged_manifest(decoded)
    except Exception as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("calibration merged manifest failed validation") from error
    if require_canonical:
        canonical = canonical_json_text(manifest)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("calibration merged manifest JSON is not canonical")
    return manifest


def _load(path: str | Path, parser):
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_SHARD_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("calibration shard JSON exceeds the size limit")
    return parser(file_path.read_text(encoding="utf-8"))


def load_mid_dev_generated_calibration_shard_json(path: str | Path) -> MidDevGeneratedCalibrationShard:
    return _load(path, parse_mid_dev_generated_calibration_shard_json)


def load_mid_dev_calibration_merged_manifest_json(path: str | Path) -> MidDevCalibrationMergedManifest:
    return _load(path, parse_mid_dev_calibration_merged_manifest_json)
