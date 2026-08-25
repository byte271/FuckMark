from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _argparse_default(path: Path, option: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if not any(
            isinstance(argument, ast.Constant) and argument.value == option
            for argument in node.args
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value
        raise AssertionError(f"{option} has no literal default in {path}")
    raise AssertionError(f"{option} is not defined in {path}")


def test_cycle6_reproduction_tools_default_to_selected_b14_budget() -> None:
    paths = (
        ROOT / "tools" / "build_cycle6_quote_fidelity_packet.py",
        ROOT / "tools" / "cycle6_geometry_report.py",
    )
    for path in paths:
        assert _argparse_default(path, "--budget") == 14
