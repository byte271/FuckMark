from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TextIO


DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8765


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


def _web_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark web",
        description=(
            "Open the FuckMark browser tool locally. "
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

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.path = "/mark.html"
        return super().do_GET()


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
