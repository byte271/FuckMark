import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from fuckmark.product.scan import SCAN_CATEGORIES, classify_hidden_codepoint, scan_hidden_characters


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_WASM = ROOT / "editors" / "wasm" / "fuckmark_scan.wasm"
CANONICAL_JS = ROOT / "editors" / "wasm" / "scan_wasm.js"
WASM_COPIES = (
    ROOT / "docs" / "fuckmark_scan.wasm",
    ROOT / "fuckmark" / "webui" / "fuckmark_scan.wasm",
    ROOT / "editors" / "browser" / "fuckmark_scan.wasm",
)
JS_COPIES = (
    ROOT / "docs" / "scan_wasm.js",
    ROOT / "fuckmark" / "webui" / "scan_wasm.js",
    ROOT / "editors" / "browser" / "scan_wasm.js",
)
VECTORS = ROOT / "specs" / "fuckmark-hidden-scan-v1.vectors.json"
CRATE = ROOT / "crates" / "fuckmark-scan"
SCAN_JS = ROOT / "editors" / "vscode" / "scan.js"


def test_committed_wasm_module_is_copied_everywhere() -> None:
    assert CANONICAL_WASM.is_file()
    payload = CANONICAL_WASM.read_bytes()
    assert payload[:4] == b"\0asm"
    assert len(payload) > 1024
    for path in WASM_COPIES:
        assert path.read_bytes() == payload
    source = CANONICAL_JS.read_text(encoding="utf-8")
    assert "loadFuckMarkScanWasm" in source
    assert "fm_scan" in source
    for path in JS_COPIES:
        assert path.read_text(encoding="utf-8") == source


def test_scan_page_prefers_wasm_with_js_fallback() -> None:
    html = (ROOT / "docs" / "scan.html").read_text(encoding="utf-8")
    assert html == (ROOT / "fuckmark" / "webui" / "scan.html").read_text(encoding="utf-8")
    assert 'script src="scan.js"' in html
    assert 'script src="scan_wasm.js"' in html
    assert "fuckmark_scan.wasm" in html
    assert "loadFuckMarkScanWasm" in html
    assert "engine === \"wasm\"" in html
    popup = (ROOT / "editors" / "browser" / "popup.html").read_text(encoding="utf-8")
    assert 'script src="scan_wasm.js"' in popup


def test_rust_crate_unit_tests() -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    subprocess.run(
        [cargo, "test", "--manifest-path", str(CRATE / "Cargo.toml"), "--offline", "--quiet"],
        check=True,
        timeout=120,
    )


def _run_node_harness(harness: str, stdin: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        harness_path = handle.name
    try:
        return subprocess.run(
            [node, harness_path, str(CANONICAL_JS), str(SCAN_JS), str(CANONICAL_WASM)],
            input=stdin,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)


def test_wasm_replays_hidden_scan_vectors() -> None:
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))
    harness = r"""
"use strict";
const fs = require("fs");
const loader = require(process.argv[2]);
const fallback = require(process.argv[3]);
const wasmBytes = fs.readFileSync(process.argv[4]);
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
(async () => {
  globalThis.FuckMarkScan = fallback;
  const api = await loader.loadFuckMarkScanWasm(wasmBytes);
  const out = payload.vectors.map((vector) => {
    const text = String.fromCodePoint(...vector.codepoints);
    const result = api.scanText(text, null, vector.language || "auto");
    return result.findings.map((finding) => ({
      index: finding.index,
      codepoint: finding.codepoint,
      category: finding.category,
      context: finding.context,
      severity: finding.severity,
    }));
  });
  process.stdout.write(JSON.stringify(out));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    completed = _run_node_harness(harness, stdin=json.dumps(payload), timeout=30)
    actual = json.loads(completed.stdout)
    for vector, findings in zip(payload["vectors"], actual, strict=True):
        expected = [
            {
                "index": item["index"],
                "codepoint": item["codepoint"],
                "category": item["category"],
                "context": item["context"],
                "severity": item["severity"],
            }
            for item in vector["expect"]
        ]
        assert findings == expected, vector["id"]
        text = "".join(chr(code) for code in vector["codepoints"])
        python = scan_hidden_characters(text, language=vector.get("language"))
        assert len(python.findings) == len(findings), vector["id"]


def test_wasm_classify_matches_javascript_port() -> None:
    harness = r"""
"use strict";
const fs = require("fs");
const loader = require(process.argv[2]);
const fallback = require(process.argv[3]);
const wasmBytes = fs.readFileSync(process.argv[4]);
(async () => {
  globalThis.FuckMarkScan = fallback;
  const api = await loader.loadFuckMarkScanWasm(wasmBytes);
  const MAX = 0x10FFFF;
  for (let cp = 0; cp <= MAX; cp += 1) {
    const js = fallback.classify(cp);
    const wasm = api.classify(cp);
    if (js !== wasm) {
      process.stdout.write(JSON.stringify({ cp, js, wasm }));
      process.exit(2);
    }
  }
  process.stdout.write("ok");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    completed = _run_node_harness(harness, timeout=180)
    assert completed.stdout.startswith("ok")
    sample = (0x09, 0x61, 0x202E, 0x200B, 0x20DD, 0xE0061, 0x13430, 0xFFFD)
    for codepoint in sample:
        assert classify_hidden_codepoint(codepoint) in {None, *SCAN_CATEGORIES}


def test_wasm_routes_lone_surrogates_through_js_fallback() -> None:
    harness = r"""
"use strict";
const fs = require("fs");
const loader = require(process.argv[2]);
const fallback = require(process.argv[3]);
const wasmBytes = fs.readFileSync(process.argv[4]);
(async () => {
  globalThis.FuckMarkScan = fallback;
  const api = await loader.loadFuckMarkScanWasm(wasmBytes);
  const lone = "\uD800";
  if (!api.hasLoneSurrogate(lone)) throw new Error("expected lone surrogate");
  const scanned = api.scanText(lone, null, "auto");
  if (scanned.total !== 1) throw new Error("scan total " + scanned.total);
  if (scanned.findings[0].category !== "surrogate") throw new Error("category " + scanned.findings[0].category);
  const cleaned = api.cleanText(lone, null);
  if (cleaned.removed !== 1) throw new Error("removed " + cleaned.removed);
  if (cleaned.cleaned !== "") throw new Error("cleaned leftover");
  const empty = api.scanText("a\u202Eb", [], "auto");
  if (empty.total !== 0) throw new Error("empty categories should find nothing, got " + empty.total);
  const emptyClean = api.cleanText("a\u202Eb", []);
  if (emptyClean.removed !== 0 || emptyClean.cleaned !== "a\u202Eb") {
    throw new Error("empty categories should remove nothing");
  }
  if (api.encodeCategories(null) !== "*") throw new Error("null categories encoding");
  if (api.encodeCategories([]) !== "") throw new Error("empty array encoding");
  process.stdout.write("ok");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    completed = _run_node_harness(harness, timeout=30)
    assert completed.stdout.startswith("ok")
