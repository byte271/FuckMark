from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ..hashing import sha256_json, sha256_text
from ..product.rendering import chrome_executable, compare_chrome_pre_screenshots


BENCHMARK_RENDER_VERSION = "cycle8-benchmark-render-v2"
BENCHMARK_RENDER_FONT = "DejaVu Sans Mono"


def chrome_version(executable: str | None = None) -> str | None:
    path = executable if executable is not None else chrome_executable()
    if path is None:
        return None
    try:
        output = subprocess.check_output([path, "--version"], timeout=10, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        return output.decode("utf-8").strip()
    except UnicodeError:
        return None


def _html_surface(text: str, surface: str) -> str:
    payload = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    if surface == "textarea":
        body = (
            "<textarea id='t' spellcheck='false' "
            "style=\"margin:16px;width:760px;height:160px;border:0;resize:none;"
            "caret-color:transparent;outline:none;font:16px/24px 'DejaVu Sans Mono',monospace;"
            "color:#000;background:#fff\"></textarea>"
        )
        assign = f"el.value={payload};actual=el.value;"
    elif surface == "contenteditable":
        body = (
            "<div id='t' contenteditable='true' spellcheck='false' "
            "style=\"margin:16px;width:760px;min-height:160px;caret-color:transparent;"
            "font:16px/24px 'DejaVu Sans Mono',monospace;color:#000;background:#fff;"
            "white-space:pre-wrap\"></div>"
        )
        assign = f"el.textContent={payload};actual=el.textContent;"
    else:
        raise ValueError("unknown render surface")
    script = (
        "var el=document.getElementById('t');var actual='';"
        f"{assign}"
        f"if(actual!=={payload}){{document.body.style.background='#f00';"
        "document.body.setAttribute('data-fm-render','mismatch');}"
        "else{document.body.setAttribute('data-fm-render','ok');}"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;background:#fff'>"
        f"{body}"
        f"<script>{script}</script>"
        "</body></html>"
    )


def displayed_js_property(surface: str) -> str:
    if surface == "textarea":
        return "value"
    if surface == "contenteditable":
        return "textContent"
    raise ValueError("unknown render surface")


def _screenshot(executable: str, root: Path, name: str, html: str) -> bytes:
    html_path = root / f"{name}.html"
    png_path = root / f"{name}.png"
    html_path.write_text(html, encoding="utf-8")
    process = subprocess.Popen(
        [
            executable,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-background-networking",
            "--virtual-time-budget=5000",
            "--window-size=800,240",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if png_path.exists() and png_path.stat().st_size > 0:
                time.sleep(0.25)
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    if not png_path.exists() or png_path.stat().st_size <= 0:
        raise RuntimeError("chromium screenshot missing")
    return png_path.read_bytes()


def compare_chrome_surface(original: str, transformed: str, surface: str) -> dict[str, object]:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    if surface not in {"textarea", "contenteditable"}:
        raise ValueError("unknown render surface")
    environment = f"chromium_{surface}"
    executable = chrome_executable()
    original_sha = sha256_text(original)
    transformed_sha = sha256_text(transformed)
    browser = chrome_version(executable)
    if executable is None:
        payload = {
            "algorithm_version": BENCHMARK_RENDER_VERSION,
            "environment": environment,
            "status": "UNKNOWN",
            "original_sha256": original_sha,
            "transformed_sha256": transformed_sha,
            "equal": None,
            "detail": "no chromium executable on this host",
            "font": BENCHMARK_RENDER_FONT,
            "browser_version": browser,
        }
        return {**payload, "comparison_hash": sha256_json(payload)}
    try:
        with tempfile.TemporaryDirectory(prefix="fuckmark-bench-render-") as directory:
            root = Path(directory)
            original_html = _html_surface(original, surface)
            transformed_html = _html_surface(transformed, surface)
            if original and "el.textContent=" not in original_html and surface == "contenteditable":
                raise RuntimeError("contenteditable assignment missing")
            if original and "el.value=" not in original_html and surface == "textarea":
                raise RuntimeError("textarea assignment missing")
            original_png = _screenshot(executable, root, "original", original_html)
            transformed_png = _screenshot(executable, root, "transformed", transformed_html)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as error:
        payload = {
            "algorithm_version": BENCHMARK_RENDER_VERSION,
            "environment": environment,
            "status": "UNKNOWN",
            "original_sha256": original_sha,
            "transformed_sha256": transformed_sha,
            "equal": None,
            "detail": type(error).__name__,
            "font": BENCHMARK_RENDER_FONT,
            "browser_version": browser,
        }
        return {**payload, "comparison_hash": sha256_json(payload)}
    equal = original_png == transformed_png
    payload = {
        "algorithm_version": BENCHMARK_RENDER_VERSION,
        "environment": environment,
        "status": "VERIFIED" if equal else "REJECTED",
        "original_sha256": original_sha,
        "transformed_sha256": transformed_sha,
        "equal": equal,
        "detail": "png_bytes_equal" if equal else "png_bytes_differ",
        "font": BENCHMARK_RENDER_FONT,
        "browser_version": browser,
    }
    return {**payload, "comparison_hash": sha256_json(payload)}


def compare_pre_payload(original: str, transformed: str) -> dict[str, object]:
    result = compare_chrome_pre_screenshots(original, transformed)
    payload = result.payload()
    payload["comparison_hash"] = result.comparison_hash
    return payload


def xclip_available() -> bool:
    return shutil.which("xclip") is not None


def clipboard_roundtrip(text: str) -> str | None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not xclip_available():
        return None
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "UTF8_STRING"],
            input=text.encode("utf-8"),
            check=True,
            timeout=10,
        )
        output = subprocess.check_output(
            ["xclip", "-selection", "clipboard", "-t", "UTF8_STRING", "-o"],
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=True,
                timeout=10,
            )
            output = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], timeout=10)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
    return output.decode("utf-8")
