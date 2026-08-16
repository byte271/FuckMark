from pathlib import Path


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
