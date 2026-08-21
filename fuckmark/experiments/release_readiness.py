from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .._validation import require_bool, require_clean_string, require_sha256
from ..hashing import sha256_file, sha256_json


RELEASE_READINESS_BASELINE_ALGORITHM_VERSION = "release-readiness-baseline-v1"
V010_BASELINE_COMMIT = "afc8794be68c9495348c4934f2dd7e6cf4c61ce9"
V010_BASELINE_TREE = "791cf94cfd0a318046796e89bbed0151342a1239"
V010_BASELINE_UV_LOCK_HASH = "11a5b1e6c8ab04114fb57829f27beb6c6a3017725252f03473c3ddf179152f4d"
V010_BASELINE_SPEC_HASH = "089e32ab5477038adbb47b63eeaeddd1fa95dfcd226f1770d8b174ead088dc9a"
V010_BASELINE_README_HASH = "e648386b5afb801df7baed35e028874ab18c76ed7110cd6dff36d8464f2dc30d"
V010_BASELINE_PYPROJECT_HASH = "dca929c18caf732910e9a89070dbd72801b34788355e6d88006ad5343f7de01e"
V010_RELEASE_RULESET_HASH = "9ad0406d2019dd4e6d6fb7335b731fb2656efe342ed155a4891c75710aff82cd"
V010_RELEASE_RULE_IDS = (
    "contract-cannot",
    "contract-did-not",
    "contract-do-not",
    "contract-does-not",
    "contract-should-not",
    "contract-will-not",
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReleaseGateStatus(str, Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"
    SCIENTIFIC_REJECTION = "SCIENTIFIC_REJECTION"


@dataclass(frozen=True, slots=True)
class ReleaseReadinessEvidence:
    evidence_id: str
    status: ReleaseGateStatus
    reference: str
    result: str

    def __post_init__(self) -> None:
        require_clean_string("evidence_id", self.evidence_id)
        if not isinstance(self.status, ReleaseGateStatus):
            raise TypeError("status must be a ReleaseGateStatus")
        require_clean_string("reference", self.reference)
        require_clean_string("result", self.result)


@dataclass(frozen=True, slots=True)
class ReleaseReadinessGate:
    gate_id: str
    required: bool
    status: ReleaseGateStatus
    evidence_ids: tuple[str, ...]
    consequence: str

    def __post_init__(self) -> None:
        require_clean_string("gate_id", self.gate_id)
        require_bool("required", self.required)
        if not isinstance(self.status, ReleaseGateStatus):
            raise TypeError("status must be a ReleaseGateStatus")
        if not isinstance(self.evidence_ids, tuple):
            raise TypeError("evidence_ids must be a tuple")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if self.evidence_ids != tuple(sorted(self.evidence_ids)):
            raise ValueError("evidence_ids must be canonically ordered")
        for value in self.evidence_ids:
            require_clean_string("evidence_id", value)
        require_clean_string("consequence", self.consequence)


@dataclass(frozen=True, slots=True)
class ReleaseReadinessBaseline:
    algorithm_version: str
    project_version: str
    baseline_commit: str
    baseline_tree: str
    python_versions: tuple[str, ...]
    uv_lock_hash: str
    spec_hash: str
    readme_hash: str
    pyproject_hash: str
    release_ruleset_hash: str
    release_rule_ids: tuple[str, ...]
    algorithm_identities: tuple[tuple[str, str], ...]
    evidence: tuple[ReleaseReadinessEvidence, ...]
    gates: tuple[ReleaseReadinessGate, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != RELEASE_READINESS_BASELINE_ALGORITHM_VERSION:
            raise ValueError("unsupported release readiness baseline version")
        require_clean_string("project_version", self.project_version)
        for name in ("baseline_commit", "baseline_tree"):
            value = getattr(self, name)
            require_clean_string(name, value)
            if _GIT_SHA_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be a lowercase Git SHA")
        if self.python_versions != ("3.11", "3.12", "3.13"):
            raise ValueError("python_versions must contain the frozen supported matrix")
        for name in (
            "uv_lock_hash",
            "spec_hash",
            "readme_hash",
            "pyproject_hash",
            "release_ruleset_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.release_rule_ids, tuple) or not self.release_rule_ids:
            raise TypeError("release_rule_ids must be a non-empty tuple")
        if self.release_rule_ids != tuple(sorted(self.release_rule_ids)):
            raise ValueError("release_rule_ids must be canonically ordered")
        if len(set(self.release_rule_ids)) != len(self.release_rule_ids):
            raise ValueError("release_rule_ids must be unique")
        for value in self.release_rule_ids:
            require_clean_string("release_rule_id", value)
        if not isinstance(self.algorithm_identities, tuple) or not self.algorithm_identities:
            raise TypeError("algorithm_identities must be a non-empty tuple")
        if self.algorithm_identities != tuple(sorted(self.algorithm_identities)):
            raise ValueError("algorithm_identities must be canonically ordered")
        if len({name for name, _ in self.algorithm_identities}) != len(self.algorithm_identities):
            raise ValueError("algorithm identity names must be unique")
        for name, value in self.algorithm_identities:
            require_clean_string("algorithm identity name", name)
            require_clean_string("algorithm identity value", value)
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise TypeError("evidence must be a non-empty tuple")
        if any(not isinstance(value, ReleaseReadinessEvidence) for value in self.evidence):
            raise TypeError("evidence must contain ReleaseReadinessEvidence values")
        evidence_ids = tuple(value.evidence_id for value in self.evidence)
        if evidence_ids != tuple(sorted(evidence_ids)) or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence must use unique canonical evidence_id ordering")
        if not isinstance(self.gates, tuple) or not self.gates:
            raise TypeError("gates must be a non-empty tuple")
        if any(not isinstance(value, ReleaseReadinessGate) for value in self.gates):
            raise TypeError("gates must contain ReleaseReadinessGate values")
        gate_ids = tuple(value.gate_id for value in self.gates)
        if gate_ids != tuple(sorted(gate_ids)) or len(set(gate_ids)) != len(gate_ids):
            raise ValueError("gates must use unique canonical gate_id ordering")
        known_evidence = set(evidence_ids)
        if any(not set(value.evidence_ids) <= known_evidence for value in self.gates):
            raise ValueError("gate references unknown evidence")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("release readiness artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "project_version": self.project_version,
            "baseline_commit": self.baseline_commit,
            "baseline_tree": self.baseline_tree,
            "python_versions": self.python_versions,
            "uv_lock_hash": self.uv_lock_hash,
            "spec_hash": self.spec_hash,
            "readme_hash": self.readme_hash,
            "pyproject_hash": self.pyproject_hash,
            "release_ruleset_hash": self.release_ruleset_hash,
            "release_rule_ids": self.release_rule_ids,
            "algorithm_identities": self.algorithm_identities,
            "evidence": self.evidence,
            "gates": self.gates,
        }


def _evidence() -> tuple[ReleaseReadinessEvidence, ...]:
    rows = (
        ("calibration-cross-role-collision-audit", ReleaseGateStatus.BLOCKED, "MidDev calibration v2 merged pair", "55 unique exact cross-role generated-content collisions; strict independence gate rejected the pair"),
        ("ci-python-matrix", ReleaseGateStatus.PASS, "GitHub Actions run 32455782049", "Python 3.11, 3.12, and 3.13 tests, lock checks, installed CLI E2E, and frozen calibration readiness passed"),
        ("geometry-v3-decision", ReleaseGateStatus.SCIENTIFIC_REJECTION, "GitHub Actions run 32455781863", "K2_V3_SEARCH_HAS_NO_MATCHED_COST_GAIN; artifact 794bbcbaccd256e77da657aa996753ea1508fe93b2ec9090e0e2639a8f52e61e"),
        ("license-audit", ReleaseGateStatus.BLOCKED, "main tree 791cf94cfd0a318046796e89bbed0151342a1239", "Project LICENSE absent and pyproject project.license metadata absent"),
        ("linux-artifact-install", ReleaseGateStatus.PASS, "local clean artifact audit at baseline commit afc8794be68c9495348c4934f2dd7e6cf4c61ce9", "Wheel and sdist built and installed; all three command spellings passed Linux CLI E2E"),
        ("local-python-3.12-suite", ReleaseGateStatus.PASS, "baseline commit afc8794be68c9495348c4934f2dd7e6cf4c61ce9", "1285 passed and 10 skipped"),
        ("middev-full-matrix", ReleaseGateStatus.PASS, "GitHub Actions run 32455781833", "Full matrix, full repository regression, and frozen TinyDev replay passed"),
        ("package-metadata-audit", ReleaseGateStatus.BLOCKED, "fuckmark 0.1.0 wheel and sdist metadata", "License and License-Expression fields are absent"),
        ("public-cli-audit", ReleaseGateStatus.BLOCKED, "fuckmark.cli at baseline commit afc8794be68c9495348c4934f2dd7e6cf4c61ce9", "Interactive clipboard path works; --version and non-interactive stdin/stdout mode are absent"),
        ("release-registry-snapshot", ReleaseGateStatus.PASS, "release ruleset 9ad0406d2019dd4e6d6fb7335b731fb2656efe342ed155a4891c75710aff82cd", "Public registry contains six deterministic default contraction rules and no development-only rules"),
        ("tinydev-context-survival", ReleaseGateStatus.PASS, "GitHub Actions run 32455781887", "Detector-blind plan freeze, independent scoring, and artifact upload passed"),
        ("tinydev-extended-transform", ReleaseGateStatus.PASS, "GitHub Actions run 32455781903", "Real TinyDev extended transform evidence passed"),
        ("tinydev-transform-evidence", ReleaseGateStatus.PASS, "GitHub Actions run 32455781839", "Real TinyDev transform evidence passed"),
        ("tinydev-transformability", ReleaseGateStatus.PASS, "GitHub Actions run 32455781849", "Real TinyDev transformability passed"),
    )
    return tuple(sorted((ReleaseReadinessEvidence(*value) for value in rows), key=lambda value: value.evidence_id))


def _gates() -> tuple[ReleaseReadinessGate, ...]:
    rows = (
        ("cal-audit-threshold-consistency", True, ReleaseGateStatus.BLOCKED, ("calibration-cross-role-collision-audit",), "Repair calibration before threshold audit"),
        ("calibration-select-audit-independence", True, ReleaseGateStatus.BLOCKED, ("calibration-cross-role-collision-audit",), "Return to calibration repair"),
        ("confirmatory-primary-endpoint", True, ReleaseGateStatus.PENDING, (), "Return to the earliest causal capability phase if the endpoint fails"),
        ("dependency-lock-checks", True, ReleaseGateStatus.PASS, ("ci-python-matrix",), "Fix dependency state on failure"),
        ("diverse-beam-real-corpus-win", False, ReleaseGateStatus.PENDING, (), "Keep Beam v2 if Diverse Beam has no matched real-corpus win"),
        ("end-to-end-blind-fidelity", True, ReleaseGateStatus.PENDING, (), "Fix the portfolio or planner on failure"),
        ("final-sha256sums", True, ReleaseGateStatus.PENDING, (), "Regenerate checksums from final release artifacts"),
        ("full-python-suite", True, ReleaseGateStatus.PASS, ("ci-python-matrix", "local-python-3.12-suite"), "Fix engineering defects on failure"),
        ("hard-invariant-accepted-violations-zero", True, ReleaseGateStatus.PENDING, (), "Block release on any accepted violation"),
        ("linux-package-e2e", True, ReleaseGateStatus.PASS, ("ci-python-matrix", "linux-artifact-install"), "Fix release packaging on failure"),
        ("macos-package-e2e", True, ReleaseGateStatus.PENDING, (), "Fix release portability on failure"),
        ("main-baseline-reproducible", True, ReleaseGateStatus.PASS, ("ci-python-matrix", "middev-full-matrix", "release-registry-snapshot"), "Return to baseline freeze on failure"),
        ("normalization-benchmark", True, ReleaseGateStatus.PENDING, (), "Do not justify a durable planner without this benchmark"),
        ("opportunity-serious-n-support", True, ReleaseGateStatus.PENDING, (), "Narrow claims or expand the independent corpus"),
        ("pristine-watermark-interpretability", True, ReleaseGateStatus.PENDING, (), "Drop unsupported regimes or block the claim"),
        ("project-license", True, ReleaseGateStatus.BLOCKED, ("license-audit",), "Owner must deliberately choose a compatible project license"),
        ("protected-invariant-violations-zero", True, ReleaseGateStatus.PENDING, (), "Block release on any violation"),
        ("public-v0.1.0-tag-release", True, ReleaseGateStatus.PENDING, (), "Release remains incomplete"),
        ("pyproject-license-metadata", True, ReleaseGateStatus.BLOCKED, ("license-audit", "package-metadata-audit"), "Add metadata only after the owner chooses the project license"),
        ("readme-release-claims-evidence-bounded", True, ReleaseGateStatus.PASS, ("geometry-v3-decision", "tinydev-context-survival", "tinydev-transformability"), "Rewrite documentation if claims exceed evidence"),
        ("release-engine-authorized-rules", True, ReleaseGateStatus.BLOCKED, ("public-cli-audit", "release-registry-snapshot"), "Qualify and version the actual public release engine"),
        ("survival-aware-scheduler-win", False, ReleaseGateStatus.PENDING, (), "Keep the accepted prior scheduler if no matched win exists"),
        ("transformed-control-drift", True, ReleaseGateStatus.PENDING, (), "Fix transformation or calibration on failure"),
        ("wheel-sdist-clean-install", True, ReleaseGateStatus.PASS, ("linux-artifact-install",), "Fix packaging on failure"),
        ("windows-package-e2e", True, ReleaseGateStatus.PENDING, (), "Fix release portability on failure"),
        ("durable-release-candidate-portfolio", True, ReleaseGateStatus.PENDING, (), "Return to durable transformation development"),
    )
    return tuple(sorted((ReleaseReadinessGate(*value) for value in rows), key=lambda value: value.gate_id))


def build_v010_release_readiness_baseline() -> ReleaseReadinessBaseline:
    identities = (
        ("baseline-invariant-screen", "context-survival-baseline-invariant-screen-v1"),
        ("candidate-scheduler", "candidate-scheduler-v2"),
        ("diverse-beam", "context-survival-diverse-beam-v1"),
        ("environment-snapshot", "environment-snapshot-v2"),
        ("hard-invariant", "hard-invariant-validator-v3"),
        ("historical-beam", "context-survival-beam-v2"),
        ("protected-span", "protected-span-extractor-v4"),
        ("surface-rules", "development-surface-rules-v4"),
        ("transform-apply", "explicit-candidate-apply-v4"),
        ("transform-registry", "transform-registry-v6"),
    )
    payload = {
        "algorithm_version": RELEASE_READINESS_BASELINE_ALGORITHM_VERSION,
        "project_version": "0.1.0",
        "baseline_commit": V010_BASELINE_COMMIT,
        "baseline_tree": V010_BASELINE_TREE,
        "python_versions": ("3.11", "3.12", "3.13"),
        "uv_lock_hash": V010_BASELINE_UV_LOCK_HASH,
        "spec_hash": V010_BASELINE_SPEC_HASH,
        "readme_hash": V010_BASELINE_README_HASH,
        "pyproject_hash": V010_BASELINE_PYPROJECT_HASH,
        "release_ruleset_hash": V010_RELEASE_RULESET_HASH,
        "release_rule_ids": V010_RELEASE_RULE_IDS,
        "algorithm_identities": identities,
        "evidence": _evidence(),
        "gates": _gates(),
    }
    return ReleaseReadinessBaseline(**payload, artifact_hash=sha256_json(payload))


def verify_v010_baseline_repository(root: Path) -> None:
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")
    if Path(_git_stdout(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise ValueError("repository-root must name the Git worktree root")
    if _git_stdout(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("baseline repository worktree is not clean")
    if _git_stdout(root, "rev-parse", "HEAD") != V010_BASELINE_COMMIT:
        raise ValueError("baseline repository commit drifted")
    if _git_stdout(root, "rev-parse", "HEAD^{tree}") != V010_BASELINE_TREE:
        raise ValueError("baseline repository tree drifted")
    expected_hashes = {
        "uv.lock": V010_BASELINE_UV_LOCK_HASH,
        "spec.md": V010_BASELINE_SPEC_HASH,
        "README.md": V010_BASELINE_README_HASH,
        "pyproject.toml": V010_BASELINE_PYPROJECT_HASH,
    }
    for relative, expected in expected_hashes.items():
        if sha256_file(root / relative) != expected:
            raise ValueError(f"baseline file drifted: {relative}")
    if any((root / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")):
        raise ValueError("baseline license-file absence no longer replays")
    with (root / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    if project.get("version") != "0.1.0" or "license" in project:
        raise ValueError("baseline package metadata no longer replays")


def _git_stdout(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(root), *args),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"baseline Git verification failed: {detail}")
    return completed.stdout.strip()


def _pairs(value: object, name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    output = []
    for row in value:
        if not isinstance(row, list) or len(row) != 2 or any(not isinstance(item, str) for item in row):
            raise TypeError(f"{name} must contain two-string lists")
        output.append((row[0], row[1]))
    return tuple(output)


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _require_keys(value: dict[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match the frozen schema")


def load_release_readiness_baseline(path: Path) -> ReleaseReadinessBaseline:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
    if not isinstance(value, dict):
        raise TypeError("release readiness artifact must be a JSON object")
    _require_keys(
        value,
        {
            "algorithm_version",
            "project_version",
            "baseline_commit",
            "baseline_tree",
            "python_versions",
            "uv_lock_hash",
            "spec_hash",
            "readme_hash",
            "pyproject_hash",
            "release_ruleset_hash",
            "release_rule_ids",
            "algorithm_identities",
            "evidence",
            "gates",
            "artifact_hash",
        },
        "release readiness artifact",
    )
    evidence_value = value.get("evidence")
    gates_value = value.get("gates")
    if not isinstance(evidence_value, list) or not isinstance(gates_value, list):
        raise TypeError("release readiness evidence and gates must be lists")
    for row in evidence_value:
        if not isinstance(row, dict):
            raise TypeError("release readiness evidence rows must be objects")
        _require_keys(row, {"evidence_id", "status", "reference", "result"}, "evidence row")
    for row in gates_value:
        if not isinstance(row, dict):
            raise TypeError("release readiness gate rows must be objects")
        _require_keys(row, {"gate_id", "required", "status", "evidence_ids", "consequence"}, "gate row")
    evidence = tuple(
        ReleaseReadinessEvidence(
            row["evidence_id"],
            ReleaseGateStatus(row["status"]),
            row["reference"],
            row["result"],
        )
        for row in evidence_value
    )
    gates = tuple(
        ReleaseReadinessGate(
            row["gate_id"],
            row["required"],
            ReleaseGateStatus(row["status"]),
            tuple(row["evidence_ids"]),
            row["consequence"],
        )
        for row in gates_value
    )
    return ReleaseReadinessBaseline(
        algorithm_version=value["algorithm_version"],
        project_version=value["project_version"],
        baseline_commit=value["baseline_commit"],
        baseline_tree=value["baseline_tree"],
        python_versions=tuple(value["python_versions"]),
        uv_lock_hash=value["uv_lock_hash"],
        spec_hash=value["spec_hash"],
        readme_hash=value["readme_hash"],
        pyproject_hash=value["pyproject_hash"],
        release_ruleset_hash=value["release_ruleset_hash"],
        release_rule_ids=tuple(value["release_rule_ids"]),
        algorithm_identities=_pairs(value["algorithm_identities"], "algorithm_identities"),
        evidence=evidence,
        gates=gates,
        artifact_hash=value["artifact_hash"],
    )


FROZEN_V010_RELEASE_READINESS_BASELINE = build_v010_release_readiness_baseline()
