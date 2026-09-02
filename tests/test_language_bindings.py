import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fuckmark.native_scan import available, clean_text, library_path, scan_text
from fuckmark.product.scan import scan_hidden_characters


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "specs" / "fuckmark-hidden-scan-v1.vectors.json"
CRATE = ROOT / "crates" / "fuckmark-scan"
NODE_BIND = ROOT / "bindings" / "node"


def test_c_header_and_binding_docs_exist() -> None:
    assert (CRATE / "include" / "fuckmark_scan.h").is_file()
    header = (CRATE / "include" / "fuckmark_scan.h").read_text(encoding="utf-8")
    assert "fm_scan" in header
    assert "fm_clean" in header
    assert "fm_classify" in header
    assert (ROOT / "bindings" / "README.md").is_file()
    assert "FUCKMARK_SCAN_LIB" in (ROOT / "bindings" / "README.md").read_text(encoding="utf-8")


def test_native_library_matches_python_vectors() -> None:
    if not available():
        cargo = shutil.which("cargo")
        if cargo is None:
            pytest.skip("cargo is not available")
        subprocess.run(
            ["sh", str(CRATE / "build-native.sh")],
            check=True,
            timeout=180,
        )
    assert available()
    assert library_path() is not None
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    for vector in payload["vectors"]:
        text = "".join(chr(code) for code in vector["codepoints"])
        native = scan_text(text, language=vector.get("language") or "auto")
        python = scan_hidden_characters(text, language=vector.get("language"))
        assert native["total"] == python.total, vector["id"]
        assert len(native["findings"]) == len(python.findings), vector["id"]
        for left, right in zip(native["findings"], python.findings, strict=True):
            assert left["index"] == right.index, vector["id"]
            assert left["codepoint"] == right.codepoint, vector["id"]
            assert left["category"] == right.category, vector["id"]
            assert left["context"] == right.context, vector["id"]
            assert left["severity"] == right.severity, vector["id"]


def test_native_empty_categories_and_clean() -> None:
    if not available():
        pytest.skip("native library is not available")
    text = "a\u202eb\u200bc"
    empty = scan_text(text, categories=[])
    assert empty["total"] == 0
    cleaned, removed = clean_text(text, categories=["bidi_control"])
    assert removed == 1
    assert cleaned == "ab\u200bc"


def test_node_binding_assets_and_tests() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    subprocess.run([node, str(NODE_BIND / "sync-assets.js")], check=True, timeout=30)
    for name in ("scan_wasm.js", "fuckmark_scan.wasm", "scan.js"):
        assert (NODE_BIND / name).is_file()
    completed = subprocess.run(
        [node, str(NODE_BIND / "test.js")],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.stdout.strip() == "ok"
