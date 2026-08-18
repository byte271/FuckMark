from __future__ import annotations

import json
from pathlib import Path

from fuckmark.adapters import DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN


ROOT = Path(__file__).resolve().parents[1]
LICENSE_FREEZE = ROOT / "source_licenses" / "upstream.json"


def test_source_license_freeze_matches_runtime_source_pins() -> None:
    payload = json.loads(LICENSE_FREEZE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "source-license-freeze-v1"
    assert payload["project_license_status"] == "UNSPECIFIED"
    assert "owner decision" in payload["project_license_note"]

    rows = {row["source_id"]: row for row in payload["sources"]}
    assert set(rows) == {
        DEEPMIND_REFERENCE_SOURCE_PIN.source_id,
        HUGGINGFACE_SYNTHID_SOURCE_PIN.source_id,
    }
    for source_pin in (DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN):
        row = rows[source_pin.source_id]
        assert row["repository"] == source_pin.repository
        assert row["commit"] == source_pin.commit
        assert row["license_id"] == source_pin.license_id == "Apache-2.0"
        assert row["license_path"] == "LICENSE"


def test_source_license_freeze_does_not_implicitly_license_project_code() -> None:
    payload = json.loads(LICENSE_FREEZE.read_text(encoding="utf-8"))
    assert payload["project_license_status"] == "UNSPECIFIED"
    assert all(row["license_id"] == "Apache-2.0" for row in payload["sources"])
