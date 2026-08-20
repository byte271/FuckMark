from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus.schema import WatermarkLabel
from fuckmark.experiments.mid_dev_source_opportunity_coverage import (
    MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
    MidDevSourceOpportunityCoverageArtifact,
    MidDevSourceOpportunityCoverageRow,
    MidDevSourceRegimeCount,
)
from fuckmark.experiments.mid_dev_source_opportunity_coverage_io import (
    parse_mid_dev_source_opportunity_coverage_json,
)


def _hash(character: str) -> str:
    return character * 64


def _coverage() -> MidDevSourceOpportunityCoverageArtifact:
    rows = []
    for index in range(36):
        regime_id = "eligible-09" if index < 18 else "eligible-10"
        for label in (WatermarkLabel.UNWATERMARKED, WatermarkLabel.WATERMARKED):
            sample_id = f"sample-{index:02d}-{label.value}"
            rows.append(
                MidDevSourceOpportunityCoverageRow.create(
                    sample_id=sample_id,
                    source_group_id=f"match-{index:02d}",
                    prompt_id=f"prompt-{index:02d}",
                    label=label.value,
                    target_length=128 if index < 18 else 256,
                    source_record_hash=_hash("a"),
                    text_sha256=_hash("b"),
                    opportunity_row_hash=_hash("c"),
                    eligible_observation_count=100 if index < 18 else 130,
                    regime_id=regime_id,
                )
            )
    canonical_rows = tuple(sorted(rows, key=lambda row: row.sample_id))
    counts = (
        MidDevSourceRegimeCount.create("eligible-09", 36),
        MidDevSourceRegimeCount.create("eligible-10", 36),
    )
    payload = {
        "algorithm_version": MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
        "calibration_opportunity_audit_hash": _hash("d"),
        "regime_decision_hash": _hash("e"),
        "source_corpus_artifact_hash": _hash("f"),
        "source_manifest_hash": _hash("1"),
        "source_profile_hash": _hash("2"),
        "analysis_split_hash": _hash("3"),
        "source_opportunity_audit_hash": _hash("4"),
        "model_tokenizer_identity_hash": _hash("5"),
        "source_count": 36,
        "sample_count": 72,
        "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in canonical_rows),
        "regime_counts": tuple(item.payload() | {"count_hash": item.count_hash} for item in counts),
        "required_regime_ids": ("eligible-09", "eligible-10"),
    }
    from fuckmark.hashing import sha256_json
    return MidDevSourceOpportunityCoverageArtifact(
        algorithm_version=MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
        calibration_opportunity_audit_hash=_hash("d"),
        regime_decision_hash=_hash("e"),
        source_corpus_artifact_hash=_hash("f"),
        source_manifest_hash=_hash("1"),
        source_profile_hash=_hash("2"),
        analysis_split_hash=_hash("3"),
        source_opportunity_audit_hash=_hash("4"),
        model_tokenizer_identity_hash=_hash("5"),
        source_count=36,
        sample_count=72,
        rows=canonical_rows,
        regime_counts=counts,
        required_regime_ids=("eligible-09", "eligible-10"),
        artifact_hash=sha256_json(payload),
    )


def test_source_opportunity_coverage_roundtrip_is_canonical() -> None:
    artifact = _coverage()
    parsed = parse_mid_dev_source_opportunity_coverage_json(canonical_json_text(artifact))
    assert parsed == artifact
    assert parsed.required_regime_ids == ("eligible-09", "eligible-10")


def test_source_opportunity_coverage_rejects_incomplete_required_regime_set() -> None:
    artifact = _coverage()
    with pytest.raises(ValueError):
        replace(artifact, required_regime_ids=("eligible-09",))


def test_source_opportunity_cli_has_no_detector_scoring_import() -> None:
    source = Path("fuckmark/mid_dev_source_opportunity_audit_hf.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert all("detector_calibration" not in module for module in modules)
    assert all("tiny_dev_detector_hf" not in module for module in modules)


def test_source_opportunity_workflow_is_manual_and_pristine_only() -> None:
    source = Path(".github/workflows/middev-source-opportunity-audit.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "opportunity_run_id:" in source
    assert "push:" not in source
    assert "pull_request:" not in source
    assert "mid_dev_source_opportunity_audit_hf" in source
    assert "attack_transform_count" in source
    assert "detector_score_count" in source
