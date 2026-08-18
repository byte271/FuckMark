import json

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus import (
    TinyDevCorpusJsonError,
    load_tiny_dev_corpus_json,
    parse_tiny_dev_corpus_json,
)
from tiny_dev_experiment_helpers import tiny_dev_artifact


def test_tiny_dev_json_roundtrip_replays_all_nested_hashes() -> None:
    artifact = tiny_dev_artifact()
    text = canonical_json_text(artifact) + "\n"
    replayed = parse_tiny_dev_corpus_json(text)
    assert replayed == artifact
    assert replayed.artifact_hash == artifact.artifact_hash
    assert replayed.manifest.manifest_hash == artifact.manifest.manifest_hash


def test_tiny_dev_json_file_loader_replays_canonical_artifact(tmp_path) -> None:
    artifact = tiny_dev_artifact()
    path = tmp_path / "tiny-dev.json"
    path.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    assert load_tiny_dev_corpus_json(path) == artifact


def test_tiny_dev_json_rejects_nested_hash_tampering() -> None:
    raw = json.loads(canonical_json_text(tiny_dev_artifact()))
    raw["manifest"]["samples"][0]["text"] += " tampered"
    text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with pytest.raises(TinyDevCorpusJsonError, match="artifact validation"):
        parse_tiny_dev_corpus_json(text)


def test_tiny_dev_json_rejects_duplicate_object_keys() -> None:
    text = canonical_json_text(tiny_dev_artifact())
    duplicate = text.replace(
        '{"algorithm_version":',
        '{"algorithm_version":"tiny-dev-corpus-v2","algorithm_version":',
        1,
    )
    with pytest.raises(TinyDevCorpusJsonError, match="duplicate JSON object key"):
        parse_tiny_dev_corpus_json(duplicate)


def test_tiny_dev_json_rejects_unknown_schema_fields() -> None:
    raw = json.loads(canonical_json_text(tiny_dev_artifact()))
    raw["unexpected"] = True
    text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with pytest.raises(TinyDevCorpusJsonError, match="fields do not match schema"):
        parse_tiny_dev_corpus_json(text)


def test_tiny_dev_json_rejects_noncanonical_serialization_by_default() -> None:
    text = canonical_json_text(tiny_dev_artifact())
    noncanonical = text.replace(",", ", ", 1)
    with pytest.raises(TinyDevCorpusJsonError, match="canonical serialized form"):
        parse_tiny_dev_corpus_json(noncanonical)
    assert parse_tiny_dev_corpus_json(noncanonical, require_canonical=False) == tiny_dev_artifact()


def test_tiny_dev_json_rejects_nonfinite_json_numbers() -> None:
    with pytest.raises(TinyDevCorpusJsonError, match="non-finite JSON number"):
        parse_tiny_dev_corpus_json('{"value":NaN}', require_canonical=False)
