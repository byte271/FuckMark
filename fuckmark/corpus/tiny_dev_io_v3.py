from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .schema import CorpusDomain, CorpusSplit
from .tiny_dev_io import (
    TINY_DEV_JSON_MAX_BYTES,
    TinyDevCorpusJsonError,
    _array,
    _manifest,
    _mapping,
    _reject_constant,
    _unique_object,
)
from .tiny_dev import TinyDevCorpusError
from .tiny_dev_v3 import (
    TINY_DEV_V3_CORPUS_ALGORITHM_VERSION,
    TINY_DEV_V3_MAX_ATTACK_PAIRS_PER_DOMAIN,
    TinyDevV3CorpusArtifact,
    TinyDevV3CorpusCell,
)


def _cell(value: object) -> TinyDevV3CorpusCell:
    data = _mapping("cell", value, ("split", "domain", "pair_count"))
    return TinyDevV3CorpusCell(
        split=CorpusSplit(data["split"]),
        domain=CorpusDomain(data["domain"]),
        pair_count=data["pair_count"],
    )


def _artifact_v3(value: object) -> TinyDevV3CorpusArtifact:
    data = _mapping(
        "artifact",
        value,
        (
            "algorithm_version",
            "manifest",
            "target_length",
            "calibration_pairs_per_domain",
            "attack_pairs_per_domain",
            "required_splits",
            "required_domains",
            "model_identity_hash",
            "generation_matching_signature_hash",
            "watermark_condition_hash",
            "cells",
            "artifact_hash",
        ),
    )
    return TinyDevV3CorpusArtifact(
        algorithm_version=data["algorithm_version"],
        manifest=_manifest(data["manifest"]),
        target_length=data["target_length"],
        calibration_pairs_per_domain=data["calibration_pairs_per_domain"],
        attack_pairs_per_domain=data["attack_pairs_per_domain"],
        required_splits=tuple(
            CorpusSplit(item) for item in _array("artifact.required_splits", data["required_splits"])
        ),
        required_domains=tuple(
            CorpusDomain(item) for item in _array("artifact.required_domains", data["required_domains"])
        ),
        model_identity_hash=data["model_identity_hash"],
        generation_matching_signature_hash=data["generation_matching_signature_hash"],
        watermark_condition_hash=data["watermark_condition_hash"],
        cells=tuple(_cell(item) for item in _array("artifact.cells", data["cells"])),
        artifact_hash=data["artifact_hash"],
    )


def parse_tiny_dev_v3_corpus_json(text: str, *, require_canonical: bool = True) -> TinyDevV3CorpusArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > TINY_DEV_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("tiny-dev v3 JSON exceeds the size limit")
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except TinyDevCorpusJsonError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise TinyDevCorpusJsonError("tiny-dev v3 JSON is not valid JSON") from error
    try:
        artifact = _artifact_v3(decoded)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, TinyDevCorpusJsonError):
            raise
        raise TinyDevCorpusJsonError("tiny-dev v3 JSON failed artifact validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise TinyDevCorpusJsonError("tiny-dev v3 JSON is not in canonical serialized form")
    return artifact


def load_tiny_dev_v3_corpus_json(path: str | Path, *, require_canonical: bool = True) -> TinyDevV3CorpusArtifact:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > TINY_DEV_JSON_MAX_BYTES:
        raise TinyDevCorpusJsonError("tiny-dev v3 JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TinyDevCorpusJsonError("tiny-dev v3 JSON must be UTF-8") from error
    return parse_tiny_dev_v3_corpus_json(text, require_canonical=require_canonical)


def load_tiny_dev_corpus_by_version_json(path: str | Path):
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as error:
        raise TinyDevCorpusJsonError("tiny-dev corpus JSON is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise TinyDevCorpusJsonError("tiny-dev corpus JSON must be an object")
    version = decoded.get("algorithm_version")
    if version == TINY_DEV_V3_CORPUS_ALGORITHM_VERSION:
        return parse_tiny_dev_v3_corpus_json(text)
    from .tiny_dev_io import parse_tiny_dev_corpus_json

    return parse_tiny_dev_corpus_json(text)
