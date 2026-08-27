from io import BytesIO, StringIO, TextIOWrapper
import os
from pathlib import Path
import subprocess
import sys

import pytest

from fuckmark.cli import main
from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix


ROOT = Path(__file__).resolve().parents[1]
CARRIERS = ("\u034f", "\ufe00")


def _strip(text: str) -> str:
    for carrier in CARRIERS:
        text = text.replace(carrier, "")
    return text


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


def test_file_roundtrip_preserves_lf_crlf_cr_mixed_and_final_newline(tmp_path: Path) -> None:
    samples = {
        "lf.txt": b"first\nsecond\n",
        "crlf.txt": b"first\r\nsecond\r\n",
        "cr.txt": b"first\rsecond\r",
        "mixed.txt": b"first\r\nsecond\nthird\r",
        "no_nl.txt": b"first\r\nsecond",
    }
    for name, original in samples.items():
        source = tmp_path / name
        target = tmp_path / f"out-{name}"
        source.write_bytes(original)
        assert main(StringIO(""), StringIO(), error_stream=StringIO(), argv=(str(source), "--output", str(target))) == 0
        written = target.read_bytes()
        assert _strip(written.decode("utf-8")).encode("utf-8") == original
        visible = tmp_path / f"vis-{name}"
        assert main(StringIO(""), StringIO(), error_stream=StringIO(), argv=(str(source), "--output", str(visible), "--visible")) == 0
        assert visible.read_bytes() == original


def test_stdout_and_visible_preserve_crlf_from_file(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    original = b"first\r\nsecond\r\n"
    source.write_bytes(original)
    raw_out = BytesIO()
    output = TextIOWrapper(raw_out, encoding="utf-8", newline="")
    errors = StringIO()
    assert main(output_stream=output, error_stream=errors, argv=(str(source),)) == 0
    output.flush()
    payload = raw_out.getvalue()
    assert _strip(payload.decode("utf-8")).encode("utf-8") == original
    visible_out = BytesIO()
    visible = TextIOWrapper(visible_out, encoding="utf-8", newline="")
    assert main(output_stream=visible, error_stream=StringIO(), argv=(str(source), "--visible")) == 0
    visible.flush()
    assert visible_out.getvalue() == original


def test_explicit_text_mode_accepts_sentences_decimals_and_slashes() -> None:
    cases = (
        "I agree. You are right",
        "Version 1.2 works",
        "Use input/output here",
    )
    for source in cases:
        output = StringIO()
        errors = StringIO()
        status = main(StringIO(""), output, error_stream=errors, argv=("--text", source))
        assert status == 0, errors.getvalue()
        assert output.getvalue() == apply_letter_alternating_mix(source)
        assert errors.getvalue() == ""


def test_positional_sentences_and_decimals_are_literal_text() -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("I agree. You are right",))
    assert status == 0, errors.getvalue()
    assert output.getvalue() == apply_letter_alternating_mix("I agree. You are right")
    status = main(StringIO(""), StringIO(), error_stream=errors, argv=("Version 1.2 works",))
    assert status == 0


def test_explicit_file_mode_rejects_missing_files(tmp_path: Path) -> None:
    missing = tmp_path / "notes.txt"
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("--file", str(missing)))
    assert status == 1
    assert output.getvalue() == ""
    assert "file not found" in errors.getvalue()
    assert "quote the text" not in errors.getvalue()


def test_file_mode_reads_names_with_spaces_and_rejects_directories(tmp_path: Path) -> None:
    named = tmp_path / "my notes.txt"
    original = b"I do not agree.\n"
    named.write_bytes(original)
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("--file", str(named)))
    assert status == 0
    assert output.getvalue() == apply_letter_alternating_mix(original.decode("utf-8"))
    status = main(StringIO(""), StringIO(), error_stream=errors, argv=("--file", str(tmp_path)))
    assert status == 1
    assert "directory" in errors.getvalue()


def test_text_mode_accepts_values_starting_with_hyphen() -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("--text=-hyphen-start",))
    assert status == 0, errors.getvalue()
    assert output.getvalue() == apply_letter_alternating_mix("-hyphen-start")


def test_slash_text_without_text_flag_is_still_a_missing_path() -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("Use input/output here",))
    assert status == 1
    assert "file not found" in errors.getvalue()
    assert "--text" in errors.getvalue()


def test_real_subprocess_stdin_preserves_crlf() -> None:
    original = b"first\r\nsecond\r\n"
    result = _cli_bytes("--stdin", stdin=original)
    assert result.returncode == 0
    assert _strip(result.stdout.decode("utf-8")).encode("utf-8") == original
    visible = _cli_bytes("--stdin", "--visible", stdin=original)
    assert visible.returncode == 0
    assert visible.stdout == original
    result = _cli_bytes("--stdin", "--visible", stdin=b"hello\xffworld")
    assert result.returncode != 0
    assert result.stdout == b""
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert "UTF-8" in stderr
    assert "Traceback" not in stderr
    truncated = _cli_bytes("--stdin", stdin=b"\xc3")
    assert truncated.returncode != 0
    assert truncated.stdout == b""
    lone = _cli_bytes("--stdin", stdin=b"\xff")
    assert lone.returncode != 0
    assert lone.stdout == b""


def test_real_subprocess_accepts_ascii_and_non_ascii_utf8() -> None:
    ascii_result = _cli_bytes("--stdin", "--visible", stdin=b"I do not agree.\n")
    assert ascii_result.returncode == 0
    assert ascii_result.stdout == b"I do not agree.\n"
    valid = _cli_bytes("--stdin", stdin="I do not agree.\n".encode("utf-8"))
    assert valid.returncode == 0
    assert valid.stdout
    non_ascii = ("I do not agree " + chr(0x00E9) + ".\n").encode("utf-8")
    latin = _cli_bytes("--stdin", stdin=non_ascii)
    assert latin.returncode == 0
    assert latin.stdout == non_ascii


def test_surrogateescape_wrapper_is_rejected_as_invalid_utf8() -> None:
    source = TextIOWrapper(BytesIO(b"hello\xffworld"), encoding="utf-8", errors="surrogateescape", newline="")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors, argv=("--stdin", "--copy"))
    assert status == 1
    assert output.getvalue() == ""
    assert copied == []
    assert "UTF-8" in errors.getvalue()
    assert "Traceback" not in errors.getvalue()


def test_cli_help_documents_text_and_file_flags(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "--text" in rendered
    assert "--file" in rendered
    assert "TEXT_OR_FILE" in rendered
    assert "literal" in rendered.casefold() or "--text" in rendered
