from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.request import urlopen

from fuckmark.cli import RELEASE_CLI_ALGORITHM_VERSION, main
from fuckmark.web import mark_html_path, serve_mark_web, web_root


ROOT = Path(__file__).resolve().parents[1]


def test_packaged_mark_html_matches_docs_source() -> None:
    docs = (ROOT / "docs" / "mark.html").read_text(encoding="utf-8")
    packaged = (ROOT / "fuckmark" / "webui" / "mark.html").read_text(encoding="utf-8")
    assert packaged == docs
    assert mark_html_path().is_file()
    assert web_root() == mark_html_path().parent


def test_mark_html_miss_copy_is_english() -> None:
    html = mark_html_path().read_text(encoding="utf-8")
    assert "We did not detect a watermark in this text." in html
    assert "What? You think there is a watermark in this?" in html
    assert "Contact us" in html
    assert "Fhelp@q1z.org" in html
    assert "\u6211\u4eec" not in html
    assert "\u8054\u7cfb" not in html


def test_fuckmark_web_serves_mark_page() -> None:
    errors = StringIO()
    seen: dict[str, object] = {}

    def on_ready(url: str, port: int) -> None:
        seen["url"] = url
        seen["port"] = port
        with urlopen(url, timeout=2) as response:
            seen["body"] = response.read().decode("utf-8")
        with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            seen["index"] = response.read().decode("utf-8")

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
    assert "FuckMark web:" in errors.getvalue()
    body = str(seen["body"])
    assert "FuckMark" in body
    assert "detectFuckMark" in body
    assert "We did not detect a watermark in this text." in body
    assert "detectFuckMark" in str(seen["index"])


def test_cli_web_help_documents_browser_tool() -> None:
    assert RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v12"
    out = StringIO()
    errors = StringIO()
    with redirect_stdout(out):
        status = main(StringIO(""), StringIO(), error_stream=errors, argv=("web", "--help"))
    assert status == 0
    help_text = out.getvalue() + errors.getvalue()
    assert "fuckmark web" in help_text
    assert "browser" in help_text.casefold() or "beginner" in help_text.casefold()
