from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from fuckmark import __version__
from fuckmark.cli import (
    INTERACTIVE_DONE,
    RELEASE_CLI_ALGORITHM_VERSION,
    copy_to_clipboard,
    main,
    process_text,
    read_interactive_text,
    transform_text,
)
from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.product.invariants import validate_user_visible_invariants
from fuckmark.product.visible_projection import is_carrier_insertion_v1, product_approved_carriers_v1, project_visible_v1
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
APPROVED = frozenset(LETTER_MIX_APPROVED_CARRIERS)


class TtyIO(StringIO):
    def isatty(self) -> bool:
        return True


def test_cli_process_text_does_not_apply_visible_contractions() -> None:
    source = "I do not agree and I cannot stay."
    applied = process_text(source)
    assert applied == apply_letter_alternating_mix(source)
    assert "don't" not in applied
    assert "can't" not in applied
    assert project_visible_v1(applied, APPROVED) == source
    assert transform_text(source).change_count > 0
    assert transform_text(source).output_text == applied


@pytest.mark.parametrize("source", VISIBLE_FIXTURES)
def test_cli_preserves_exact_visible_projection_on_contract_examples(source: str) -> None:
    applied = process_text(source)
    assert applied == apply_letter_alternating_mix(source)
    assert is_carrier_insertion_v1(source, applied, APPROVED)
    assert project_visible_v1(applied, APPROVED) == source
    assert validate_user_visible_invariants(source, applied, APPROVED).status is InvariantStatus.PASS


def test_historical_visible_edit_registry_still_contracts_for_replay() -> None:
    source = "I do not agree."
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(source)
    candidate = next(value for value in enumeration.candidates if value.rule_id == "contract-do-not")
    result = registry.apply(enumeration, (candidate.candidate_id,))
    assert result.output_text == "I don't agree."
    report = validate_user_visible_invariants(source, result.output_text)
    assert report.status is InvariantStatus.FAIL


def test_cli_process_text_applies_mix_inside_quotes_and_blocks_urls() -> None:
    source = 'Keep "do not change this" but I do not agree.'
    applied = process_text(source)
    assert applied == apply_letter_alternating_mix(source)
    interior = applied[applied.index('"') + 1 : applied.rindex('"')]
    assert "\u034f" in interior or "\ufe00" in interior
    machine = "See https://example.com/do-not-touch and continue."
    mixed = process_text(machine)
    assert "https://example.com/do-not-touch" in mixed
    assert project_visible_v1(mixed, APPROVED) == machine


def test_cli_process_text_fail_closes_without_letter_sites() -> None:
    source = "123."
    assert process_text(source) == source
    assert transform_text(source).change_count == 0


def test_cli_process_text_fail_closes_outside_ascii_domain() -> None:
    source = "I do not agree " + chr(0x00E9) + "."
    assert process_text(source) == source
    assert transform_text(source).change_count == 0


def test_cli_process_text_fail_closes_when_carriers_already_present() -> None:
    source = "I do not agree."
    mixed = apply_letter_alternating_mix(source)
    assert process_text(mixed) == mixed
    assert transform_text(mixed).change_count == 0


def test_cli_respects_selected_site_cap() -> None:
    source = "abcdefghijklmnopqrstuvwxyz" * 12
    applied = process_text(source)
    assert applied.count("\u034f") + applied.count("\ufe00") == 192
    assert project_visible_v1(applied, APPROVED) == source


def test_cli_reads_multiline_paste_until_done_and_keeps_blank_lines() -> None:
    source = TtyIO("I do not agree.\n\nSecond paragraph.\nok is content\n:done\nIgnored\n")
    prompt = StringIO()
    captured = read_interactive_text(source, prompt)
    assert captured == ["I do not agree.", "", "Second paragraph.", "ok is content"]
    assert INTERACTIVE_DONE not in captured
    ui = prompt.getvalue()
    assert ui.startswith("FuckMark\n")
    assert "Paste or type your text below." in ui
    assert "English ASCII only" in ui
    assert ":done" in ui
    assert ui.count("> ") == 5


