from __future__ import annotations

import hashlib
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SPEC_SHA256 = "089e32ab5477038adbb47b63eeaeddd1fa95dfcd226f1770d8b174ead088dc9a"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_revision_2_spec_is_exact() -> None:
    spec = ROOT / "evidence" / "frozen-spec-revision-2" / "spec.md"
    sums = ROOT / "evidence" / "frozen-spec-revision-2" / "SHA256SUMS.txt"
    assert spec.is_file()
    assert spec.stat().st_size == 145372
    assert _sha256(spec) == SPEC_SHA256
    assert sums.read_bytes() == f"{SPEC_SHA256}  spec.md\n".encode("ascii")


def test_dependency_lock_is_present_and_project_bound() -> None:
    lock = ROOT / "uv.lock"
    assert lock.is_file()
    text = lock.read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert text.startswith("version = 1\nrevision = 3\n")
    assert f'name = "fuckmark"\nversion = "{project["version"]}"' in text
    assert 'requires-python = ">=3.11"' in text
