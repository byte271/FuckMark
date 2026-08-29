from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_static_website_package_is_present() -> None:
    web = ROOT / "web"
    assert (web / "package.json").is_file()
    assert (web / "index.html").is_file()
    assert (web / "mark.html").is_file()
    assert (web / "demo.html").is_file()
    assert (web / "limits.html").is_file()
    assert (web / "src" / "engine" / "index.ts").is_file()
    assert (web / "src" / "engine" / "generated" / "fixtures.json").is_file()
    assert (web / "src" / "engine" / "generated" / "letters.ts").is_file()
    package = (web / "package.json").read_text(encoding="utf-8")
    assert "vite" in package
    assert "vitest" in package
    readme = (web / "README.md").read_text(encoding="utf-8")
    assert "npm run build" in readme
    assert "static" in readme.casefold()
