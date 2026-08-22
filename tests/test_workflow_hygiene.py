from pathlib import Path

import pytest


def one_time_export_workflow_violations(root: Path) -> list[Path]:
    workflows = root / ".github" / "workflows"
    assert workflows.is_dir(), workflows
    forbidden = ("export-fidelity-api.yml", "export-readiness-api.yml")
    return [workflows / name for name in forbidden if (workflows / name).exists()]


def test_one_time_export_workflows_are_not_committed() -> None:
    root = Path(__file__).resolve().parents[1]
    assert one_time_export_workflow_violations(root) == []


def test_one_time_export_workflow_check_fails_when_forbidden_workflow_present(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "export-fidelity-api.yml").write_text("jobs: {}\n", encoding="utf-8")
    assert one_time_export_workflow_violations(tmp_path) == [workflows / "export-fidelity-api.yml"]


def test_one_time_export_workflow_check_fails_closed_without_workflows_directory(tmp_path: Path) -> None:
    with pytest.raises(AssertionError):
        one_time_export_workflow_violations(tmp_path)
