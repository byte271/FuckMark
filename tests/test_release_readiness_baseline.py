from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from fuckmark.experiments import release_readiness as release_readiness_module
from fuckmark.experiments.release_readiness import (
    FROZEN_V010_RELEASE_READINESS_BASELINE,
    RELEASE_READINESS_BASELINE_ALGORITHM_VERSION,
    V010_BASELINE_COMMIT,
    V010_RELEASE_RULESET_HASH,
    ReleaseGateStatus,
    load_release_readiness_baseline,
    verify_v010_baseline_repository,
)
from fuckmark.release_readiness_baseline import main


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _artifact() -> Path:
    return _root() / "specs" / "fuckmark-v0.1.0-release-readiness-baseline.json"


def test_frozen_release_readiness_baseline_binds_current_release_blockers() -> None:
    baseline = FROZEN_V010_RELEASE_READINESS_BASELINE
    gates = {value.gate_id: value for value in baseline.gates}
    assert baseline.algorithm_version == RELEASE_READINESS_BASELINE_ALGORITHM_VERSION
    assert baseline.baseline_commit == V010_BASELINE_COMMIT
    assert baseline.release_ruleset_hash == V010_RELEASE_RULESET_HASH
    assert gates["main-baseline-reproducible"].status is ReleaseGateStatus.PASS
    assert gates["project-license"].status is ReleaseGateStatus.BLOCKED
    assert gates["calibration-select-audit-independence"].status is ReleaseGateStatus.BLOCKED
    assert gates["normalization-benchmark"].status is ReleaseGateStatus.PENDING
    assert gates["diverse-beam-real-corpus-win"].required is False


def test_release_readiness_artifact_replays_byte_for_byte() -> None:
    loaded = load_release_readiness_baseline(_artifact())
    assert loaded == FROZEN_V010_RELEASE_READINESS_BASELINE


def test_release_readiness_rejects_tampering(tmp_path: Path) -> None:
    value = json.loads(_artifact().read_text(encoding="utf-8"))
    value["project_version"] = "0.1.1"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash"):
        load_release_readiness_baseline(path)
    with pytest.raises(ValueError, match="artifact hash"):
        replace(FROZEN_V010_RELEASE_READINESS_BASELINE, project_version="0.1.1")


def test_release_readiness_cli_generates_and_verifies(tmp_path: Path, capsys) -> None:
    path = tmp_path / "baseline.json"
    assert main(["--repository-root", str(_root()), "--json", str(path)]) == 0
    assert load_release_readiness_baseline(path) == FROZEN_V010_RELEASE_READINESS_BASELINE
    assert main(["--repository-root", str(_root()), "--verify-json", str(path)]) == 0
    output = capsys.readouterr().out
    assert output.count("artifact_hash=") == 2
    assert "gate_count=26" in output


def test_release_readiness_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    value = json.loads(_artifact().read_text(encoding="utf-8"))
    value["unexpected"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="keys"):
        load_release_readiness_baseline(path)


def test_release_readiness_cli_requires_exactly_one_mode() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        main(["--repository-root", str(_root())])


def test_baseline_source_verifier_rejects_a_different_checkout_commit(monkeypatch) -> None:
    def git_stdout(root: Path, *args: str) -> str:
        if args == ("rev-parse", "--show-toplevel"):
            return str(root.resolve())
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return "0" * 40
        raise AssertionError(args)

    monkeypatch.setattr(release_readiness_module, "_git_stdout", git_stdout)
    with pytest.raises(ValueError, match="commit drifted"):
        verify_v010_baseline_repository(_root())
