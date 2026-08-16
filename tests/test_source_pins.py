from pathlib import Path
import json

from fuckmark.types import SourcePin


def test_committed_source_pins_deserialize_into_immutable_source_pins() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "source_pins").glob("*.json"))
    assert paths
    pins = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        pins.append(SourcePin(**data))
    assert len({pin.source_id for pin in pins}) == len(pins)
    assert len({(pin.repository, pin.commit) for pin in pins}) == len(pins)
