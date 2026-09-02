import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.product.scan import scan_hidden_characters


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "specs"
PROTOCOL = SPEC_DIR / "fuckmark-hidden-scan-v1.protocol.md"
VECTORS = SPEC_DIR / "fuckmark-hidden-scan-v1.vectors.json"
FREEZE = SPEC_DIR / "fuckmark-hidden-scan-v1.freeze.json"
SCAN_JS = ROOT / "editors" / "vscode" / "scan.js"


def _load_vectors() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


def test_hidden_scan_freeze_binds_protocol_and_vectors() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    payload = _load_vectors()
    assert freeze["algorithm_version"] == "fuckmark-hidden-scan-v1"
    assert freeze["protocol_id"] == "fuckmark-hidden-scan-v1"
    assert freeze["protocol_sha256"] == sha256_file(PROTOCOL)
    assert freeze["vectors_file_sha256"] == sha256_file(VECTORS)
    assert freeze["vectors_canonical_sha256"] == sha256_json(payload)
    assert payload["algorithm_version"] == "fuckmark-hidden-scan-v1"
    assert "fuckmark-hidden-scan-v1" in PROTOCOL.read_text(encoding="utf-8")


def test_hidden_scan_vectors_replay_on_python_engine() -> None:
    payload = _load_vectors()
    for vector in payload["vectors"]:
        text = "".join(chr(code) for code in vector["codepoints"])
        result = scan_hidden_characters(text, language=vector.get("language"))
        expected = vector["expect"]
        assert len(result.findings) == len(expected), vector["id"]
        for finding, want in zip(result.findings, expected, strict=True):
            assert finding.index == want["index"], vector["id"]
            assert finding.codepoint == want["codepoint"], vector["id"]
            assert finding.category == want["category"], vector["id"]
            assert finding.context == want["context"], vector["id"]
            assert finding.severity == want["severity"], vector["id"]
        if not expected:
            assert result.detected is False


def test_hidden_scan_js_replays_vector_verdicts() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    payload = _load_vectors()
    harness = """
"use strict";
const scan = require(process.argv[2]);
const payload = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = payload.vectors.map((vector) => {
  const text = String.fromCodePoint(...vector.codepoints);
  const result = scan.scanText(text, null, vector.language || "auto");
  return result.findings.map((finding) => ({
    codepoint: finding.codepoint,
    category: finding.category,
    context: finding.context,
    severity: finding.severity,
  }));
});
process.stdout.write(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        harness_path = handle.name
    try:
        completed = subprocess.run(
            [node, harness_path, str(SCAN_JS)],
            input=json.dumps(payload),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)
    js_findings = json.loads(completed.stdout)
    for vector, actual in zip(payload["vectors"], js_findings, strict=True):
        expected = [
            {
                "codepoint": item["codepoint"],
                "category": item["category"],
                "context": item["context"],
                "severity": item["severity"],
            }
            for item in vector["expect"]
        ]
        assert actual == expected, vector["id"]


def test_scan_js_syntax() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    subprocess.run([node, "--check", str(SCAN_JS)], check=True, timeout=15)
    extension = ROOT / "editors" / "vscode" / "extension.js"
    subprocess.run([node, "--check", str(extension)], check=True, timeout=15)
    copies = (
        ROOT / "docs" / "scan.js",
        ROOT / "fuckmark" / "webui" / "scan.js",
    )
    canonical = SCAN_JS.read_text(encoding="utf-8")
    for path in copies:
        assert path.read_text(encoding="utf-8") == canonical
        subprocess.run([node, "--check", str(path)], check=True, timeout=15)
