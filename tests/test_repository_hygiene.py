import ast
import io
import re
import tokenize
from pathlib import Path

import pytest


_CJK_RE = re.compile(r"[\u2e80-\u2eff\u2f00-\u2fdf\u3005\u3007\u303b\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]")


def test_gitignore_excludes_generated_artifacts_and_local_secrets() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = set((root / ".gitignore").read_text(encoding="utf-8").splitlines())
    required = {
        "__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".hypothesis/",
        "build/",
        "dist/",
        "*.egg-info/",
        ".venv/",
        ".env",
        ".env.*",
    }
    assert required <= rules
    assert "spec.md" not in rules


def test_internal_release_metadata_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "VERSION_LOCK.json",
        "ARTIFACT_REVISION.json",
        "PROJECT_IDENTITY.json",
    }
    assert forbidden.isdisjoint(path.name for path in root.iterdir())


def test_python_files_have_no_comments_or_docstrings() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        assert all(token.type != tokenize.COMMENT for token in tokens), path
        tree = ast.parse(text, filename=str(path))
        nodes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        assert all(ast.get_docstring(node, clean=False) is None for node in ast.walk(tree) if isinstance(node, nodes)), path


def test_project_text_has_no_cjk_characters() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".toml", ".json"}:
            continue
        assert _CJK_RE.search(path.read_text(encoding="utf-8")) is None, path


@pytest.mark.parametrize(
    "codepoint",
    (
        0x2E80,
        0x2F00,
        0x3005,
        0x3007,
        0x303B,
        0x3400,
        0x4E00,
        0xF900,
        0x20000,
        0x2A700,
        0x2B740,
        0x2B820,
        0x2CEB0,
        0x30000,
        0x31350,
    ),
)
def test_cjk_hygiene_regex_covers_all_ideograph_blocks(codepoint: int) -> None:
    assert _CJK_RE.search(chr(codepoint)) is not None
