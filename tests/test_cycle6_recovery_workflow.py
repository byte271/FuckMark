from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cycle6_recovery_pins_run16_artifact_identity() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cycle6-recovery.yml").read_text(
        encoding="utf-8"
    )

    assert 'SOURCE_RUN_ID: "32873260399"' in workflow
    assert "9573956498" in workflow
    assert "sha256:79ee80808758d2ee143b4a41dc7e0104d9261d4873e7af37cac8a6ba2e5925d3" in workflow
    assert "9573829301" in workflow
    assert "sha256:c75717dc3538abadbd33997b883c5f15e0bc15e155b2be5eab870ccb82aa5807" in workflow
    assert "9573952748" in workflow
    assert "sha256:2900ed5f61057b7fff5f1e42b855a11322441fb1e53fd48da39ad9fff1482821" in workflow


def test_cycle6_recovery_separates_orchestration_and_scientific_checkouts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cycle6-recovery.yml").read_text(
        encoding="utf-8"
    )
    score = workflow.split("  score:\n", 1)[1].split("  aggregate:\n", 1)[0]
    aggregate = workflow.split("  aggregate:\n", 1)[1]

    assert "needs: cross-check" in score
    assert "path: orchestration" in score
    assert "path: scientific" in score
    assert "ref: ${{ env.FROZEN_SOURCE_CODE_COMMIT }}" in score
    assert "--expected-cross-check-json" in score
    assert "--source-code-commit \"${FROZEN_SOURCE_CODE_COMMIT}\"" in score
    assert "git rev-parse HEAD" not in workflow
    assert workflow.count("persist-credentials: false") == workflow.count("actions/checkout@v4")
    assert "needs: score" in aggregate
    assert "ref: ${{ env.FROZEN_SOURCE_CODE_COMMIT }}" in aggregate
    assert "tiny_dev_corpus_hf" not in workflow
