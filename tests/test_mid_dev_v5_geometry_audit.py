import ast
from pathlib import Path

import pytest

from fuckmark.experiments.mid_dev_v5_geometry_audit import (
    MID_DEV_V5_REPETITION_MASK_GROWTH_CAP,
    MidDevV5GeometryAuditRow,
)
from fuckmark.hashing import sha256_text


def _row(**overrides):
    values = {
        "scored_row_hash": sha256_text("scored-row"),
        "plan_row_hash": sha256_text("plan-row"),
        "sample_id": "sample-0001",
        "transformed_text_hash": sha256_text("text"),
        "residual_geometry_hash": sha256_text("geometry"),
        "root_valid_observation_count": 100,
        "final_valid_observation_count": 95,
        "repetition_mask_delta": 0,
        "eos_mask_delta": 0,
        "residual_inherited_fraction": 0.50,
        "new_context_opportunity_fraction": 0.50,
        "valid_denominator_ratio": 0.95,
        "alignment_distance": 2,
    }
    values.update(overrides)
    return MidDevV5GeometryAuditRow.create(**values)


def test_geometry_audit_freezes_zero_repetition_mask_growth_cap():
    assert MID_DEV_V5_REPETITION_MASK_GROWTH_CAP == 0
    row = _row()
    assert row.repetition_mask_delta == 0


def test_geometry_audit_row_allows_negative_mask_delta_but_rejects_invalid_counts():
    assert _row(repetition_mask_delta=-2).repetition_mask_delta == -2
    with pytest.raises(ValueError, match="positive valid observation"):
        _row(final_valid_observation_count=0)


def test_geometry_audit_module_is_detector_free():
    path = Path("fuckmark/experiments/mid_dev_v5_geometry_audit.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any("detectors" in name.lower() for name in imports)
    assert not any("adapter" in name.lower() for name in imports)
