import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY_RELEASE_INSTALL = ROOT / "tools" / "verify_release_install.py"
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE_WORKFLOW = WORKFLOWS / "release-engineering.yml"
UNIX_INSTALLER = ROOT / "tools" / "install" / "unix.sh"
WINDOWS_INSTALLER = ROOT / "tools" / "install" / "windows.ps1"


def _workflow_run_scripts(text: str) -> list[str]:
    scripts: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("run:"):
            remainder = stripped[4:].lstrip()
            if remainder[:1] in {"|", ">"}:
                body: list[str] = []
                index += 1
                while index < len(lines):
                    current = lines[index]
                    if current.strip() == "":
                        body.append(current)
                        index += 1
                        continue
                    current_indent = len(current) - len(current.lstrip())
                    if current_indent > indent:
                        body.append(current)
                        index += 1
                        continue
                    break
                scripts.append("\n".join(body))
                continue
            scripts.append(remainder)
        index += 1
    return scripts


def test_release_engineering_does_not_auto_tag_publish_or_delete_branches() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "git tag" not in text
    assert "git push" not in text
    assert "persist-credentials: true" not in text
    assert "cleanup-merged" not in text
    assert "/git/refs/heads" not in text
    assert "publish_github_release" in text
    assert "workflow_dispatch" in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "inputs.publish_github_release == true" in text


def test_workflow_dispatch_inputs_are_not_interpolated_into_run_scripts() -> None:
    workflows = sorted(WORKFLOWS.glob("*.yml"))
    assert workflows
    for path in workflows:
        scripts = _workflow_run_scripts(path.read_text(encoding="utf-8"))
        for script in scripts:
            assert "${{ inputs." not in script, path
            assert '""$INPUT_' not in script, path


def test_unix_installer_uses_tagged_release_checksum_and_does_not_start_cli() -> None:
    text = UNIX_INSTALLER.read_text(encoding="utf-8")
    assert UNIX_INSTALLER.stat().st_mode & 0o111
    assert "releases/download" in text
    assert "SHA256SUMS" in text
    assert "v0.4.1" in text
    assert "returns input text unchanged" not in text
    assert 'export PATH="$HOME/.local/bin:$PATH"' not in text
    assert "main.zip" not in text
    assert "force-reinstall" not in text
    assert not any(line.strip().startswith("sudo") for line in text.splitlines())
    assert "apt-get" not in text
    assert text.count("-m fuckmark.cli") == 1
    assert 'Command: fuckmark --help' in text
    assert "hidden Unicode" in text
    assert not text.rstrip().endswith('-m fuckmark.cli')


def test_windows_installer_uses_tagged_release_checksum_and_does_not_start_cli() -> None:
    text = WINDOWS_INSTALLER.read_text(encoding="utf-8")
    assert "releases/download" in text
    assert "SHA256SUMS" in text
    assert "v0.4.1" in text
    assert "returns input text unchanged" not in text
    assert "UnicodeEncoding" not in text
    assert "ASCIIEncoding" in text
    assert "%~dp0" in text
    assert "fuckmark.ps1" in text
    assert "main.zip" not in text
    assert "force-reinstall" not in text
    assert "winget install" not in text
    assert "Starting FuckMark" not in text
    assert text.count("-m fuckmark.cli") == 1
    assert "Command: fuckmark --help" in text
    assert "hidden Unicode" in text


def test_verify_release_install_loads_mix_from_repository_root() -> None:
    text = VERIFY_RELEASE_INSTALL.read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in text
    assert text.index("PROJECT_ROOT = Path") < text.index("from fuckmark.cycle8.letter_mix import apply_letter_alternating_mix")
    assert 'kwargs.setdefault("encoding", "utf-8")' in text
    assert '"PYTHONIOENCODING": "utf-8"' in text
    assert '"PYTHONUTF8": "1"' in text


def test_verify_release_install_imports_under_isolated_interpreter() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(VERIFY_RELEASE_INSTALL)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "ModuleNotFoundError" not in completed.stderr
    assert "usage: verify_release_install.py DIST_DIRECTORY" in completed.stderr


def test_install_docs_do_not_recommend_live_main_or_pipe_installers() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "docs/install.md").read_text(encoding="utf-8")
    for text in (readme, install):
        assert "archive/refs/heads/main.zip" not in text
        assert "| sh" not in text
        assert "|sh" not in text
        assert "| iex" not in text
        assert "irm https" not in text
        assert "SHA256SUMS" in text or "pip install ." in text
    assert "python3 -m pip install ." in readme or ".venv/bin/python -m pip install ." in readme
    assert "releases/download/v0.4.0" not in readme
    assert "releases/download/v0.4.0" in install
    assert "fuckmark-0.4.0-py3-none-any.whl" in install
    assert "SHA256SUMS" in install
    assert "5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f" in readme
    assert "5a6ac62c8bb8d7ddd9e5bc9cb6cee6e3eb181ac5f397b4a6645ef86468ee932f" in install
    assert "cb4ee7b6c06d1dde8c612c237df78f68f8364bc74bf469086288e55a2d5c9325" in install
    assert ".venv/bin/fuckmark --version" in readme
    assert ".venv/bin/fuckmark --visible" in readme or ".venv/bin/fuckmark --status" in readme
    assert "docs/demo.html" in readme
    assert "fuckmark web" in readme
    assert "docs/mark.html" in readme
    assert readme.index("Browser tool") < readme.index("Install from this repository")
    website = (ROOT / "docs/website.md").read_text(encoding="utf-8")
    assert "| sh" not in website
    assert "| iex" not in website
    assert "demo.html" in website
    assert "mark.html" in website
    assert "fuckmark web" in website
    assert (ROOT / "docs/demo.html").is_file()
    assert (ROOT / "docs/mark.html").is_file()


def test_unix_path_config_quotes_custom_bin_directory() -> None:
    text = UNIX_INSTALLER.read_text(encoding="utf-8")
    assert 'BIN="${FUCKMARK_BIN:-$HOME/.local/bin}"' in text
    assert 'quoted="\'${escaped}\'"' in text or "quoted=\"'${escaped}'\"" in text
    assert "export PATH=${quoted}" in text
    assert "fish_add_path ${quoted}" in text
    assert "$HOME/.local/bin:$PATH" not in text


def test_github_action_does_not_interpolate_inputs_into_run_scripts() -> None:
    action = ROOT / "action.yml"
    text = action.read_text(encoding="utf-8")
    scripts = _workflow_run_scripts(text)
    assert scripts
    for script in scripts:
        assert "${{ inputs." not in script, script
    assert "FUCKMARK_SELECT" in text
    assert "FUCKMARK_FIX" in text
    assert "FUCKMARK_JSON" in text
    assert "FUCKMARK_ARGS" in text
    assert "FUCKMARK_PATHS" in text
    assert "shlex.split" in text
