from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cycle6_recovery_seals_a_separate_provenance_manifest() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cycle6-recovery.yml").read_text(
        encoding="utf-8"
    )
    seal = workflow.split("  seal:\n", 1)[1]

    assert "needs: aggregate" in seal
    assert "python -m fuckmark.tiny_dev_cycle6_recovery_manifest" in seal
    assert '--source-workflow-run-id "${SOURCE_RUN_ID}"' in seal
    assert '--recovery-workflow-run-id "${GITHUB_RUN_ID}"' in seal
    assert '--frozen-source-code-commit "${FROZEN_SOURCE_CODE_COMMIT}"' in seal
    assert '--orchestration-code-commit "${ORCHESTRATION_SHA}"' in seal
    assert "name: cycle6-recovery-formal-bundle" in seal
