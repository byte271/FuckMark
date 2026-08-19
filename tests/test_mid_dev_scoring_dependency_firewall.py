from __future__ import annotations

import ast
from pathlib import Path


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.append(node.module or "")
            values.extend(alias.name for alias in node.names)
    return tuple(values)


def test_production_middev_scorer_does_not_import_selection_implementation() -> None:
    root = Path(__file__).parents[1]
    paths = (
        root / "fuckmark" / "detector_calibration.py",
        root / "fuckmark" / "experiments" / "mid_dev_scored_schema.py",
        root / "fuckmark" / "experiments" / "mid_dev_scoring_contracts.py",
        root / "fuckmark" / "experiments" / "mid_dev_scoring_io.py",
        root / "fuckmark" / "experiments" / "mid_dev_scoring_safe.py",
        root / "fuckmark" / "experiments" / "mid_dev_trace_schema.py",
        root / "fuckmark" / "mid_dev_context_survival_score_hf.py",
    )
    forbidden = (
        "mid_dev_context_survival",
        "mid_dev_freeze",
        "mid_dev_plan_builder",
        "mid_dev_context_survival_plan_hf",
        "mid_dev_plan_io",
        "tiny_dev_transform_hf",
        "build_mid_dev_context_survival_plan",
        "ContextSurvivalExpander",
        "CandidateScheduler",
        "beam_v2",
        "beam_search_v2",
        "state_search",
        "greedy_search",
        "_stateful_random",
        "_baseline_variant",
    )
    for path in paths:
        imported = _imports(path)
        assert all(
            all(value not in name for value in forbidden)
            for name in imported
        ), (path, imported)
