from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from fuckmark.cli import (
    EXIT_CLIPBOARD,
    EXIT_ERROR,
    EXIT_INTERNAL,
    EXIT_OK,
    REASON_INTERNAL_ERROR,
    REASON_NO_ELIGIBLE_SITES,
    REASON_SITE_CAP,
    REASON_TOO_LARGE,
    REASON_TRANSFORMED,
    main,
    transform_text,
)
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix, hard_machine_intervals
from fuckmark.product.domain import PRODUCT_MAX_INPUT_CHARS
from fuckmark.product.visible_projection import project_visible_v1
from fuckmark.transforms.protected_markdown import resolve_markdown_reference_hrefs


CARRIERS = ("\u034f", "\ufe00")
ROOT = Path(__file__).resolve().parents[1]


def _strip(text: str) -> str:
    from fuckmark.product.visible_projection import project_visible_v1
    return project_visible_v1(text)


def _commonmark_hrefs(text: str) -> tuple[str, ...]:
    markdown_it = pytest.importorskip("markdown_it")
    tokens = markdown_it.MarkdownIt("commonmark").parse(text)
    hrefs: list[str] = []
    for token in tokens:
        children = token.children or ()
        for child in children:
            if child.type == "link_open":
                hrefs.append(child.attrGet("href") or "")
    return tuple(hrefs)


def _commonmark_html(text: str) -> str:
    markdown_it = pytest.importorskip("markdown_it")
    return markdown_it.MarkdownIt("commonmark").render(text)


def _cli_bytes(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "fuckmark.cli", *args],
        input=stdin,
        cwd=ROOT,
        env=env,
        capture_output=True,
    )


@pytest.mark.parametrize(
    "source",
    (
        "[foo\nbar][]\n\n[foo bar]: https://example.com\n",
        "[ref]\n\n[ref]:\n  https://example.com\n",
        "> [ref]\n>\n> [ref]: https://example.com\n",
        "- [ref]\n\n- [ref]: https://example.com\n",
        "[ref]\r\r[ref]: https://example.com\r",
        "[click][ref]\n\n[ref]: https://example.com\n",
    ),
)
def test_markdown_reference_hrefs_match_commonmark_before_and_after(source: str) -> None:
    before = _commonmark_hrefs(source)
    assert before
    applied = apply_letter_alternating_mix(source)
    assert _strip(applied) == source
    assert _commonmark_hrefs(applied) == before
    assert resolve_markdown_reference_hrefs(source) == resolve_markdown_reference_hrefs(applied)


def test_multiline_inline_destination_keeps_href() -> None:
    source = "[hello](\nrelative-file\n)\n"
    before = _commonmark_hrefs(source)
    assert before == ("relative-file",)
    applied = apply_letter_alternating_mix(source)
    assert _commonmark_hrefs(applied) == before
    assert "relative-file" in applied
    assert _strip(applied) == source


def test_html_entity_and_indented_code_are_stable() -> None:
    html = "<b>Hello</b>\n"
    applied_html = apply_letter_alternating_mix(html)
    assert "<b>" in applied_html and "</b>" in applied_html
    assert _strip(_commonmark_html(applied_html)) == _strip(_commonmark_html(html))
    entity = "Fish &amp; chips.\n"
    applied_entity = apply_letter_alternating_mix(entity)
    assert "&amp;" in applied_entity
    assert _strip(_commonmark_html(applied_entity)) == _strip(_commonmark_html(entity))
    indented = "    print(\"hello\")\n"
    applied_code = apply_letter_alternating_mix(indented)
    assert 'print("hello")' in applied_code
    assert _strip(applied_code) == indented


def test_paths_and_ftp_uri_are_protected_without_and_or() -> None:
    cases = (
        ("See scripts/build now.", "scripts/build"),
        ("Open C:/Users/Alice/My final notes.txt now.", "C:/Users/Alice/My final notes.txt"),
        ("Open C:/My final notes.txt now.", "C:/My final notes.txt"),
        ("Read /tmp/My final notes.txt now.", "/tmp/My final notes.txt"),
        ("Read /My final notes.txt now.", "/My final notes.txt"),
        ("Read ~/My final notes.txt now.", "~/My final notes.txt"),
        ("Get ftp://example.com/file now.", "ftp://example.com/file"),
    )
    for source, token in cases:
        applied = apply_letter_alternating_mix(source)
        assert token in applied
        assert _strip(applied) == source
        covered = "".join(source[start:end] for start, end in hard_machine_intervals(source))
        assert token in covered
    prose = "Use and/or input/output here."
    covered = "".join(prose[start:end] for start, end in hard_machine_intervals(prose))
    assert "and/or" not in covered
    assert "input/output" not in covered
    assert apply_letter_alternating_mix(prose) != prose
    math = "B2 = (B1 / B2) 2.2, B4.B2"
    math_covered = "".join(math[start:end] for start, end in hard_machine_intervals(math))
    assert "/ B2)" not in math_covered
    assert "B4.B2" not in math_covered
    messages = "Use a series of test/error messages."
    message_covered = "".join(messages[start:end] for start, end in hard_machine_intervals(messages))
    assert "test/error" not in message_covered
    assert apply_letter_alternating_mix(messages) != messages


