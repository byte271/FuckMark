import ast
from pathlib import Path


def _imports(path: str):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.append(node.module or "")
    return tuple(values)


def test_v5_planning_path_does_not_import_detector_or_scoring_modules():
    paths = (
        "fuckmark/experiments/mid_dev_v5_builder.py",
        "fuckmark/search/normalized_random_safe.py",
        "fuckmark/search/visible_cost_budget.py",
    )
    banned = ("detector", "mid_dev_v5_scoring", "calibration_audit", "scoring_safe")
    for path in paths:
        bad = [name for name in _imports(path) if any(token in name.lower() for token in banned)]
        assert bad == [], f"{path} imported prohibited planner dependency: {bad}"


def test_v5_scoring_path_explicitly_owns_detector_and_frozen_threshold_dependencies():
    imports = _imports("fuckmark/experiments/mid_dev_v5_scoring.py")
    assert any("detector" in value.lower() for value in imports)
    assert any("mid_dev_calibration_audit" in value for value in imports)


def test_real_middev_is_still_hard_blocked_while_scoring_layer_is_unfrozen():
    workflow = Path(".github/workflows/mid-dev-context-survival.yml").read_text(encoding="utf-8")
    assert "PRE_RUN_LOCK_REQUIRED_AND_VNEXT_WORKFLOW_NOT_YET_FROZEN" in workflow
    assert "Block legacy execution until vNext plan is frozen" in workflow
