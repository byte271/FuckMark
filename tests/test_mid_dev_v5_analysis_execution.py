from pathlib import Path

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.experiments.mid_dev_context_survival import MidDevCondition
from fuckmark.experiments.mid_dev_legacy_trace_io import parse_mid_dev_selection_trace_artifact_json
from fuckmark.experiments.mid_dev_plan_builder import MidDevSelectionTrace, MidDevSelectionTraceArtifact
from fuckmark.experiments.mid_dev_plan_io import MidDevPlanJsonError
from fuckmark.hashing import sha256_text


def _legacy_trace() -> MidDevSelectionTrace:
    return MidDevSelectionTrace.create(
        source_group_id="group-0001",
        sample_id="sample-0001",
        condition=MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
        budget=1,
        replicate=0,
        schedule_seed=123,
        candidate_pool_hash=sha256_text("pool"),
        scheduler_input_hash=sha256_text("scheduler-input"),
        schedule_result_hash=sha256_text("schedule-result"),
        final_search_state_hash=sha256_text("state"),
        operation_hashes=(sha256_text("operation"),),
        transition_hashes=(sha256_text("transition"),),
        status="SUCCESS",
    )


def test_legacy_trace_artifact_canonical_round_trip():
    artifact = MidDevSelectionTraceArtifact.create(
        plan_hash=sha256_text("plan"),
        traces=(_legacy_trace(),),
    )
    text = canonical_json_text(artifact)
    assert parse_mid_dev_selection_trace_artifact_json(text) == artifact
    with pytest.raises(MidDevPlanJsonError, match="not canonical"):
        parse_mid_dev_selection_trace_artifact_json(text + " ")


def test_v5_analysis_cli_is_analysis_only_and_does_not_load_synthid_adapter():
    source = Path("fuckmark/mid_dev_v5_analyze_hf.py").read_text(encoding="utf-8").lower()
    assert "huggingfacesynthidadapter" not in source
    assert "from .adapters" not in source
    assert "default_watermark_payload" not in source
    assert "score_mid_dev_development_plan_v5" not in source
    assert "build_mid_dev_development_plan_v5" not in source
    assert "build_frozen_calibration_threshold_registry" not in source
    assert "calibrate_detector" not in source
    assert "build_mid_dev_v5_geometry_audit" in source
    assert "build_mid_dev_v5_rule_usage_artifact" in source
    assert "build_mid_dev_v5_analysis_artifact" in source


def test_v5_analysis_cli_requires_scoring_provenance_and_frozen_inputs():
    source = Path("fuckmark/mid_dev_v5_analyze_hf.py").read_text(encoding="utf-8")
    for argument in (
        "--corpus-json",
        "--plan-json",
        "--legacy-trace-json",
        "--normalized-trace-json",
        "--scoring-json",
        "--scoring-provenance-json",
        "--opportunity-audit-json",
    ):
        assert argument in source
    assert "separate_scoring_process" in source
    assert "analysis started before scoring finished" in source
    assert "human_audit_status" in source
