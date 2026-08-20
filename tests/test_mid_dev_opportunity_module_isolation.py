from __future__ import annotations

import ast
from pathlib import Path


def test_pristine_opportunity_has_no_detector_scoring_module_dependency() -> None:
    source = Path("fuckmark/mid_dev_opportunity_audit_hf.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "detector_calibration" not in imported_modules
    assert "tiny_dev_detector_hf" not in imported_modules
    assert "encode_text" not in imported_names
    assert "default_watermark_payload" not in imported_names
    assert "HuggingFaceSynthIDAdapter" not in imported_names
    assert "HuggingFaceSynthIDConfig" not in imported_names
    assert "detector_calibration" not in source
    assert "tiny_dev_detector_hf" not in source
    assert "tokenizer.encode(text, add_special_tokens=False)" in source
