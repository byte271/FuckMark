import json
from io import StringIO
from pathlib import Path

from fuckmark.cli import main
from fuckmark.lint import (
    LINT_DEFAULT_CATEGORIES,
    LINT_EXIT_FINDINGS,
    LINT_EXIT_OK,
    LINT_EXIT_USAGE,
    run_lint_argv,
)


TROJAN = "if (level != \u202eadmin\u202c) {}\n"


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = run_lint_argv(argv, out, err)
    return code, out.getvalue(), err.getvalue()


def test_default_categories_are_security_focused() -> None:
    assert "bidi_control" in LINT_DEFAULT_CATEGORIES
    assert "tag" in LINT_DEFAULT_CATEGORIES
    assert "variation_selector" not in LINT_DEFAULT_CATEGORIES


def test_clean_tree_passes(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("nothing hidden here\n", encoding="utf-8")
    code, _out, err = _run([str(tmp_path)])
    assert code == LINT_EXIT_OK
    assert "no hidden characters" in err


def test_finds_trojan_source_and_zero_width(tmp_path: Path) -> None:
    (tmp_path / "evil.js").write_text(TROJAN, encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "z.txt").write_text("hello\u200bworld\n", encoding="utf-8")
    code, out, err = _run([str(tmp_path)])
    assert code == LINT_EXIT_FINDINGS
    assert "evil.js" in out
    assert "U+202E" in out
    assert "z.txt" in out
    assert "found 3 hidden characters" in err


def test_json_report_structure(tmp_path: Path) -> None:
    (tmp_path / "evil.js").write_text(TROJAN, encoding="utf-8")
    code, out, err = _run(["--json", str(tmp_path)])
    assert code == LINT_EXIT_FINDINGS
    assert err == ""
    report = json.loads(out)
    assert report["algorithm_version"] == "fuckmark-lint-v1"
    assert report["files_with_findings"] == 1
    assert report["total_findings"] == 2
    result = report["results"][0]
    assert result["counts"]["bidi_control"] == 2
    assert result["locations"][0]["codepoint"] == "U+202E"
    assert result["locations"][0]["severity"] == "critical"
    assert result["locations"][0]["context"] == "identifier"
    assert result["locations"][0]["why"]
    assert result["locations"][0]["remedy"]


def test_javascript_comment_context_from_suffix(tmp_path: Path) -> None:
    (tmp_path / "note.js").write_text("// \u202e\n", encoding="utf-8")
    code, out, err = _run(["--json", str(tmp_path)])
    assert code == LINT_EXIT_FINDINGS
    assert err == ""
    report = json.loads(out)
    location = report["results"][0]["locations"][0]
    assert location["context"] == "comment"
    assert location["severity"] == "critical"
    assert location["codepoint"] == "U+202E"


def test_fix_rewrites_files_and_then_passes(tmp_path: Path) -> None:
    target = tmp_path / "evil.js"
    target.write_text(TROJAN, encoding="utf-8")
    code, _out, err = _run(["--fix", str(tmp_path)])
    assert code == LINT_EXIT_FINDINGS
    assert "fixed 1 file" in err
    assert target.read_text(encoding="utf-8") == "if (level != admin) {}\n"
    again, _out2, err2 = _run([str(tmp_path)])
    assert again == LINT_EXIT_OK
    assert "no hidden characters" in err2


def test_select_controls_which_categories_fail(tmp_path: Path) -> None:
    target = tmp_path / "emoji.txt"
    target.write_text("star\ufe0f\n", encoding="utf-8")
    default_code, _o, _e = _run([str(tmp_path)])
    assert default_code == LINT_EXIT_OK
    all_code, out, _e2 = _run(["--select", "all", str(tmp_path)])
    assert all_code == LINT_EXIT_FINDINGS
    assert "variation_selector" in out
    only_code, _o3, _e3 = _run(["--select", "variation_selector", str(tmp_path)])
    assert only_code == LINT_EXIT_FINDINGS


def test_unknown_category_is_usage_error(tmp_path: Path) -> None:
    code, _out, err = _run(["--select", "not_a_category", str(tmp_path)])
    assert code == LINT_EXIT_USAGE
    assert "unknown scan categories" in err


def test_binary_and_non_utf8_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02hidden\x00")
    (tmp_path / "latin.txt").write_bytes(b"caf\xe9 only\n")
    (tmp_path / "clean.txt").write_text("plain\n", encoding="utf-8")
    code, _out, err = _run([str(tmp_path)])
    assert code == LINT_EXIT_OK
    assert "2 skipped" in err


def test_excluded_directories_are_pruned(tmp_path: Path) -> None:
    vcs = tmp_path / ".git"
    vcs.mkdir()
    (vcs / "hook.js").write_text(TROJAN, encoding="utf-8")
    (tmp_path / "clean.txt").write_text("ok\n", encoding="utf-8")
    code, _out, err = _run([str(tmp_path)])
    assert code == LINT_EXIT_OK


def test_exclude_glob_skips_matching_files(tmp_path: Path) -> None:
    (tmp_path / "evil.min.js").write_text(TROJAN, encoding="utf-8")
    (tmp_path / "clean.txt").write_text("ok\n", encoding="utf-8")
    code, _out, _err = _run(["--exclude", "*.min.js", str(tmp_path)])
    assert code == LINT_EXIT_OK


def test_scan_a_single_file(tmp_path: Path) -> None:
    target = tmp_path / "evil.js"
    target.write_text(TROJAN, encoding="utf-8")
    code, out, _err = _run([str(target)])
    assert code == LINT_EXIT_FINDINGS
    assert "evil.js" in out


def test_cli_main_dispatches_lint(tmp_path: Path) -> None:
    (tmp_path / "evil.js").write_text(TROJAN, encoding="utf-8")
    out, err = StringIO(), StringIO()
    code = main(StringIO(""), out, error_stream=err, argv=("lint", str(tmp_path)))
    assert code == LINT_EXIT_FINDINGS
    assert "U+202E" in out.getvalue()


def test_lint_help_returns_zero() -> None:
    out, err = StringIO(), StringIO()
    code = main(StringIO(""), out, error_stream=err, argv=("lint", "--help"))
    assert code == LINT_EXIT_OK


def test_cesu8_lone_surrogate_files_are_findings_not_skipped(tmp_path: Path) -> None:
    target = tmp_path / "lone.txt"
    target.write_bytes("ok\ud800\n".encode("utf-8", "surrogatepass"))
    code, out, err = _run(["--json", str(target)])
    assert code == LINT_EXIT_FINDINGS
    assert "skipped" not in err or "0 skipped" in err
    report = json.loads(out)
    assert report["files_skipped"] == 0
    assert report["files_with_findings"] == 1
    assert report["results"][0]["counts"]["surrogate"] == 1
    assert report["results"][0]["locations"][0]["codepoint"] == "U+D800"


def test_fix_strips_surrogates_and_keeps_unselected(tmp_path: Path) -> None:
    target = tmp_path / "mixed.txt"
    target.write_bytes("\u202e\ud800".encode("utf-8", "surrogatepass"))
    code, _out, err = _run(["--fix", str(target)])
    assert code == LINT_EXIT_FINDINGS
    assert "fixed 1 file" in err
    assert target.read_bytes() == b""
    again = tmp_path / "partial.txt"
    again.write_bytes("\u202e\ud800".encode("utf-8", "surrogatepass"))
    partial, _o2, _e2 = _run(["--fix", "--select", "bidi_control", str(again)])
    assert partial == LINT_EXIT_FINDINGS
    leftover = again.read_bytes().decode("utf-8", "surrogatepass")
    assert leftover == "\ud800"
