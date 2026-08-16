import ast
from pathlib import Path


def test_transform_package_has_no_model_detector_network_or_ai_imports() -> None:
    root = Path(__file__).parents[1] / "fuckmark" / "transforms"
    banned = {
        "requests",
        "httpx",
        "torch",
        "transformers",
        "jax",
        "tensorflow",
        "openai",
        "anthropic",
        "fuckmark.detectors",
        "fuckmark.adapters",
    }
    found = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names if alias.name in banned)
            elif isinstance(node, ast.ImportFrom) and node.module in banned:
                found.add(node.module)
    assert found == set()
