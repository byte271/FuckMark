from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..hashing import sha256_json, sha256_text


RENDERING_HARNESS_VERSION = "product-reference-render-v1"
_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


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
            original_png = _render_pre(executable, root, "original", original)
            transformed_png = _render_pre(executable, root, "transformed", transformed)
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
    payload = json.dumps(text, ensure_ascii=False)
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;background:#fff'>"
        "<pre id='t' style=\"margin:16px;font:16px/24px 'DejaVu Sans Mono',monospace;"
        "white-space:pre-wrap;color:#000\"></pre>"
        f"<script>document.getElementById('t').textContent={payload};</script>"
        "</body></html>"
    )


def _render_pre(executable: str, root: Path, name: str, text: str) -> bytes:
    html_path = root / f"{name}.html"
    png_path = root / f"{name}.png"
    html_path.write_text(_html_page(text), encoding="utf-8")
    subprocess.run(
        [
            executable,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--window-size=800,200",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=8,
    )
    return png_path.read_bytes()
