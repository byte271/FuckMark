from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .prompt import PromptRecord
from .sample import CorpusSample
from .tiny_dev_io import (
    TinyDevCorpusJsonError,
    _array,
    _mapping,
    _prompt,
    _reject_constant,
    _sample,
    _unique_object,
)
from .measurement_calibration import (
    MEASUREMENT_CALIBRATION_MANIFEST_VERSION,
    MeasurementCalibrationCorpus,
    MeasurementCalibrationManifest,
)


def _manifest(value: object) -> MeasurementCalibrationManifest:
    data = _mapping(
        "manifest",
        value,
        (
            "algorithm_version",
            "corpus_id",
            "language",
            "prompts",
            "samples",
            "prompt_manifest_hash",
            "sample_manifest_hash",
            "manifest_hash",
        ),
    )
    return MeasurementCalibrationManifest(
        algorithm_version=data["algorithm_version"],
        corpus_id=data["corpus_id"],
        language=data["language"],
        prompts=tuple(_prompt(item) for item in _array("manifest.prompts", data["prompts"])),
        samples=tuple(_sample(item) for item in _array("manifest.samples", data["samples"])),
        prompt_manifest_hash=data["prompt_manifest_hash"],
        sample_manifest_hash=data["sample_manifest_hash"],
        manifest_hash=data["manifest_hash"],
    )


def parse_measurement_calibration_corpus_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MeasurementCalibrationCorpus:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        raise TinyDevCorpusJsonError("measurement calibration JSON is not valid JSON") from error
    data = _mapping(
        "artifact",
        decoded,
        (
            "algorithm_version",
            "manifest",
            "target_length",
            "topic_count_per_domain",
            "seeds_per_prompt",
            "sample_count",
            "negative_count",
            "audit_count",
            "model_identity_hash",
            "generation_matching_signature_hash",
            "watermark_condition_hash",
            "artifact_hash",
        ),
    )
    artifact = MeasurementCalibrationCorpus(
        algorithm_version=data["algorithm_version"],
        manifest=_manifest(data["manifest"]),
        target_length=data["target_length"],
        topic_count_per_domain=data["topic_count_per_domain"],
        seeds_per_prompt=data["seeds_per_prompt"],
        sample_count=data["sample_count"],
        negative_count=data["negative_count"],
        audit_count=data["audit_count"],
        model_identity_hash=data["model_identity_hash"],
        generation_matching_signature_hash=data["generation_matching_signature_hash"],
        watermark_condition_hash=data["watermark_condition_hash"],
        artifact_hash=data["artifact_hash"],
    )
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("measurement calibration JSON is not canonical")
    return artifact


def load_measurement_calibration_corpus_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MeasurementCalibrationCorpus:
    file_path = Path(path)
    return parse_measurement_calibration_corpus_json(
        file_path.read_text(encoding="utf-8"),
        require_canonical=require_canonical,
    )
