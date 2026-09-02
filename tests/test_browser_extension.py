import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from fuckmark.product.scan import scan_hidden_characters


ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "editors" / "browser"
VSCODE_SCAN = ROOT / "editors" / "vscode" / "scan.js"
MANIFEST = BROWSER / "manifest.json"


def test_browser_scan_js_matches_vscode_engine() -> None:
    assert (BROWSER / "scan.js").read_text(encoding="utf-8") == VSCODE_SCAN.read_text(encoding="utf-8")


def test_manifest_is_mv3_and_local() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["manifest_version"] == 3
    assert payload["version"] == "0.4.1"
    assert "clipboardRead" not in payload.get("permissions", [])
    assert payload["action"]["default_popup"] == "popup.html"
    assert payload["background"]["service_worker"] == "background.js"
    scripts = payload["content_scripts"][0]["js"]
    assert scripts == ["scan.js", "page.js", "content.js"]
    for name in ("externally_connectable", "update_url", "key"):
        assert name not in payload


def test_extension_files_have_no_hidden_unicode() -> None:
    for path in BROWSER.iterdir():
        if not path.is_file():
            continue
        if path.suffix not in {".js", ".html", ".json", ".md", ".css"}:
            continue
        language = "html" if path.suffix == ".html" else "javascript" if path.suffix == ".js" else "auto"
        result = scan_hidden_characters(path.read_text(encoding="utf-8"), language=language)
        assert result.detected is False, path


def test_popup_and_readme_document_local_engine() -> None:
    popup = (BROWSER / "popup.html").read_text(encoding="utf-8")
    readme = (BROWSER / "README.md").read_text(encoding="utf-8")
    assert 'script src="scan.js"' in popup
    assert 'script src="page.js"' in popup
    assert "Paste-safe" in popup
    assert "fromCodePoint(0x202E)" in (BROWSER / "popup.js").read_text(encoding="utf-8")
    assert "Load unpacked" in readme
    assert "fuckmark-hidden-scan-v1" in readme
    assert "never leaves" in readme


def test_page_js_paste_safe_and_emoji_keep() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    harness = """
"use strict";
const page = require(process.argv[2]);
const rlo = String.fromCodePoint(0x202E);
const zwj = String.fromCodePoint(0x200D);
const man = String.fromCodePoint(0x1F468);
const woman = String.fromCodePoint(0x1F469);
const ident = page.cleanForPaste("if (x != " + rlo + "admin) {");
if (ident.removed !== 1) throw new Error("expected one bidi strip, got " + ident.removed);
if (ident.cleaned.includes(rlo)) throw new Error("bidi remained");
const emoji = page.cleanForPaste(man + zwj + woman);
if (emoji.removed !== 0) throw new Error("emoji ZWJ should be kept, removed=" + emoji.removed);
if (emoji.cleaned !== man + zwj + woman) throw new Error("emoji rewritten");
const tags = page.cleanForPaste("ok" + String.fromCodePoint(0xE0061));
if (tags.removed !== 1) throw new Error("tag should strip");
const scan = page.scanString("// " + rlo, "javascript");
if (scan.findings[0].context !== "comment") throw new Error("comment context");
if (scan.findings[0].severity !== "critical") throw new Error("comment severity");
process.stdout.write("ok");
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        harness_path = handle.name
    try:
        completed = subprocess.run(
            [node, harness_path, str(BROWSER / "page.js")],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)
    assert completed.stdout == "ok"


def test_browser_js_syntax() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    for name in ("scan.js", "page.js", "content.js", "background.js", "popup.js"):
        subprocess.run([node, "--check", str(BROWSER / name)], check=True, timeout=15)
