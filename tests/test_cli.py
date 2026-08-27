from io import StringIO
from pathlib import Path
import sys
import tomllib

import pytest

from fuckmark import __version__
from fuckmark.cli import RELEASE_CLI_ALGORITHM_VERSION, main, process_text, read_pasted_text, transform_text
from fuckmark.product.invariants import validate_user_visible_invariants
from fuckmark.product.visible_projection import is_carrier_insertion_v1
from fuckmark.transforms.registry import (
    historical_visible_edit_transform_registry,
    release_transform_registry,
)
from fuckmark.transforms.schema import InvariantStatus


VISIBLE_FIXTURES = (
    "I do not agree.",
    "We cannot continue.",
    "You should not do that.",
    "It's important to test this.",
    "This is a proof of concept.",
    "However, the result matters.",
    "All of the examples are relevant.",
)


def test_cli_process_text_does_not_apply_visible_contractions() -> None:
    source = "I do not agree and I cannot stay."
    assert process_text(source) == source
    assert transform_text(source).change_count == 0
    assert transform_text(source).output_text == source


@pytest.mark.parametrize("source", VISIBLE_FIXTURES)
def test_cli_preserves_exact_visible_projection_on_contract_examples(source: str) -> None:
    assert process_text(source) == source
    assert is_carrier_insertion_v1(source, process_text(source), ())


def test_historical_visible_edit_registry_still_contracts_for_replay() -> None:
    source = "I do not agree."
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(source)
    candidate = next(value for value in enumeration.candidates if value.rule_id == "contract-do-not")
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == "I don't agree."
    report = validate_user_visible_invariants(source, result.output_text)
    assert report.status is InvariantStatus.FAIL


def test_cli_process_text_preserves_quoted_and_unquoted_visible_text() -> None:
    source = 'Keep "do not change this" but I do not agree.'
    assert process_text(source) == source


def test_cli_process_text_preserves_text_when_no_candidate_is_eligible() -> None:
    source = "Already concise."
    assert process_text(source) == source


def test_cli_reads_multiline_paste_until_ok_line() -> None:
    source = StringIO("First line\nSecond line\nok\nIgnored line\n")
    output = StringIO()
    assert read_pasted_text(source, output) == "First line\nSecond line"
    assert "Finish with :done on its own line" in output.getvalue()


def test_cli_main_processes_unchanged_visible_text_without_copying() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == []
    rendered = output.getvalue()
    assert f"FuckMark {__version__}" in rendered
    assert "Processing..." in rendered
    assert "visible text left unchanged" in rendered
    assert "Copied to clipboard." not in rendered
    assert "I do not agree." in rendered
    assert "I don't agree." not in rendered


def test_cli_main_leaves_original_when_no_change_is_eligible() -> None:
    source = StringIO("Already concise.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append)
    assert status == 0
    assert copied == []
    rendered = output.getvalue()
    assert "Already concise." in rendered
    assert "visible text left unchanged" in rendered
    assert "Copied to clipboard." not in rendered


def test_cli_main_copies_only_with_copy_flag() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, argv=("--copy",))
    assert status == 0
    assert copied == ["I do not agree."]
    rendered = output.getvalue()
    assert "Copied to clipboard." in rendered
    assert "I don't agree." not in rendered


def test_cli_main_prints_result_if_clipboard_copy_fails() -> None:
    source = StringIO("I do not agree.\nok\n")
    output = StringIO()
    errors = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(source, output, fail, error_stream=errors, argv=("--copy",))
    assert status == 2
    rendered = output.getvalue()
    assert "I do not agree." in rendered
    assert "I don't agree." not in rendered
    assert "clipboard copy failed" in errors.getvalue()


def test_cli_version_reports_project_and_algorithm_identity(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--version",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert f"FuckMark {__version__}" in rendered
    assert RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v4"
    assert "release-cli-v4" in rendered
    assert "transform-registry-v6" in rendered


@pytest.mark.parametrize("option", (("--stdin",), ("--non-interactive",)))
def test_cli_noninteractive_mode_writes_only_transformed_text(option) -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, argv=option)
    assert status == 0
    assert output.getvalue() == "I do not agree.\n"
    assert copied == []


def test_cli_rejects_latin1_and_keeps_visible_projection_identity() -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    assert main(source, output, error_stream=errors, argv=("--stdin", "--encoding", "latin-1")) == 1
    assert output.getvalue() == ""
    assert "unsupported product encoding" in errors.getvalue()
    copied: list[str] = []
    visible_out = StringIO()
    status = main(StringIO("I do not agree.\n"), visible_out, copied.append, argv=("--stdin", "--visible"))
    assert status == 0
    assert visible_out.getvalue() == "I do not agree.\n"
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
    assert target.read_text(encoding="utf-8") == "I do not agree.\n"


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
    assert output.getvalue() == "I do not agree.\n"
    assert errors.getvalue() == ""


def test_cli_help_documents_file_pipe_clipboard_and_visible_contract(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "FILE" in rendered
    assert "--stdin" in rendered
    assert "--copy" in rendered
    assert "--visible" in rendered
    assert "--encoding" in rendered
    assert "--output" in rendered
    assert "user-visible" in rendered
    assert "latin-1" in rendered


def test_release_registry_contains_no_visible_edit_transforms() -> None:
    release_ids = {rule.rule_id for rule in release_transform_registry().rules}
    historical_ids = {rule.rule_id for rule in historical_visible_edit_transform_registry().rules}
    assert release_ids == set()
    assert "contract-do-not" in historical_ids
    assert historical_visible_edit_transform_registry().ruleset_hash != release_transform_registry().ruleset_hash


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
