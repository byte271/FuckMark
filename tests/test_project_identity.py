from pathlib import Path
import tomllib

import fuckmark


def test_project_identity_is_fuckmark_v040() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == "fuckmark"
    assert project["version"] == "0.4.0"
    assert fuckmark.__project_name__ == "FuckMark"
    assert fuckmark.__version__ == "0.4.0"


def test_legacy_project_identity_is_absent_outside_immutable_spec() -> None:
    root = Path(__file__).resolve().parents[1]
    frozen_spec = root / "evidence" / "frozen-spec-revision-2" / "spec.md"
    forbidden = (
        "Watermark " + "Fracture " + "Lab",
        "watermark-" + "fracture-" + "lab",
        "GF" + "Watermark",
        "GFOC" + "Mark",
    )
    for path in root.rglob("*"):
        if path == frozen_spec:
            continue
        if not path.is_file() or any(part.startswith(".") for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".toml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert all(value not in text for value in forbidden)
    assert not (root / ("w" + "f" + "l")).exists()
