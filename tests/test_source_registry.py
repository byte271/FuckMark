import json
from pathlib import Path

import pytest

from fuckmark.adapters.deepmind_reference import SOURCE_PIN as DEEPMIND_SOURCE_PIN
from fuckmark.adapters.huggingface_synthid import SOURCE_PIN as HUGGINGFACE_SOURCE_PIN
from fuckmark.source_registry import SourcePinRegistry, load_source_pin
from fuckmark.types import SourcePin


def test_source_pin_registry_loads_committed_pins_deterministically() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = SourcePinRegistry.from_directory(root / "source_pins")
    assert registry.source_ids == (
        "deepmind-synthid-text-reference",
        "huggingface-transformers-synthid",
    )
    assert registry.get("deepmind-synthid-text-reference") == DEEPMIND_SOURCE_PIN
    assert registry.get("huggingface-transformers-synthid") == HUGGINGFACE_SOURCE_PIN


def test_source_pin_registry_rejects_duplicate_source_id() -> None:
    pin = DEEPMIND_SOURCE_PIN
    duplicate = SourcePin(
        source_id=pin.source_id,
        repository="example/other",
        commit="1" * 40,
        license_id="Apache-2.0",
        critical_files=("a.py",),
    )
    with pytest.raises(ValueError):
        SourcePinRegistry((pin, duplicate))


def test_source_pin_registry_rejects_duplicate_repository_revision() -> None:
    pin = DEEPMIND_SOURCE_PIN
    duplicate = SourcePin(
        source_id="other-source",
        repository=pin.repository,
        commit=pin.commit,
        license_id=pin.license_id,
        critical_files=pin.critical_files,
    )
    with pytest.raises(ValueError):
        SourcePinRegistry((pin, duplicate))


def test_load_source_pin_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "pin.json"
    path.write_text(
        '{"source_id":"a","source_id":"b","repository":"x/y","commit":"' + "1" * 40 + '","license_id":"Apache-2.0","critical_files":["a.py"]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_source_pin(path)


def test_load_source_pin_rejects_schema_drift(tmp_path: Path) -> None:
    path = tmp_path / "pin.json"
    payload = {
        "source_id": "a",
        "repository": "x/y",
        "commit": "1" * 40,
        "license_id": "Apache-2.0",
        "critical_files": ["a.py"],
        "unexpected": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_pin(path)


def test_source_pin_registry_unknown_id_is_explicit() -> None:
    registry = SourcePinRegistry((DEEPMIND_SOURCE_PIN,))
    with pytest.raises(KeyError, match="Unknown source_id"):
        registry.get("missing")
