from __future__ import annotations

import ast
from pathlib import Path


def test_middev_planning_side_has_no_detector_or_secret_imports() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "fuckmark" / "corpus" / "mid_dev.py",
        root / "fuckmark" / "corpus" / "mid_dev_generation.py",
        root / "fuckmark" / "corpus" / "mid_dev_io.py",
        root / "fuckmark" / "corpus" / "mid_dev_validation.py",
        root / "fuckmark" / "experiments" / "mid_dev_freeze.py",
        root / "fuckmark" / "experiments" / "mid_dev_plan_builder.py",
        root / "fuckmark" / "experiments" / "mid_dev_quality.py",
        root / "fuckmark" / "mid_dev_context_survival_plan_hf.py",
    )
    forbidden = (
        "detector",
        "g_value",
        "gvalue",
        "bayesian",
        "watermark_key",
        "secret_key",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
        assert all(
            not any(value in name.lower() for value in forbidden)
            for name in imported
        ), (path, imported)
