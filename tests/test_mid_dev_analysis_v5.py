import ast
from pathlib import Path

from fuckmark.experiments.mid_dev_analysis_v5 import (
    MID_DEV_V5_CELL_ELIGIBLE,
    MID_DEV_V5_CELL_INELIGIBLE,
    MID_DEV_V5_HUMAN_AUDIT_PENDING,
    MidDevV5SourceEffect,
    _make_comparison,
)
from fuckmark.experiments.mid_dev_pre_run_lock import PRE_RUN_BOOTSTRAP_SEED_BASE


def _effect(index: int) -> MidDevV5SourceEffect:
    value = index / 1000.0
    return MidDevV5SourceEffect.create(
        source_group_id=f"group-{index:02d}",
        cell_id="MATCHED_BEAM_V2_STRICT",
        target_length=128 if index % 2 == 0 else 256,
        watermarked_random_count=16,
        control_random_count=16,
        watermarked_margin_advantage=value + 0.02,
        control_margin_advantage=value,
        control_adjusted_margin_advantage=0.02,
        watermarked_rif_advantage=value + 0.01,
        control_rif_advantage=value,
        control_adjusted_rif_advantage=0.01,
    )


def test_v5_matched_comparison_uses_source_groups_and_10000_bootstrap_replicates():
    effects = tuple(_effect(index) for index in range(32))
    comparison = _make_comparison(
        "MATCHED_BEAM_V2_STRICT",
        effects,
        tuple(f"group-{index:02d}" for index in range(32, 36)),
        PRE_RUN_BOOTSTRAP_SEED_BASE,
    )
    assert comparison.status == MID_DEV_V5_CELL_ELIGIBLE
    assert comparison.eligible_source_group_count == 32
    assert comparison.bootstrap_replicates == 10_000
    assert comparison.margin_bootstrap_lower <= comparison.mean_control_adjusted_margin_advantage <= comparison.margin_bootstrap_upper
    assert comparison.rif_bootstrap_lower <= comparison.mean_control_adjusted_rif_advantage <= comparison.rif_bootstrap_upper


def test_v5_matched_comparison_reports_but_does_not_infer_below_32_groups():
    effects = tuple(_effect(index) for index in range(31))
    comparison = _make_comparison(
        "MATCHED_BEAM_V2_STRICT",
        effects,
        tuple(f"group-{index:02d}" for index in range(31, 36)),
        PRE_RUN_BOOTSTRAP_SEED_BASE,
    )
    assert comparison.status == MID_DEV_V5_CELL_INELIGIBLE
    assert comparison.bootstrap_replicates == 0
    assert comparison.mean_control_adjusted_margin_advantage is None
    assert comparison.margin_bootstrap_lower is None
    assert comparison.mean_control_adjusted_rif_advantage is None


def test_v5_analysis_has_no_confirmatory_p_value_or_threshold_tuning_path():
    path = Path("fuckmark/experiments/mid_dev_analysis_v5.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    identifiers = set()
    string_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            identifiers.add(node.name.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_literals.append(node.value.lower())
    assert not any(name == "p_value" or name.endswith("_p_value") for name in identifiers)
    assert not any("p-value" in value for value in string_literals)
    lowered = source.lower()
    assert "calibrate_detector" not in lowered
    assert "build_frozen_calibration_threshold_registry" not in lowered
    assert "threshold_value =" not in lowered
    assert MID_DEV_V5_HUMAN_AUDIT_PENDING == "PENDING"
