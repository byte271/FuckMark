from __future__ import annotations

import json

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus.mid_dev_generation import build_real_mid_dev_corpus
from fuckmark.corpus.mid_dev_io import MidDevCorpusJsonError, parse_mid_dev_corpus_json
from tests.test_mid_dev_generation import _FakeBackend


def test_middev_json_round_trip_requires_canonical_content() -> None:
    artifact = build_real_mid_dev_corpus(_FakeBackend())
    text = canonical_json_text(artifact) + "\n"
    loaded = parse_mid_dev_corpus_json(text)
    assert loaded.artifact_hash == artifact.artifact_hash
    assert loaded.manifest.manifest_hash == artifact.manifest.manifest_hash


def test_middev_json_rejects_noncanonical_serialization() -> None:
    artifact = build_real_mid_dev_corpus(_FakeBackend())
    decoded = json.loads(canonical_json_text(artifact))
    noncanonical = json.dumps(decoded, indent=2)
    with pytest.raises(MidDevCorpusJsonError, match="canonical"):
        parse_mid_dev_corpus_json(noncanonical)


def test_middev_json_rejects_tampered_artifact_hash() -> None:
    artifact = build_real_mid_dev_corpus(_FakeBackend())
    decoded = json.loads(canonical_json_text(artifact))
    decoded["artifact_hash"] = "0" * 64
    with pytest.raises(MidDevCorpusJsonError, match="artifact validation"):
        parse_mid_dev_corpus_json(json.dumps(decoded, sort_keys=True, separators=(",", ":")), require_canonical=False)


def test_middev_json_rejects_extra_top_level_field() -> None:
    artifact = build_real_mid_dev_corpus(_FakeBackend())
    decoded = json.loads(canonical_json_text(artifact))
    decoded["unexpected"] = True
    with pytest.raises(MidDevCorpusJsonError, match="artifact validation"):
        parse_mid_dev_corpus_json(json.dumps(decoded), require_canonical=False)
