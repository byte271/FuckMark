from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ..hashing import sha256_json, sha256_text


RENDERING_HARNESS_VERSION = "product-reference-render-v2"
_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
_RENDER_MAX_HEIGHT = 8000
_RENDER_WIDTH = 800


def render_window_size(text: str, *, min_height: int) -> tuple[int, int, bool, int]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    columns = max(1, (_RENDER_WIDTH - 40) // 10)
    wrapped = 0
    lines = text.splitlines() or [""]
    if text.endswith(("\n", "\r")):
        lines = [*lines, ""]
    for line in lines:
        wrapped += max(1, (len(line) + columns - 1) // columns)
    content_height = 16 + wrapped * 24 + 32
    complete = content_height <= _RENDER_MAX_HEIGHT
    height = min(max(content_height, min_height), _RENDER_MAX_HEIGHT)
    return _RENDER_WIDTH, height, complete, content_height


@dataclass(frozen=True, slots=True)
class ReferenceRenderComparison:
    environment: str
    status: str
    original_sha256: str
    transformed_sha256: str
    equal: bool | None
    detail: str
    comparison_hash: str

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": RENDERING_HARNESS_VERSION,
            "environment": self.environment,
            "status": self.status,
            "original_sha256": self.original_sha256,
            "transformed_sha256": self.transformed_sha256,
            "equal": self.equal,
            "detail": self.detail,
        }


def chrome_executable() -> str | None:
    for name in _CHROME_NAMES:
        path = shutil.which(name)
        if path:
            return path
    return None


def compare_chrome_pre_screenshots(original: str, transformed: str) -> ReferenceRenderComparison:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    executable = chrome_executable()
    unknown = {
        "algorithm_version": RENDERING_HARNESS_VERSION,
        "environment": "chromium_headless",
        "status": "UNKNOWN",
        "original_sha256": sha256_text(original),
        "transformed_sha256": sha256_text(transformed),
        "equal": None,
        "detail": "no chromium executable on this host",
    }
    if executable is None:
        return ReferenceRenderComparison(
            "chromium_headless",
            "UNKNOWN",
            sha256_text(original),
            sha256_text(transformed),
            None,
            "no chromium executable on this host",
            sha256_json(unknown),
        )
    try:
        with tempfile.TemporaryDirectory(prefix="fuckmark-render-") as directory:
            root = Path(directory)
            width, height, complete, content_height = render_window_size(original if len(original) >= len(transformed) else transformed, min_height=200)
            if not complete:
                payload = {
                    "algorithm_version": RENDERING_HARNESS_VERSION,
                    "environment": "chromium_headless",
                    "status": "INCOMPLETE",
                    "original_sha256": sha256_text(original),
                    "transformed_sha256": sha256_text(transformed),
                    "equal": None,
                    "detail": "content exceeds captured window",
                    "window_width": width,
                    "window_height": height,
                    "content_height": content_height,
                }
                return ReferenceRenderComparison(
                    "chromium_headless",
                    "INCOMPLETE",
                    sha256_text(original),
                    sha256_text(transformed),
                    None,
                    "content exceeds captured window",
                    sha256_json(payload),
                )
            original_png = _render_pre(executable, root, "original", original, width=width, height=height)
            transformed_png = _render_pre(executable, root, "transformed", transformed, width=width, height=height)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        payload = {
            "algorithm_version": RENDERING_HARNESS_VERSION,
            "environment": "chromium_headless",
            "status": "UNKNOWN",
            "original_sha256": sha256_text(original),
            "transformed_sha256": sha256_text(transformed),
            "equal": None,
            "detail": type(error).__name__,
        }
        return ReferenceRenderComparison(
            "chromium_headless",
            "UNKNOWN",
            sha256_text(original),
            sha256_text(transformed),
            None,
            type(error).__name__,
            sha256_json(payload),
        )
    equal = original_png == transformed_png
    status = "VERIFIED" if equal else "REJECTED"
    detail = "png_bytes_equal" if equal else "png_bytes_differ"
    payload = {
        "algorithm_version": RENDERING_HARNESS_VERSION,
        "environment": "chromium_headless",
        "status": status,
        "original_sha256": sha256_text(original),
        "transformed_sha256": sha256_text(transformed),
        "equal": equal,
        "detail": detail,
    }
    return ReferenceRenderComparison(
        "chromium_headless",
        status,
        sha256_text(original),
        sha256_text(transformed),
        equal,
        detail,
        sha256_json(payload),
    )


def _html_page(text: str) -> str:
    payload = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;background:#fff'>"
        "<pre id='t' style=\"margin:16px;font:16px/24px 'DejaVu Sans Mono',monospace;"
        "white-space:pre-wrap;color:#000\"></pre>"
        f"<script>document.getElementById('t').textContent={payload};</script>"
        "</body></html>"
    )


def _render_pre(executable: str, root: Path, name: str, text: str, *, width: int = 800, height: int = 200) -> bytes:
    html_path = root / f"{name}.html"
    png_path = root / f"{name}.png"
    html_path.write_text(_html_page(text), encoding="utf-8")
    profile = root / f"{name}-chrome-profile"
    profile.mkdir(parents=True, exist_ok=True)
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
            f"--user-data-dir={profile}",
            "--virtual-time-budget=5000",
            f"--window-size={width},{height}",
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
        else:
            raise subprocess.TimeoutExpired(process.args, 30)
        if not png_path.exists() or png_path.stat().st_size == 0:
            raise OSError("chrome screenshot missing")
        return png_path.read_bytes()
    finally:
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
