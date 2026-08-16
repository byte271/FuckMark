import ast
import io
import re
import tokenize
from pathlib import Path


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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
        "spec.md",
    }
    assert required <= rules


def test_internal_release_metadata_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "SHA256SUMS.txt",
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
