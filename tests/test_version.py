from pathlib import Path
import re
import tomllib

import fuckmark


def test_project_version_matches_package_identity() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert fuckmark.__version__ == version


def test_changelog_leads_with_current_project_version() -> None:
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data["project"]["version"]
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+(v?\d+\.\d+\.\d+)", text, flags=re.MULTILINE)
    assert headings
    assert headings[0] == f"v{version}"
    assert len(headings) == len(set(headings))
