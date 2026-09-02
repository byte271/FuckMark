import json
from io import StringIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fuckmark.cli import main, process_text
from fuckmark.product.scan import (
    CATEGORY_BIDI_CONTROL,
    CATEGORY_CONTROL,
    CATEGORY_ENCLOSING_MARK,
    CATEGORY_PRIVATE_USE,
    CATEGORY_TAG,
    CATEGORY_VARIATION_SELECTOR,
    CATEGORY_ZERO_WIDTH,
    SCAN_CATEGORIES,
    autofix_trojan_source,
    classify_hidden_codepoint,
    clean_hidden_characters,
    scan_dict,
    scan_hidden_characters,
    scan_human_report,
    scan_machine_line,
)
from fuckmark.product.severity import language_from_path, source_roles
from fuckmark.web import scan_payload, serve_mark_web


TROJAN_SOURCE = "if (accessLevel != \u202eadmin\u202c) {"


def _post_json(url: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_classifier_covers_known_hidden_ranges() -> None:
    assert classify_hidden_codepoint(ord("A")) is None
    assert classify_hidden_codepoint(ord(" ")) is None
    assert classify_hidden_codepoint(ord("\n")) is None
    assert classify_hidden_codepoint(ord("\t")) is None
    assert classify_hidden_codepoint(0x00E9) is None
    assert classify_hidden_codepoint(0x0301) is None
    assert classify_hidden_codepoint(0x202E) == CATEGORY_BIDI_CONTROL
    assert classify_hidden_codepoint(0x2066) == CATEGORY_BIDI_CONTROL
    assert classify_hidden_codepoint(0x200B) == CATEGORY_ZERO_WIDTH
    assert classify_hidden_codepoint(0x200D) == CATEGORY_ZERO_WIDTH
    assert classify_hidden_codepoint(0xFEFF) == CATEGORY_ZERO_WIDTH
    assert classify_hidden_codepoint(0x034F) == CATEGORY_ZERO_WIDTH
    assert classify_hidden_codepoint(0xFE0F) == CATEGORY_VARIATION_SELECTOR
    assert classify_hidden_codepoint(0xE0101) == CATEGORY_VARIATION_SELECTOR
    assert classify_hidden_codepoint(0xE0041) == CATEGORY_TAG
    assert classify_hidden_codepoint(0x20DD) == CATEGORY_ENCLOSING_MARK
    assert classify_hidden_codepoint(0x0007) == CATEGORY_CONTROL
    assert classify_hidden_codepoint(0xE000) == CATEGORY_PRIVATE_USE


def test_scan_detects_trojan_source_bidi() -> None:
    result = scan_hidden_characters(TROJAN_SOURCE)
    assert result.detected is True
    assert result.total == 2
    assert result.counts[CATEGORY_BIDI_CONTROL] == 2
    assert result.active_categories() == (CATEGORY_BIDI_CONTROL,)
    assert result.first_hit.startswith("U+202E@")
    report = scan_human_report(result)
    assert "hidden characters found" in report
    assert "RIGHT-TO-LEFT OVERRIDE" in report
    assert "critical/identifier" in report
    assert "fuckmark-scan found=yes" in scan_machine_line(result)
    assert "severity=critical" in scan_machine_line(result)


def test_scan_detects_tag_smuggling() -> None:
    smuggled = "Approve this request." + "".join(chr(c) for c in range(0xE0061, 0xE0066))
    result = scan_hidden_characters(smuggled)
    assert result.counts[CATEGORY_TAG] == 5
    assert result.total == 5


def test_scan_reports_clean_text() -> None:
    result = scan_hidden_characters("Ordinary text, nothing hidden.")
    assert result.detected is False
    assert result.total == 0
    assert result.active_categories() == ()
    assert "no hidden characters" in scan_human_report(result)
    assert "found=no" in scan_machine_line(result)


def test_scan_dict_is_json_serializable() -> None:
    payload = scan_dict(scan_hidden_characters(TROJAN_SOURCE))
    encoded = json.dumps(payload)
    assert '"bidi_control"' in encoded
    assert payload["found"] is True
    assert payload["counts"][CATEGORY_BIDI_CONTROL] == 2
    assert payload["highest_severity"] == "critical"
    assert payload["findings"][0]["severity"] == "critical"
    assert payload["findings"][0]["context"] == "identifier"
    assert "Trojan Source" in payload["findings"][0]["why"]


def test_scan_findings_are_capped() -> None:
    result = scan_hidden_characters("\u200b" * 10, max_findings=3)
    assert result.total == 10
    assert len(result.findings) == 3
    assert result.truncated is True


def test_clean_strips_all_hidden_categories() -> None:
    cleaned, removed = clean_hidden_characters(TROJAN_SOURCE)
    assert removed == 2
    assert "\u202e" not in cleaned
    assert cleaned == "if (accessLevel != admin) {"


def test_clean_reverses_a_fuckmark_mix() -> None:
    source = "The quick brown fox."
    mixed = process_text(source)
    assert mixed != source
    cleaned, removed = clean_hidden_characters(mixed)
    assert cleaned == source
    assert removed > 0


def test_clean_can_target_a_subset_of_categories() -> None:
    text = "a\u202eb\u200bc"
    cleaned, removed = clean_hidden_characters(text, categories={CATEGORY_BIDI_CONTROL})
    assert removed == 1
    assert cleaned == "a" + "b\u200bc"


def test_clean_is_a_noop_for_plain_ascii() -> None:
    cleaned, removed = clean_hidden_characters("plain ascii text")
    assert removed == 0
    assert cleaned == "plain ascii text"


def test_cli_scan_reports_hidden_and_clean_text() -> None:
    out, err = StringIO(), StringIO()
    status = main(StringIO(""), out, error_stream=err, argv=("--scan", "--text", TROJAN_SOURCE))
    assert status == 0
    assert "hidden characters found" in out.getvalue()
    assert "RIGHT-TO-LEFT OVERRIDE" in out.getvalue()

    quiet_out, quiet_err = StringIO(), StringIO()
    quiet_status = main(
        StringIO(""), quiet_out, error_stream=quiet_err, argv=("--scan", "-q", "--text", TROJAN_SOURCE)
    )
    assert quiet_status == 0
    assert quiet_out.getvalue().startswith("fuckmark-scan found=yes")

    clean_out, clean_err = StringIO(), StringIO()
    clean_status = main(
        StringIO(""), clean_out, error_stream=clean_err, argv=("--scan", "--text", "nothing hidden here")
    )
    assert clean_status == 0
    assert "no hidden characters" in clean_out.getvalue()


def test_cli_clean_removes_hidden_and_keeps_visible() -> None:
    out, err = StringIO(), StringIO()
    status = main(StringIO(""), out, error_stream=err, argv=("--clean", "--text", TROJAN_SOURCE))
    assert status == 0
    assert out.getvalue() == "if (accessLevel != admin) {"
    assert "removed 2 hidden characters" in err.getvalue()

    noop_out, noop_err = StringIO(), StringIO()
    noop_status = main(StringIO(""), noop_out, error_stream=noop_err, argv=("--clean", "--text", "clean text"))
    assert noop_status == 0
    assert noop_out.getvalue() == "clean text"
    assert "no hidden characters found" in noop_err.getvalue()


def test_cli_rejects_conflicting_modes_and_visible() -> None:
    conflict = main(StringIO(""), StringIO(), error_stream=StringIO(), argv=("--scan", "--clean", "--text", "x"))
    assert conflict == 1
    scan_visible = main(StringIO(""), StringIO(), error_stream=StringIO(), argv=("--scan", "--visible", "--text", "x"))
    assert scan_visible == 1
    clean_visible = main(
        StringIO(""), StringIO(), error_stream=StringIO(), argv=("--clean", "--visible", "--text", "x")
    )
    assert clean_visible == 1


def test_cli_scan_status_line_on_stderr() -> None:
    out, err = StringIO(), StringIO()
    status = main(StringIO(""), out, error_stream=err, argv=("--scan", "--status", "--text", TROJAN_SOURCE))
    assert status == 0
    assert "fuckmark-scan found=yes" in err.getvalue()


def test_scan_categories_all_have_descriptions() -> None:
    from fuckmark.product.scan import CATEGORY_DESCRIPTIONS

    assert set(SCAN_CATEGORIES) == set(CATEGORY_DESCRIPTIONS)


def test_web_scan_payload_and_endpoint() -> None:
    mixed = process_text("Hello from the scanner.")
    payload = scan_payload(mixed)
    assert payload["ok"] is True
    assert payload["reason"] == "found"
    assert payload["backend"] == "python"
    assert payload["cleaned"] == "Hello from the scanner."
    assert int(payload["removed"]) > 0
    assert payload["scan"]["found"] is True
    assert payload["language"] == "auto"

    seen: dict[str, object] = {}

    def on_ready(url: str, port: int) -> None:
        status, data = _post_json(f"http://127.0.0.1:{port}/api/scan", {"text": mixed})
        seen["status"] = status
        seen["data"] = data
        clean_status, clean_data = _post_json(
            f"http://127.0.0.1:{port}/api/scan", {"text": "no hidden characters"}
        )
        seen["clean_status"] = clean_status
        seen["clean_data"] = clean_data

    serve_mark_web(host="127.0.0.1", port=0, open_browser=False, serve_seconds=0.05, on_ready=on_ready)
    assert seen["status"] == 200
    data = seen["data"]
    assert isinstance(data, dict)
    assert data["scan"]["found"] is True
    assert data["cleaned"] == "Hello from the scanner."
    clean_data = seen["clean_data"]
    assert isinstance(clean_data, dict)
    assert clean_data["reason"] == "clean"
    assert clean_data["scan"]["found"] is False

    def on_ready_language(url: str, port: int) -> None:
        py_status, py_data = _post_json(
            f"http://127.0.0.1:{port}/api/scan",
            {"text": "# \u202e", "language": "python"},
        )
        seen["py_status"] = py_status
        seen["py_data"] = py_data
        auto_status, auto_data = _post_json(
            f"http://127.0.0.1:{port}/api/scan",
            {"text": "# \u202e"},
        )
        seen["auto_status"] = auto_status
        seen["auto_data"] = auto_data

    serve_mark_web(host="127.0.0.1", port=0, open_browser=False, serve_seconds=0.05, on_ready=on_ready_language)
    assert seen["py_status"] == 200
    py_data = seen["py_data"]
    assert isinstance(py_data, dict)
    assert py_data["language"] == "python"
    assert py_data["scan"]["findings"][0]["context"] == "comment"
    assert py_data["scan"]["findings"][0]["severity"] == "critical"
    auto_data = seen["auto_data"]
    assert isinstance(auto_data, dict)
    assert auto_data["language"] == "auto"
    assert auto_data["scan"]["findings"][0]["context"] == "prose"


def test_severity_is_context_aware() -> None:
    ident = scan_hidden_characters("a\u202eb")
    assert ident.findings[0].context == "identifier"
    assert ident.findings[0].severity == "critical"
    assert ident.highest_severity == "critical"

    emoji = scan_hidden_characters("\U0001F468\u200d\U0001F469")
    assert emoji.findings[0].category == CATEGORY_ZERO_WIDTH
    assert emoji.findings[0].context == "emoji"
    assert emoji.findings[0].severity == "info"

    tags = scan_hidden_characters("".join(chr(c) for c in range(0xE0061, 0xE0063)))
    assert tags.counts[CATEGORY_TAG] == 2
    assert tags.highest_severity == "critical"
    assert all(item.severity == "critical" for item in tags.findings)

    quoted = scan_hidden_characters('"\u202e"')
    assert quoted.findings[0].context == "string"
    assert quoted.findings[0].severity == "critical"

    comment = scan_hidden_characters("// \u202e")
    assert comment.findings[0].context == "comment"
    assert comment.findings[0].severity == "critical"


def test_language_from_path_maps_suffixes() -> None:
    assert language_from_path("app.js") == "javascript"
    assert language_from_path("mod.py") == "python"
    assert language_from_path("q.sql") == "sql"
    assert language_from_path("page.html") == "html"
    assert language_from_path("notes.txt") == "auto"


def test_hash_comment_is_language_aware() -> None:
    python = scan_hidden_characters("# \u202e", language="python")
    assert python.findings[0].context == "comment"
    assert python.findings[0].severity == "critical"
    auto = scan_hidden_characters("# \u202e")
    assert auto.findings[0].context == "prose"
    assert auto.findings[0].severity == "high"


def test_url_double_slash_is_not_a_comment() -> None:
    roles = source_roles("http://x")
    assert all(role == "code" for role in roles)
    result = scan_hidden_characters("http://\u202e")
    assert result.findings[0].context == "prose"
    assert result.findings[0].severity == "high"


def test_autofix_trojan_source_strips_only_bidi() -> None:
    text = "a\u202e\u200bb"
    cleaned, removed = autofix_trojan_source(text)
    assert removed == 1
    assert cleaned == "a\u200bb"
    assert "\u202e" not in cleaned
