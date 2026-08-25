from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> str:
    return (ROOT / ".github" / "workflows" / "cycle6-recovery.yml").read_text(
        encoding="utf-8"
    )


def test_recovery_downloads_named_artifacts_after_exact_metadata_gate() -> None:
    workflow = _workflow()

    assert "actions/artifacts/9573956498" in workflow
    assert "actions/artifacts/9573829301" in workflow
    assert "actions/artifacts/9573952748" in workflow
    assert "artifact-ids:" not in workflow
    for seed in (760000, 770000, 780000):
        assert f"name: cycle6-freeze-{seed}" in workflow


def test_cross_check_and_seal_import_scientific_code_from_frozen_checkout() -> None:
    workflow = _workflow()
    cross_check = workflow.split("  cross-check:\n", 1)[1].split("  score:\n", 1)[0]
    seal = workflow.split("  seal:\n", 1)[1]

    for job in (cross_check, seal):
        assert "ref: ${{ env.FROZEN_SOURCE_CODE_COMMIT }}" in job
        assert "path: scientific" in job
        assert "PYTHONPATH: scientific" in job
        assert "--contract-json scientific/specs/fuckmark-cycle6-confirmation-v2.contract.json" in job

    assert "--repository-root scientific" in cross_check
    assert "scientific/fuckmark/" in cross_check
    assert "scientific/fuckmark/" in seal
    assert "scored/" in seal
