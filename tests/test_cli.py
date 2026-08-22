from io import StringIO
from pathlib import Path
import sys
import tomllib

import pytest

from fuckmark.cli import main, process_text, read_pasted_text, transform_text


def test_cli_process_text_uses_release_contractions_deterministically() -> None:
    source = "I do not agree and I cannot stay."
    expected = "I don't agree and I can't stay."
    assert process_text(source) == expected
    assert process_text(source) == expected
    assert transform_text(source).change_count == 2


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
    assert "Finish with :done on its own line" in output.getvalue()


def test_cli_main_processes_and_copies_result() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == ["I don't agree."]
    rendered = output.getvalue()
    assert "FuckMark 0.1.0" in rendered
    assert "Processing..." in rendered
    assert "Done — 1 change applied." in rendered
    assert "Copied to clipboard." in rendered


def test_cli_main_copies_original_when_no_change_is_eligible() -> None:
    source = StringIO("Already concise.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == ["Already concise."]
    assert "no eligible release-safe changes" in output.getvalue()


def test_cli_main_prints_result_if_clipboard_copy_fails() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    errors = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(source, output, fail, error_stream=errors)
    assert status == 2
    rendered = output.getvalue()
    assert "I don't agree." in rendered
    assert "clipboard copy failed" in errors.getvalue()


def test_cli_version_reports_project_and_algorithm_identity(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--version",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "FuckMark 0.1.0" in rendered
    assert "release-cli-v3" in rendered
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
    assert errors.getvalue() == "FuckMark: no input text received\n"


def test_cli_reads_file_and_atomically_writes_output(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    target = tmp_path / "output.txt"
    source.write_text("I do not agree.\n", encoding="utf-8")
    output = StringIO()
    errors = StringIO()
    assert main(output_stream=output, error_stream=errors, argv=(str(source), "--output", str(target))) == 0
    assert output.getvalue() == ""
    assert errors.getvalue() == ""
    assert target.read_text(encoding="utf-8") == "I don't agree.\n"


def test_cli_refuses_to_overwrite_its_input_file(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("I do not agree.\n", encoding="utf-8")
    errors = StringIO()
    assert main(error_stream=errors, argv=(str(source), "--output", str(source))) == 1
    assert "input and output paths must be different" in errors.getvalue()
    assert source.read_text(encoding="utf-8") == "I do not agree.\n"


def test_cli_automatically_uses_stream_mode_for_a_pipe(monkeypatch) -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    monkeypatch.setattr(sys, "stdin", source)
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "stderr", errors)
    assert main(argv=()) == 0
    assert output.getvalue() == "I don't agree.\n"
    assert errors.getvalue() == ""


def test_cli_help_documents_file_pipe_clipboard_and_output(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "FILE" in rendered
    assert "--stdin" in rendered
    assert "--copy" in rendered
    assert "--output" in rendered


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
        "Homepage": "https://mark.q1z.org",
        "Repository": "https://github.com/byte271/FuckMark",
        "Issues": "https://github.com/byte271/FuckMark/issues",
    }


def test_pyproject_declares_owner_selected_mit_license() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["project"]["license"] == "MIT"
    assert payload["project"]["license-files"] == ["LICENSE"]
    assert (root / "LICENSE").read_text(encoding="utf-8").startswith("MIT License\n")