def test_transform_reasons_are_distinct() -> None:
    changed = transform_text("I do not agree.")
    assert changed.reason == REASON_TRANSFORMED
    assert changed.change_count > 0
    latin_only = transform_text(chr(0x00E9) * 3)
    assert latin_only.reason == REASON_TRANSFORMED
    assert latin_only.change_count > 0
    mixed = transform_text(changed.output_text)
    assert mixed.reason == "already-transformed"
    none = transform_text("123.")
    assert none.reason == REASON_NO_ELIGIBLE_SITES
    accented = transform_text("I do not agree " + chr(0x00E9) + ".")
    assert accented.reason == REASON_TRANSFORMED
    assert accented.change_count > 0
    long = "abcdefghijklmnopqrstuvwxyz" * 158
    capped = transform_text(long)
    assert capped.reason == REASON_SITE_CAP
    assert capped.capped is True
    huge = transform_text("a" * (PRODUCT_MAX_INPUT_CHARS + 1))
    assert huge.reason == REASON_TOO_LARGE


def test_internal_transform_failure_is_not_silent_success(monkeypatch) -> None:
    def boom(text: str, sites):
        raise RuntimeError("invariant")

    monkeypatch.setattr("fuckmark.cli.compose_letter_mix", boom)
    result = transform_text("I do not agree.")
    assert result.reason == REASON_INTERNAL_ERROR
    assert result.output_text == "I do not agree."
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("--text", "I do not agree."))
    assert status == EXIT_INTERNAL
    assert output.getvalue() == ""
    assert "internally" in errors.getvalue()


def test_clipboard_runs_after_successful_file_write(tmp_path: Path) -> None:
    copied: list[str] = []
    missing = tmp_path / "no-such-dir" / "out.txt"
    status = main(
        StringIO(""),
        StringIO(),
        copied.append,
        error_stream=StringIO(),
        argv=("--text", "hello", "--copy", "-o", str(missing)),
    )
    assert status == EXIT_ERROR
    assert copied == []
    target = tmp_path / "out.txt"
    status = main(
        StringIO(""),
        StringIO(),
        copied.append,
        error_stream=StringIO(),
        argv=("--text", "hello", "--copy", "-o", str(target)),
    )
    assert status == EXIT_OK
    assert copied == [apply_letter_alternating_mix("hello")]


def test_usage_error_keeps_exit_two_and_clipboard_uses_three() -> None:
    usage = _cli_bytes("--not-a-real-flag")
    assert usage.returncode == 2
    assert usage.stdout == b""
    output = StringIO()
    errors = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(StringIO("I do not agree.\n"), output, fail, error_stream=errors, argv=("--stdin", "--copy"))
    assert status == EXIT_CLIPBOARD
    assert apply_letter_alternating_mix("I do not agree.\n") in output.getvalue()


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="no /dev/full")
def test_stdout_full_device_has_no_traceback() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONUTF8"] = "1"
    with Path("/dev/full").open("wb") as handle:
        result = subprocess.run(
            [sys.executable, "-m", "fuckmark.cli", "--text", "hello"],
            cwd=ROOT,
            env=env,
            stdout=handle,
            stderr=subprocess.PIPE,
        )
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == EXIT_ERROR
    assert "Traceback" not in stderr
    assert "standard output" in stderr or "No space" in stderr or "cannot write" in stderr


def test_status_flag_reports_mixed_unicode_processing() -> None:
    source = "I don" + chr(0x2019) + "t agree."
    result = _cli_bytes("--text", source, "--status")
    assert result.returncode == EXIT_OK
    assert result.stdout != source.encode("utf-8")
    stderr = result.stderr.decode("utf-8")
    assert "fuckmark-status" in stderr
    assert "transformed" in stderr
    assert "processed=yes" in stderr
    assert "source_length=14" in stderr
    assert "first_unsupported=U+2019@5" in stderr
    assert "U+2019" in stderr


def test_status_flag_reports_too_large_and_inspect_map() -> None:
    huge = ("a" * (PRODUCT_MAX_INPUT_CHARS + 1)).encode("utf-8")
    too_large = _cli_bytes("--stdin", "--status", stdin=huge)
    assert too_large.returncode == EXIT_ERROR
    stderr = too_large.stderr.decode("utf-8")
    assert "fuckmark-status" in stderr
    assert "too-large" in stderr
    assert "processed=no" in stderr
    source = "I do not agree."
    inspected = _cli_bytes("--text", source, "--inspect")
    assert inspected.returncode == EXIT_OK
    assert inspected.stdout == apply_letter_alternating_mix(source).encode("utf-8")
    inspect_err = inspected.stderr.decode("utf-8")
    assert "fuckmark-inspect" in inspect_err
    assert "[U+034F]" in inspect_err
    assert "Me/Cc/Cf residuals" in inspect_err


def test_internal_failure_emits_status_when_requested(monkeypatch) -> None:
    def boom(text: str, sites):
        raise RuntimeError("invariant")

    monkeypatch.setattr("fuckmark.cli.compose_letter_mix", boom)
    output = StringIO()
    errors = StringIO()
    status = main(
        StringIO(""),
        output,
        error_stream=errors,
        argv=("--text", "I do not agree.", "--status"),
    )
    assert status == EXIT_INTERNAL
    assert output.getvalue() == ""
    assert "fuckmark-status" in errors.getvalue()
    assert "internal-error" in errors.getvalue()


def test_bracket_heavy_scan_stays_bounded() -> None:
    payload = "[abc]" * 32000
    start = time.perf_counter()
    apply_letter_alternating_mix(payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 8.0
    assert project_visible_v1(apply_letter_alternating_mix(payload)) == payload
