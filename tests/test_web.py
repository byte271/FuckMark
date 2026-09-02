import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fuckmark.cli import RELEASE_CLI_ALGORITHM_VERSION, main, process_text
from fuckmark.product.detect import DETECT_CONTACT_EMAIL
from fuckmark.product.domain import PRODUCT_MAX_INPUT_CHARS
from fuckmark.product.visible_projection import product_approved_carriers_v1, project_visible_v1
from fuckmark.web import health_payload, mark_html_path, remove_marks_payload, serve_mark_web, web_root


ROOT = Path(__file__).resolve().parents[1]
DEMO_SOURCE = "Hello from Q1z. Visible text stays."


def _get_json(url: str) -> tuple[int, dict[str, object]]:
    with urlopen(url, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, payload


def _post_json(url: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
    except HTTPError as error:
        payload = json.loads(error.read().decode("utf-8"))
        return error.code, payload


def test_packaged_mark_html_matches_docs_source() -> None:
    docs = (ROOT / "docs" / "mark.html").read_text(encoding="utf-8")
    packaged = (ROOT / "fuckmark" / "webui" / "mark.html").read_text(encoding="utf-8")
    assert packaged == docs
    assert mark_html_path().is_file()
    assert web_root() == mark_html_path().parent


def test_packaged_scan_page_matches_docs_and_editor_engine() -> None:
    docs_html = (ROOT / "docs" / "scan.html").read_text(encoding="utf-8")
    packaged_html = (ROOT / "fuckmark" / "webui" / "scan.html").read_text(encoding="utf-8")
    assert packaged_html == docs_html
    canonical_js = (ROOT / "editors" / "vscode" / "scan.js").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "scan.js").read_text(encoding="utf-8") == canonical_js
    assert (ROOT / "fuckmark" / "webui" / "scan.js").read_text(encoding="utf-8") == canonical_js
    assert 'script src="scan.js"' in docs_html
    assert 'script src="scan_wasm.js"' in docs_html
    assert "fuckmark_scan.wasm" in docs_html
    assert "loadFuckMarkScanWasm" in docs_html
    assert "FuckMarkScan" in docs_html
    assert "autofixTrojanSource" in docs_html
    assert "DEFAULT_SECURITY_CATEGORIES" in docs_html
    assert "fromCodePoint(0x202E)" in docs_html
    assert "truncated" in docs_html
    assert "bidi_control" in docs_html
    from fuckmark.product.scan import scan_hidden_characters

    assert scan_hidden_characters(docs_html, language="html").detected is False
    assert scan_hidden_characters(canonical_js, language="javascript").detected is False
    wasm_js = (ROOT / "docs" / "scan_wasm.js").read_text(encoding="utf-8")
    assert wasm_js == (ROOT / "fuckmark" / "webui" / "scan_wasm.js").read_text(encoding="utf-8")
    assert scan_hidden_characters(wasm_js, language="javascript").detected is False


def test_mark_html_miss_copy_is_english() -> None:
    html = mark_html_path().read_text(encoding="utf-8")
    assert "We did not detect a watermark in this text." in html
    assert "What? You think there is a watermark in this?" in html
    assert "Contact us" in html
    assert "Fhelp@q1z.org" in html
    assert "\u6211\u4eec" not in html
    assert "\u8054\u7cfb" not in html


def test_mark_html_calls_python_remove_marks_api() -> None:
    html = mark_html_path().read_text(encoding="utf-8")
    assert "/api/health" in html
    assert "/api/remove-marks" in html
    assert 'payload.backend === "python"' in html
    assert "scanViaPython" in html
    assert "scanLocal" in html
    assert "detectFuckMark" in html


def test_health_and_remove_marks_payloads_use_python_detector() -> None:
    health = health_payload()
    assert health["ok"] is True
    assert health["backend"] == "python"
    assert health["cli_algorithm_version"] == RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v12"
    assert health["contact"] == DETECT_CONTACT_EMAIL

    miss = remove_marks_payload(DEMO_SOURCE)
    assert miss["ok"] is False
    assert miss["reason"] == "not-detected"
    assert miss["backend"] == "python"
    assert miss["text"] == DEMO_SOURCE
    assert miss["detect"]["detected"] is False

    mixed = process_text(DEMO_SOURCE)
    assert mixed != DEMO_SOURCE
    hit = remove_marks_payload(mixed)
    assert hit["ok"] is True
    assert hit["reason"] == "stripped"
    assert hit["backend"] == "python"
    assert hit["text"] == DEMO_SOURCE
    assert hit["text"] == project_visible_v1(mixed, product_approved_carriers_v1())
    assert int(hit["removed"]) > 0
    assert hit["detect"]["detected"] is True
    assert hit["contact"] == DETECT_CONTACT_EMAIL

    huge = remove_marks_payload("a" * (PRODUCT_MAX_INPUT_CHARS + 1))
    assert huge["ok"] is False
    assert huge["reason"] == "too-large"
    assert huge["text"] == ""
    assert huge["max"] == PRODUCT_MAX_INPUT_CHARS


def test_fuckmark_web_serves_mark_page() -> None:
    errors = StringIO()
    seen: dict[str, object] = {}

    def on_ready(url: str, port: int) -> None:
        seen["url"] = url
        seen["port"] = port
        with urlopen(url, timeout=2) as response:
            seen["body"] = response.read().decode("utf-8")
            seen["cache"] = response.headers.get("Cache-Control")
        with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            seen["index"] = response.read().decode("utf-8")
        with urlopen(f"http://127.0.0.1:{port}/scan.html", timeout=2) as response:
            seen["scan_html"] = response.read().decode("utf-8")
            seen["scan_cache"] = response.headers.get("Cache-Control")
        with urlopen(f"http://127.0.0.1:{port}/scan.js", timeout=2) as response:
            seen["scan_js"] = response.read().decode("utf-8")
        with urlopen(f"http://127.0.0.1:{port}/scan_wasm.js", timeout=2) as response:
            seen["scan_wasm_js"] = response.read().decode("utf-8")
        with urlopen(f"http://127.0.0.1:{port}/fuckmark_scan.wasm", timeout=2) as response:
            seen["scan_wasm"] = response.read()
            seen["scan_wasm_type"] = response.headers.get("Content-Type")
        health_status, health = _get_json(f"http://127.0.0.1:{port}/api/health")
        seen["health_status"] = health_status
        seen["health"] = health
        mixed = process_text(DEMO_SOURCE)
        hit_status, hit = _post_json(f"http://127.0.0.1:{port}/api/remove-marks", {"text": mixed})
        seen["hit_status"] = hit_status
        seen["hit"] = hit
        miss_status, miss = _post_json(
            f"http://127.0.0.1:{port}/api/remove-marks", {"text": DEMO_SOURCE}
        )
        seen["miss_status"] = miss_status
        seen["miss"] = miss
        detect_status, detect = _post_json(
            f"http://127.0.0.1:{port}/api/detect", {"text": mixed}
        )
        seen["detect_status"] = detect_status
        seen["detect"] = detect

    url, port = serve_mark_web(
        host="127.0.0.1",
        port=0,
        open_browser=False,
        errors=errors,
        serve_seconds=0.05,
        on_ready=on_ready,
    )
    assert port > 0
    assert url == seen["url"]
    assert url.endswith("/mark.html")
    log = errors.getvalue()
    assert "FuckMark web:" in log
    assert "Python API" in log
    assert "/api/remove-marks" in log
    assert "/scan.html" in log
    body = str(seen["body"])
    assert "FuckMark" in body
    assert "detectFuckMark" in body
    assert "scanViaPython" in body
    assert "/api/remove-marks" in body
    assert "We did not detect a watermark in this text." in body
    assert "detectFuckMark" in str(seen["index"])
    scan_html = str(seen["scan_html"])
    assert "See the bytes." in scan_html
    assert 'script src="scan.js"' in scan_html
    assert 'script src="scan_wasm.js"' in scan_html
    assert "FuckMarkScan" in str(seen["scan_js"])
    assert "loadFuckMarkScanWasm" in str(seen["scan_wasm_js"])
    wasm_bytes = seen["scan_wasm"]
    assert isinstance(wasm_bytes, (bytes, bytearray))
    assert bytes(wasm_bytes[:4]) == b"\0asm"
    assert "wasm" in str(seen.get("scan_wasm_type") or "").casefold()
    assert "no-store" in str(seen.get("scan_cache", "")).casefold()
    assert "no-store" in str(seen.get("cache", "")).casefold()
    assert seen["health_status"] == 200
    health = seen["health"]
    assert isinstance(health, dict)
    assert health["backend"] == "python"
    assert health["ok"] is True
    assert seen["hit_status"] == 200
    hit = seen["hit"]
    assert isinstance(hit, dict)
    assert hit["backend"] == "python"
    assert hit["ok"] is True
    assert hit["reason"] == "stripped"
    assert hit["text"] == DEMO_SOURCE
    assert int(hit["removed"]) > 0
    miss = seen["miss"]
    assert isinstance(miss, dict)
    assert seen["miss_status"] == 200
    assert miss["ok"] is False
    assert miss["reason"] == "not-detected"
    detect = seen["detect"]
    assert isinstance(detect, dict)
    assert seen["detect_status"] == 200
    assert detect["backend"] == "python"
    assert detect["ok"] is True
    inner = detect["detect"]
    assert isinstance(inner, dict)
    assert inner["detected"] is True


def test_cli_web_help_documents_browser_tool() -> None:
    assert RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v12"
    out = StringIO()
    errors = StringIO()
    with redirect_stdout(out):
        status = main(StringIO(""), StringIO(), error_stream=errors, argv=("web", "--help"))
    assert status == 0
    help_text = out.getvalue() + errors.getvalue()
    assert "fuckmark web" in help_text
    assert "Python API" in help_text
    assert "scan.html" in help_text
    assert "browser" in help_text.casefold() or "beginner" in help_text.casefold()


def test_web_api_rejects_missing_content_length() -> None:
    import socket

    errors = StringIO()
    seen: dict[str, object] = {}

    def on_ready(_url: str, port: int) -> None:
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            sock.sendall(
                b"POST /api/scan HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                b'{"text":"\\u202e"}'
            )
            payload = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                payload += chunk
        finally:
            sock.close()
        seen["raw"] = payload

    serve_mark_web(
        host="127.0.0.1",
        port=0,
        open_browser=False,
        errors=errors,
        serve_seconds=0.05,
        on_ready=on_ready,
    )
    raw = seen["raw"]
    assert isinstance(raw, (bytes, bytearray))
    header = bytes(raw).split(b"\r\n", 1)[0]
    assert b"400" in header
    assert b"missing Content-Length" in raw or b"bad-request" in raw


def test_web_json_escapes_lone_surrogates_as_valid_utf8() -> None:
    errors = StringIO()
    seen: dict[str, object] = {}

    def on_ready(_url: str, port: int) -> None:
        encoded = json.dumps({"text": "\ud800", "on_findings": "report"}).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{port}/api/guard",
            data=encoded,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            raw = response.read()
            seen["raw"] = raw
            seen["status"] = response.status
            seen["payload"] = json.loads(raw.decode("utf-8"))
        miss_body = json.dumps({"text": "plain\ud800"}).encode("utf-8")
        miss_request = Request(
            f"http://127.0.0.1:{port}/api/remove-marks",
            data=miss_body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(miss_request, timeout=5) as response:
            miss_raw = response.read()
            seen["miss_raw"] = miss_raw
            seen["miss"] = json.loads(miss_raw.decode("utf-8"))

    serve_mark_web(
        host="127.0.0.1",
        port=0,
        open_browser=False,
        errors=errors,
        serve_seconds=0.05,
        on_ready=on_ready,
    )
    raw = seen["raw"]
    assert isinstance(raw, (bytes, bytearray))
    assert b"\xed\xa0\x80" not in raw
    raw.decode("utf-8")
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["ok"] is True
    assert payload["value"] == "\ud800"
    miss_raw = seen["miss_raw"]
    assert isinstance(miss_raw, (bytes, bytearray))
    assert b"\xed\xa0\x80" not in miss_raw
    miss_raw.decode("utf-8")
    miss = seen["miss"]
    assert isinstance(miss, dict)
    assert miss["ok"] is False
    assert miss["text"] == "plain\ud800"
