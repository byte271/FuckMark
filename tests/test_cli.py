from io import StringIO
from pathlib import Path
import tomllib

import pytest

from fuckmark.cli import main, process_text, read_pasted_text


def test_cli_process_text_uses_release_contractions_deterministically() -> None:
    source = "I do not agree and I cannot stay."
    expected = "I don't agree and I can't stay."
    assert process_text(source) == expected
    assert process_text(source) == expected


def test_cli_process_text_respects_protected_quoted_content() -> None:
    source = 'Keep "do not change this" but I do not agree.'
    expected = "Keep \"do not change this\" but I don't agree."
    assert process_text(source) == expected


def test_cli_process_text_preserves_text_when_no_candidate_is_eligible() -> None:
    source = "Already concise."
    assert process_text(source) == source


def test_cli_reads_multiline_paste_until_ok_line() -> None:
    source = StringIO("First line\nSecond line\nok\nIgnored line\n")
    output = StringIO()
    assert read_pasted_text(source, output) == "First line\nSecond line"
    assert "Type ok on its own line" in output.getvalue()


def test_cli_main_processes_and_copies_result() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == ["I don't agree."]
    rendered = output.getvalue()
    assert "Processing..." in rendered
    assert "Success. Copied to clipboard." in rendered


def test_cli_main_copies_original_when_no_change_is_eligible() -> None:
    source = StringIO("Already concise.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == ["Already concise."]
    assert "No eligible changes" in output.getvalue()


def test_cli_main_prints_result_if_clipboard_copy_fails() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(source, output, fail)
    assert status == 2
    rendered = output.getvalue()
    assert "clipboard copy failed" in rendered
    assert "I don't agree." in rendered


def test_cli_version_reports_project_and_algorithm_identity(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--version",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "FuckMark 0.1.0" in rendered
    assert "release-cli-v2" in rendered
    assert "transform-registry-v6" in rendered


@pytest.mark.parametrize("option", (("--stdin",), ("--non-interactive",)))
def test_cli_noninteractive_mode_writes_only_transformed_text(option) -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, argv=option)
    assert status == 0
    assert output.getvalue() == "I don't agree.\n"
    assert copied == []


def test_cli_noninteractive_mode_rejects_empty_input() -> None:
    source = StringIO("")
    output = StringIO()
    errors = StringIO()
    assert main(source, output, argv=("--stdin",), error_stream=errors) == 1
    assert output.getvalue() == ""
    assert errors.getvalue() == ""


def test_pyproject_installs_all_FuckMark_console_command_aliases() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    expected = {
        "FuckMark": "fuckmark.cli:main",
        "Fuckmark": "fuckmark.cli:main",
        "fuckmark": "fuckmark.cli:main",
    }
    assert payload["project"]["scripts"] == expected


def test_pyproject_declares_public_project_urls() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["project"]["urls"] == {
        "Homepage": "https://github.com/byte271/FuckMark",
        "Repository": "https://github.com/byte271/FuckMark",
        "Issues": "https://github.com/byte271/FuckMark/issues",
    }
