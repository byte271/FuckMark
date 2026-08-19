from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from .mid_dev import MidDevAttackArtifact
from .mid_dev_validation import validate_mid_dev_experiment_identity
from .tiny_dev_io import _manifest, _mapping, _reject_constant, _unique_object


MID_DEV_JSON_MAX_BYTES = 256 * 1024 * 1024


class MidDevCorpusJsonError(ValueError):
    pass


def _artifact(value: object) -> MidDevAttackArtifact:
    data = _mapping(
        "mid_dev_artifact",
        value,
        (
            "algorithm_version",
            "manifest",
            "source_count",
            "target_lengths",
            "family_ids",
            "source_profile_hash",
            "analysis_split_hash",
            "artifact_hash",
        ),
    )
    target_lengths = data["target_lengths"]
    family_ids = data["family_ids"]
    if not isinstance(target_lengths, list):
        raise MidDevCorpusJsonError("target_lengths must be a JSON array")
    if not isinstance(family_ids, list):
        raise MidDevCorpusJsonError("family_ids must be a JSON array")
    return MidDevAttackArtifact(
        algorithm_version=data["algorithm_version"],
        manifest=_manifest(data["manifest"]),
        source_count=data["source_count"],
        target_lengths=tuple(target_lengths),
        family_ids=tuple(family_ids),
        source_profile_hash=data["source_profile_hash"],
        analysis_split_hash=data["analysis_split_hash"],
        artifact_hash=data["artifact_hash"],
    )


def parse_mid_dev_corpus_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevAttackArtifact:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_JSON_MAX_BYTES:
        raise MidDevCorpusJsonError("mid-dev JSON exceeds the size limit")
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except Exception as error:
        raise MidDevCorpusJsonError("mid-dev JSON is not valid JSON") from error
    try:
        artifact = _artifact(decoded)
        validate_mid_dev_experiment_identity(artifact)
    except Exception as error:
        if isinstance(error, MidDevCorpusJsonError):
            raise
        raise MidDevCorpusJsonError("mid-dev JSON failed artifact validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCorpusJsonError("mid-dev JSON is not in canonical serialized form")
    return artifact


def load_mid_dev_corpus_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevAttackArtifact:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_JSON_MAX_BYTES:
        raise MidDevCorpusJsonError("mid-dev JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCorpusJsonError("mid-dev JSON must be UTF-8") from error
    return parse_mid_dev_corpus_json(text, require_canonical=require_canonical)
