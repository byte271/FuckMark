from pathlib import Path
import re
import tomllib

import fuckmark


def test_project_version_is_frozen() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "0.1.0"
    assert fuckmark.__version__ == "0.1.0"


def test_changelog_uses_only_the_frozen_project_version() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^##\s+(v?\d+\.\d+\.\d+)", text, flags=re.MULTILINE))
    assert headings == {"v0.1.0"}
