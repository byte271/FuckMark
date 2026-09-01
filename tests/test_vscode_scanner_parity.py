import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import pytest

from fuckmark.product.scan import SCAN_CATEGORIES, classify_hidden_codepoint


ROOT = Path(__file__).resolve().parents[1]
SCAN_JS = ROOT / "editors" / "vscode" / "scan.js"

_HARNESS = """
"use strict";
const scan = require(process.argv[2]);
const order = scan.SCAN_CATEGORIES;
const code = {};
order.forEach((name, index) => { code[name] = String.fromCharCode(97 + index); });
const MAX = 0x10FFFF;
const out = new Array(MAX + 1);
for (let cp = 0; cp <= MAX; cp += 1) {
  const category = scan.classify(cp);
  out[cp] = category === null ? "." : code[category];
}
process.stdout.write(out.join(""));
"""


def _encode(category):
    if category is None:
        return "."
    return chr(97 + SCAN_CATEGORIES.index(category))


def _is_true_noncharacter(codepoint):
    if 0xFDD0 <= codepoint <= 0xFDEF:
        return True
    return (codepoint & 0xFFFF) in {0xFFFE, 0xFFFF}


def test_scan_js_exists_and_exports_expected_categories():
    assert SCAN_JS.is_file()
    source = SCAN_JS.read_text(encoding="utf-8")
    assert "fuckmark-hidden-scan-v1" in source
    for name in SCAN_CATEGORIES:
        assert name in source


def test_vscode_scanner_matches_python_engine():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    assert SCAN_JS.is_file()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(_HARNESS)
        harness_path = handle.name
    try:
        completed = subprocess.run(
            [node, harness_path, str(SCAN_JS)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)
    js_encoded = completed.stdout
    assert len(js_encoded) == 0x10FFFF + 1

    mismatches = []
    for codepoint in range(0x10FFFF + 1):
        python_category = classify_hidden_codepoint(codepoint)
        js_char = js_encoded[codepoint]
        expected = _encode(python_category)
        if js_char == expected:
            continue
        if (
            python_category == "noncharacter"
            and js_char == "."
            and not _is_true_noncharacter(codepoint)
            and unicodedata.category(chr(codepoint)) == "Cn"
        ):
            continue
        mismatches.append((hex(codepoint), python_category, js_char))
        if len(mismatches) >= 20:
            break
    assert not mismatches, mismatches