def test_cli_done_terminates_only_as_the_entire_line() -> None:
    source = TtyIO("say :done please\n:done\n")
    prompt = StringIO()
    assert read_interactive_text(source, prompt) == ["say :done please"]


def test_cli_main_interactive_copies_without_printing_payload() -> None:
    source = TtyIO("I do not agree.\n:done\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors)
    assert status == 0
    expected = apply_letter_alternating_mix("I do not agree.")
    assert copied == [expected]
    assert output.getvalue() == ""
    ui = errors.getvalue()
    assert "FuckMark" in ui
    assert "Processing..." in ui
    assert "Copied to clipboard" in ui
    assert "processed=yes" in ui
    assert "source_length=" in ui
    assert "restores the source" in ui
    assert expected not in ui
    assert "I don't agree." not in ui
    assert project_visible_v1(expected, APPROVED) == "I do not agree."


def test_cli_main_interactive_preserves_blank_lines_and_multiline() -> None:
    source = TtyIO("I do not agree.\n\nYou should not do that.\n:done\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors)
    assert status == 0
    expected = apply_letter_alternating_mix("I do not agree.\n\nYou should not do that.")
    assert copied == [expected]
    assert output.getvalue() == ""
    assert project_visible_v1(expected, APPROVED) == "I do not agree.\n\nYou should not do that."


def test_cli_main_interactive_copies_fail_closed_unicode_without_printing() -> None:
    source_text = "I do not agree " + chr(0x00E9) + "."
    source = TtyIO(source_text + "\n:done\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors)
    assert status == 0
    assert copied == [source_text]
    assert output.getvalue() == ""
    assert "Copied to clipboard" in errors.getvalue()
    assert "unsupported Unicode" in errors.getvalue() or "hidden characters" in errors.getvalue()
    assert "\u034f" not in copied[0]


def test_cli_main_interactive_reports_clipboard_failure_without_printing_payload() -> None:
    source = TtyIO("I do not agree.\n:done\n")
    output = StringIO()
    errors = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(source, output, fail, error_stream=errors)
    assert status == 3
    assert output.getvalue() == ""
    ui = errors.getvalue()
    assert "clipboard copy failed" in ui
    assert "Nothing was printed" in ui
    expected = apply_letter_alternating_mix("I do not agree.")
    assert expected not in ui
    assert "Copied to clipboard" not in ui


def test_cli_main_interactive_eof_without_done_is_clean() -> None:
    source = TtyIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors)
    assert status == 1
    assert copied == []
    assert output.getvalue() == ""
    assert "ended without :done" in errors.getvalue()


def test_cli_main_interactive_ctrl_c_exits_cleanly() -> None:
    class Boom(TtyIO):
        def readline(self, *args, **kwargs):
            raise KeyboardInterrupt

    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(Boom(), output, copied.append, error_stream=errors)
    assert status == 130
    assert copied == []
    assert output.getvalue() == ""
    assert errors.getvalue().endswith("\n")
    assert "Copied to clipboard" not in errors.getvalue()
    assert "Traceback" not in errors.getvalue()


def test_cli_main_interactive_empty_done_is_an_error() -> None:
    source = TtyIO(":done\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors)
    assert status == 1
    assert copied == []
    assert output.getvalue() == ""
    assert "no input" in errors.getvalue()


def test_copy_to_clipboard_sends_utf16_to_windows_clip(monkeypatch) -> None:
    seen: dict[str, object] = {}
    payload = apply_letter_alternating_mix("I do not agree.")

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("fuckmark.cli._clipboard_commands", lambda: (("clip",),))
    monkeypatch.setattr("fuckmark.cli.shutil.which", lambda name: "C:\\Windows\\System32\\clip.exe")
    monkeypatch.setattr("fuckmark.cli.subprocess.run", fake_run)
    copy_to_clipboard(payload)
    assert seen["command"] == ("clip",)
    kwargs = seen["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["input"] == payload.encode("utf-16")
    assert "text" not in kwargs
    assert "encoding" not in kwargs


def test_copy_to_clipboard_sends_utf8_to_unix_tools(monkeypatch) -> None:
    seen: dict[str, object] = {}
    payload = apply_letter_alternating_mix("I do not agree.")

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("fuckmark.cli._clipboard_commands", lambda: (("wl-copy",),))
    monkeypatch.setattr("fuckmark.cli.shutil.which", lambda name: "/usr/bin/wl-copy")
    monkeypatch.setattr("fuckmark.cli.subprocess.run", fake_run)
    copy_to_clipboard(payload)
    assert seen["command"] == ("wl-copy",)
    kwargs = seen["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["input"] == payload
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"


def test_cli_main_copies_raw_mix_payload_with_copy_flag() -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, error_stream=errors, argv=("--stdin", "--copy"))
    assert status == 0
    expected = apply_letter_alternating_mix("I do not agree.\n")
    assert copied == [expected]
    assert output.getvalue() == expected
    assert errors.getvalue() == ""
    assert "I don't agree." not in output.getvalue()


def test_cli_main_prints_result_if_clipboard_copy_fails() -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()

    def fail(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    status = main(source, output, fail, error_stream=errors, argv=("--stdin", "--copy"))
    assert status == 3
    rendered = output.getvalue()
    expected = apply_letter_alternating_mix("I do not agree.\n")
    assert expected in rendered
    assert "I don't agree." not in rendered
    assert "clipboard copy failed" in errors.getvalue()
    assert output.getvalue().count(expected) == 1


def test_cli_version_reports_project_identity(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--version",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out.strip()
    assert rendered == f"FuckMark {__version__}"
    assert RELEASE_CLI_ALGORITHM_VERSION == "release-cli-v5"
    assert "release-cli-v5" not in rendered
    assert "transform-registry" not in rendered


@pytest.mark.parametrize("option", (("--stdin",), ("--non-interactive",)))
def test_cli_noninteractive_mode_writes_only_transformed_text(option) -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    copied: list[str] = []
    status = main(source, output, copied.append, argv=option)
    assert status == 0
    assert output.getvalue() == apply_letter_alternating_mix("I do not agree.\n")
    assert copied == []


def test_cli_rejects_latin1_and_visible_flag_strips_to_source() -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    assert main(source, output, error_stream=errors, argv=("--stdin", "--encoding", "latin-1")) == 1
    assert output.getvalue() == ""
    assert "only UTF-8 is supported" in errors.getvalue()
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
    assert "no input" in errors.getvalue()


def test_cli_reads_file_and_atomically_writes_output(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    target = tmp_path / "output.txt"
    source.write_text("I do not agree.\n", encoding="utf-8")
    output = StringIO()
    errors = StringIO()
    assert main(output_stream=output, error_stream=errors, argv=(str(source), "--output", str(target))) == 0
    assert output.getvalue() == ""
    assert errors.getvalue() == ""
    assert target.read_text(encoding="utf-8") == apply_letter_alternating_mix("I do not agree.\n")


def test_cli_refuses_to_overwrite_its_input_file(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("I do not agree.\n", encoding="utf-8")
    errors = StringIO()
    assert main(error_stream=errors, argv=(str(source), "--output", str(source))) == 1
    assert "input and output files must be different" in errors.getvalue()
    assert source.read_text(encoding="utf-8") == "I do not agree.\n"


def test_cli_writes_mix_when_stdio_starts_as_cp1252() -> None:
    raw_out = BytesIO()
    source = TextIOWrapper(BytesIO(b"I do not agree.\n"), encoding="cp1252", newline="")
    output = TextIOWrapper(raw_out, encoding="cp1252", newline="")
    errors = StringIO()
    status = main(source, output, argv=("--stdin",), error_stream=errors)
    assert status == 0
    assert errors.getvalue() == ""
    output.flush()
    assert raw_out.getvalue() == apply_letter_alternating_mix("I do not agree.\n").encode("utf-8")


def test_cli_automatically_uses_stream_mode_for_a_pipe(monkeypatch) -> None:
    source = StringIO("I do not agree.\n")
    output = StringIO()
    errors = StringIO()
    monkeypatch.setattr(sys, "stdin", source)
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "stderr", errors)
    assert main(argv=()) == 0
    assert output.getvalue() == apply_letter_alternating_mix("I do not agree.\n")
    assert errors.getvalue() == ""


def test_cli_help_documents_file_pipe_clipboard_and_visible_contract(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "TEXT_OR_FILE" in rendered
    assert "--stdin" in rendered
    assert "--copy" in rendered
    assert "--visible" in rendered
    assert "--encoding" in rendered
    assert "--output" in rendered
    assert "visible" in rendered
    assert "latin-1" in rendered
    assert "printf" in rendered
    assert "fuckmark \"I do not agree.\"" in rendered
    assert "--text" in rendered
    assert "--file" in rendered
    assert "--status" in rendered
    assert "--inspect" in rendered
    assert "standard input" in rendered.casefold() or "--stdin" in rendered
    assert ":done" in rendered
    assert "clipboard" in rendered.casefold()
    assert "curly" in rendered.casefold()


def test_cli_quoted_text_argument_transforms_without_a_file() -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=("I do not agree.",))
    assert status == 0
    assert output.getvalue() == apply_letter_alternating_mix("I do not agree.")
    assert errors.getvalue() == ""


def test_cli_missing_path_like_argument_is_an_error(tmp_path: Path) -> None:
    missing = tmp_path / "notes.txt"
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=(str(missing),))
    assert status == 1
    assert output.getvalue() == ""
    assert "file not found" in errors.getvalue()


def test_cli_directory_argument_is_an_error(tmp_path: Path) -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(""), output, error_stream=errors, argv=(str(tmp_path),))
    assert status == 1
    assert output.getvalue() == ""
    assert "directory" in errors.getvalue()


def test_cli_rejects_stdin_flag_with_a_source() -> None:
    output = StringIO()
    errors = StringIO()
    status = main(StringIO("I do not agree.\n"), output, error_stream=errors, argv=("--stdin", "I do not agree."))
    assert status == 1
    assert output.getvalue() == ""
    assert "not both" in errors.getvalue()


def test_cli_stdin_returns_unsupported_unicode_unchanged() -> None:
    source_text = "I do not agree " + chr(0x00E9) + ".\n"
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(source_text), output, error_stream=errors, argv=("--stdin",))
    assert status == 0
    assert output.getvalue() == source_text
    assert "unsupported Unicode" in errors.getvalue() or "hidden characters" in errors.getvalue()


def test_cli_stdin_keeps_multiline_visible_text() -> None:
    source_text = "I do not agree.\nYou should not do that.\n"
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(source_text), output, error_stream=errors, argv=("--stdin",))
    assert status == 0
    applied = apply_letter_alternating_mix(source_text)
    assert output.getvalue() == applied
    assert project_visible_v1(applied, APPROVED) == source_text
    assert errors.getvalue() == ""


def test_cli_stdin_respects_selected_site_cap() -> None:
    source_text = "abcdefghijklmnopqrstuvwxyz" * 12
    output = StringIO()
    errors = StringIO()
    status = main(StringIO(source_text), output, error_stream=errors, argv=("--stdin",))
    assert status == 0
    applied = output.getvalue()
    assert applied.count("\u034f") + applied.count("\ufe00") == 192
    assert project_visible_v1(applied, APPROVED) == source_text
    assert "site cap" in errors.getvalue() or "192" in errors.getvalue()


def test_cli_rejects_invalid_utf8_stdin() -> None:
    source = TextIOWrapper(BytesIO(b"\xff\xfe not utf-8"), encoding="utf-8", errors="strict")
    output = StringIO()
    errors = StringIO()
    status = main(source, output, error_stream=errors, argv=("--stdin",))
    assert status == 1
    assert output.getvalue() == ""
    assert "UTF-8" in errors.getvalue()


def test_cli_help_stays_product_facing(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "Cycle 8" not in rendered
    assert "Gate v2" not in rendered
    assert "carrier" not in rendered.casefold()


def test_release_registry_contains_no_visible_edit_transforms() -> None:
    release_ids = {rule.rule_id for rule in release_transform_registry().rules}
    historical_ids = {rule.rule_id for rule in historical_visible_edit_transform_registry().rules}
    assert release_ids == set()
    assert "contract-do-not" in historical_ids
    assert historical_visible_edit_transform_registry().ruleset_hash != release_transform_registry().ruleset_hash
    assert product_approved_carriers_v1() == APPROVED


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
