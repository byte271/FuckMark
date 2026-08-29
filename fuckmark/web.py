from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse

from . import __version__
from .product.detect import DETECT_CONTACT_EMAIL, detect_fuckmark_insertions
from .product.domain import PRODUCT_MAX_INPUT_CHARS
from .product.visible_projection import product_approved_carriers_v1, project_visible_v1


DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8765
_MAX_BODY_BYTES = 8_000_000


def mark_html_path() -> Path:
    packaged = Path(__file__).resolve().parent / "webui" / "mark.html"
    if packaged.is_file():
        return packaged
    repo = Path(__file__).resolve().parents[1] / "docs" / "mark.html"
    if repo.is_file():
        return repo
    raise FileNotFoundError("mark.html is not installed with this FuckMark build")


def web_root() -> Path:
    return mark_html_path().resolve().parent


def _detect_dict(text: str) -> dict[str, object]:
    scan = detect_fuckmark_insertions(text)
    return {
        "detected": scan.detected,
        "found": scan.found,
        "mark": scan.mark_count,
        "cc": scan.cc_count,
        "me": scan.me_count,
        "cf": scan.cf_count,
        "ia": scan.ia_count,
        "first": scan.first_hit,
        "source_length": scan.source_length,
    }


def remove_marks_payload(text: str) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text) > PRODUCT_MAX_INPUT_CHARS:
        return {
            "ok": False,
            "reason": "too-large",
            "backend": "python",
            "max": PRODUCT_MAX_INPUT_CHARS,
            "detect": {
                "detected": False,
                "found": 0,
                "mark": 0,
                "cc": 0,
                "me": 0,
                "cf": 0,
                "ia": 0,
                "first": "",
                "source_length": len(text),
            },
            "text": "",
            "removed": 0,
            "contact": DETECT_CONTACT_EMAIL,
        }
    detect = _detect_dict(text)
    if detect["detected"] is not True:
        return {
            "ok": False,
            "reason": "not-detected",
            "backend": "python",
            "detect": detect,
            "text": text,
            "removed": 0,
            "contact": DETECT_CONTACT_EMAIL,
        }
    cleaned = project_visible_v1(text, product_approved_carriers_v1())
    return {
        "ok": True,
        "reason": "stripped",
        "backend": "python",
        "detect": detect,
        "text": cleaned,
        "removed": int(detect["found"]),
        "contact": DETECT_CONTACT_EMAIL,
    }


def health_payload() -> dict[str, object]:
    from .cli import RELEASE_CLI_ALGORITHM_VERSION

    return {
        "ok": True,
        "backend": "python",
        "version": __version__,
        "cli_algorithm_version": RELEASE_CLI_ALGORITHM_VERSION,
        "contact": DETECT_CONTACT_EMAIL,
    }


def _web_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark web",
        description=(
            "Open the FuckMark browser tool locally. "
            "Serves mark.html and a Python API for detect/strip. "
            "For beginners who prefer a page over the CLI."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_WEB_HOST,
        help=f"bind address (default {DEFAULT_WEB_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_WEB_PORT,
        help=f"port (default {DEFAULT_WEB_PORT}; 0 picks a free port)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="print the URL without opening a browser",
    )
    return parser


class _MarkHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def end_headers(self) -> None:
        buffer = getattr(self, "_headers_buffer", None)
        already = False
        if buffer:
            already = any(line.lower().startswith(b"cache-control:") for line in buffer)
        if not already:
            self.send_header("Cache-Control", "no-store")
        return super().end_headers()

    def _json_response(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_object(self) -> dict[str, object]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length < 0 or length > _MAX_BODY_BYTES:
            raise ValueError("request body too large")
        data = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("body must be UTF-8 JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json_response(200, health_payload())
            return
        if path in {"/", "/index.html"}:
            self.path = "/mark.html"
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/detect":
            try:
                payload = self._read_json_object()
                text = payload.get("text", "")
                if not isinstance(text, str):
                    raise ValueError("text must be a string")
                if len(text) > PRODUCT_MAX_INPUT_CHARS:
                    self._json_response(
                        413,
                        {
                            "ok": False,
                            "reason": "too-large",
                            "backend": "python",
                            "max": PRODUCT_MAX_INPUT_CHARS,
                        },
                    )
                    return
                detect = _detect_dict(text)
                self._json_response(
                    200,
                    {
                        "ok": True,
                        "backend": "python",
                        "detect": detect,
                        "contact": DETECT_CONTACT_EMAIL,
                    },
                )
            except ValueError as error:
                self._json_response(400, {"ok": False, "reason": "bad-request", "error": str(error)})
            return
        if path == "/api/remove-marks":
            try:
                payload = self._read_json_object()
                text = payload.get("text", "")
                if not isinstance(text, str):
                    raise ValueError("text must be a string")
                result = remove_marks_payload(text)
                status = 200 if result.get("reason") != "too-large" else 413
                self._json_response(status, result)
            except ValueError as error:
                self._json_response(400, {"ok": False, "reason": "bad-request", "error": str(error)})
            return
        self.send_error(404, "Not Found")


def serve_mark_web(
    *,
    host: str = DEFAULT_WEB_HOST,
    port: int = DEFAULT_WEB_PORT,
    open_browser: bool = True,
    errors: TextIO | None = None,
    serve_seconds: float | None = None,
    on_ready: Callable[[str, int], None] | None = None,
) -> tuple[str, int]:
    root = web_root()
    page = mark_html_path()
    if page.name != "mark.html" or not page.is_file():
        raise FileNotFoundError("mark.html is missing")
    handler = functools.partial(_MarkHandler, directory=str(root))

    class _Server(socketserver.TCPServer):
        allow_reuse_address = True

    server = _Server((host, port), handler)
    bound_host, bound_port = server.server_address[:2]
    bound_port = int(bound_port)
    url = f"http://{bound_host}:{bound_port}/mark.html"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if errors is not None:
            errors.write(f"FuckMark web: {url}\n")
            errors.write("FuckMark web: Python API at /api/health and /api/remove-marks\n")
            errors.write("FuckMark web: press Ctrl+C to stop.\n")
            errors.flush()
        if on_ready is not None:
            on_ready(url, bound_port)
        if open_browser:
            webbrowser.open(url)
        if serve_seconds is None:
            stop = threading.Event()
            while not stop.wait(0.5):
                if not thread.is_alive():
                    break
        else:
            time.sleep(max(0.0, serve_seconds))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
    return url, bound_port


def run_web_argv(argv: list[str], errors: TextIO) -> int:
    try:
        arguments = _web_parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 1
    if arguments.port < 0 or arguments.port > 65535:
        errors.write("FuckMark: --port must be between 0 and 65535\n")
        errors.flush()
        return 1
    try:
        mark_html_path()
    except FileNotFoundError as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return 1
    try:
        serve_mark_web(
            host=arguments.host,
            port=arguments.port,
            open_browser=not arguments.no_open,
            errors=errors,
            serve_seconds=None,
        )
    except KeyboardInterrupt:
        errors.write("\n")
        errors.flush()
        return 130
    except OSError as error:
        errors.write(f"FuckMark: could not start web server: {error}\n")
        errors.flush()
        return 1
    return 0
