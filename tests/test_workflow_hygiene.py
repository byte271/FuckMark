from pathlib import Path


def test_one_time_export_workflows_are_not_committed() -> None:
    workflows = Path(".github/workflows")
    assert not (workflows / "export-fidelity-api.yml").exists()
    assert not (workflows / "export-readiness-api.yml").exists()
