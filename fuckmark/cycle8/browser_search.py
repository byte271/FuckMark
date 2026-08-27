from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from ..hashing import sha256_json, sha256_text
from ..product.rendering import chrome_executable


BROWSER_SEARCH_VERSION = "cycle8-chromium-find-v1"


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
            "--window-size=400,120",
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
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise OSError("chrome screenshot missing")
    return png_path.read_bytes()


def _label_page(label: str) -> str:
    return (
        "<!doctype html><html><body style='margin:0;background:#fff'>"
        f"<pre style=\"margin:16px;font:32px/40px monospace;color:#000\">{label}</pre>"
        "</body></html>"
    )


def _find_page(text: str, needle: str) -> str:
    payload = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    codes = ",".join(str(ord(character)) for character in needle)
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;background:#fff'>"
        "<pre id='src' style=\"margin:16px;font:16px/24px monospace;color:#000;white-space:pre-wrap\"></pre>"
        "<pre id='out' style=\"margin:16px;font:32px/40px monospace;color:#000\">WAIT</pre>"
        "<script>"
        f"const text={payload};"
        f"const needle=String.fromCharCode({codes});"
        "document.getElementById('src').textContent=text;"
        "let hit=false;"
        "if(window.find){hit=!!window.find(needle,false,false,true,false,false,false);}"
        "document.getElementById('src').replaceChildren();"
        "document.getElementById('out').textContent=window.find?(hit?'HIT':'MISS'):'NONE';"
        "</script></body></html>"
    )


def compare_chrome_find(text: str, needle: str) -> dict[str, object]:
    if not isinstance(text, str) or not isinstance(needle, str):
        raise TypeError("text and needle must be strings")
    executable = chrome_executable()
    unknown = {
        "algorithm_version": BROWSER_SEARCH_VERSION,
        "environment": "chromium_window_find",
        "status": "UNKNOWN",
        "hit": None,
        "needle_sha256": sha256_text(needle),
        "text_sha256": sha256_text(text),
        "detail": "no chromium executable on this host",
    }
    if executable is None:
        return {**unknown, "comparison_hash": sha256_json(unknown)}
    try:
        with tempfile.TemporaryDirectory(prefix="fuckmark-find-") as directory:
            root = Path(directory)
            hit_png = _screenshot(executable, root, "hit", _label_page("HIT"))
            miss_png = _screenshot(executable, root, "miss", _label_page("MISS"))
            none_png = _screenshot(executable, root, "none", _label_page("NONE"))
            result_png = _screenshot(executable, root, "find", _find_page(text, needle))
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        payload = {
            "algorithm_version": BROWSER_SEARCH_VERSION,
            "environment": "chromium_window_find",
            "status": "UNKNOWN",
            "hit": None,
            "needle_sha256": sha256_text(needle),
            "text_sha256": sha256_text(text),
            "detail": type(error).__name__,
        }
        return {**payload, "comparison_hash": sha256_json(payload)}
    if result_png == hit_png:
        hit = True
        status = "VERIFIED"
        detail = "window_find_hit"
    elif result_png == miss_png:
        hit = False
        status = "VERIFIED"
        detail = "window_find_miss"
    elif result_png == none_png:
        hit = None
        status = "UNKNOWN"
        detail = "window_find_missing"
    else:
        hit = None
        status = "UNKNOWN"
        detail = "window_find_unmatched_png"
    payload = {
        "algorithm_version": BROWSER_SEARCH_VERSION,
        "environment": "chromium_window_find",
        "status": status,
        "hit": hit,
        "needle_sha256": sha256_text(needle),
        "text_sha256": sha256_text(text),
        "detail": detail,
    }
    return {**payload, "comparison_hash": sha256_json(payload)}
