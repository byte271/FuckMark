from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from .config import canonical_json_text
from .corpus import load_tiny_dev_corpus_by_version_json
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    validate_cycle6_confirmation_contract,
    validate_cycle6_confirmation_plan,
    validate_cycle6_frozen_source_blobs,
)
from .hashing import sha256_json


CYCLE6_FREEZE_CROSS_CHECK_VERSION = "cycle6-freeze-cross-check-v2"


def _require_lower_hex(name: str, value: object, *, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase {length}-character hexadecimal value")
    return value


def _require_mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be strings")
    return value


def _canonical_seed_hashes(name: str, values: Mapping[int, str]) -> dict[str, str]:
    expected = set(CYCLE6_CONFIRMATION_SEED_BASES)
    if set(values) != expected:
        raise ValueError(f"{name} must cover the three frozen Cycle 6 seed bases")
    return {
        str(seed): _require_lower_hex(f"{name}[{seed}]", values[seed], length=64)
        for seed in CYCLE6_CONFIRMATION_SEED_BASES
    }


def build_cycle6_freeze_cross_check(
    *,
    contract_hash: str,
    corpus_artifact_hashes: Mapping[int, str],
    plan_hashes: Mapping[int, str],
    frozen_source_code_commit: str,
    orchestration_code_commit: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": CYCLE6_FREEZE_CROSS_CHECK_VERSION,
        "contract_hash": _require_lower_hex("contract_hash", contract_hash, length=64),
        "seed_bases": list(CYCLE6_CONFIRMATION_SEED_BASES),
        "corpus_artifact_hashes": _canonical_seed_hashes(
            "corpus_artifact_hashes", corpus_artifact_hashes
        ),
        "plan_hashes": _canonical_seed_hashes("plan_hashes", plan_hashes),
        "frozen_source_code_commit": _require_lower_hex(
            "frozen_source_code_commit", frozen_source_code_commit, length=40
        ),
        "orchestration_code_commit": _require_lower_hex(
            "orchestration_code_commit", orchestration_code_commit, length=40
        ),
        "attack_rows_per_corpus": 128,
        "pairwise_attack_text_overlap": 0,
        "all_plans_frozen_before_scoring": True,
        "detector_access_used_for_selection": False,
        "secret_access_used_for_selection": False,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _load_json_mapping(path: Path, *, name: str) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _require_mapping(name, value)


def _validate_freeze_manifest(
    manifest: Mapping[str, object],
    *,
    seed: int,
    root: Path,
    corpus_artifact_hash: str,
    plan_hash: str,
    frozen_source_code_commit: str,
) -> None:
    if manifest.get("algorithm_version") != "cycle6-freeze-manifest-v1":
        raise ValueError(f"seed {seed}: unsupported freeze manifest version")
    if manifest.get("confirmation_seed_base") != seed:
        raise ValueError(f"seed {seed}: freeze manifest seed drifted")
    if manifest.get("source_code_commit") != frozen_source_code_commit:
        raise ValueError(f"seed {seed}: freeze manifest source commit drifted")
    if manifest.get("detector_scoring_performed") is not False:
        raise ValueError(f"seed {seed}: detector accessed before freeze")
    if manifest.get("secret_access_performed") is not False:
        raise ValueError(f"seed {seed}: secret accessed before freeze")

    manifest_payload = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    if manifest.get("manifest_hash") != sha256_json(manifest_payload):
        raise ValueError(f"seed {seed}: freeze manifest hash drifted")

    corpus_name = f"cycle6-corpus-{seed}.json"
    plan_name = f"cycle6-plan-{seed}.json"
    files = _require_mapping(f"seed {seed} manifest files", manifest.get("files"))
    if set(files) != {corpus_name, plan_name}:
        raise ValueError(f"seed {seed}: freeze manifest file set drifted")
    expected_bindings = {
        corpus_name: {"artifact_hash": corpus_artifact_hash, "plan_hash": None},
        plan_name: {"artifact_hash": None, "plan_hash": plan_hash},
    }
    for filename, expected in expected_bindings.items():
        record = _require_mapping(f"seed {seed} manifest record {filename}", files[filename])
        file_sha256 = _require_lower_hex(
            f"seed {seed} file_sha256 for {filename}", record.get("file_sha256"), length=64
        )
        if record.get("artifact_hash") != expected["artifact_hash"]:
            raise ValueError(f"seed {seed}: corpus artifact binding drifted for {filename}")
        if record.get("plan_hash") != expected["plan_hash"]:
            raise ValueError(f"seed {seed}: plan binding drifted for {filename}")
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != file_sha256:
            raise ValueError(f"seed {seed}: frozen file hash drifted: {filename}")


def cross_check_cycle6_frozen_artifacts(
    frozen_root: Path,
    repository_root: Path,
    contract: Mapping[str, object],
    *,
    frozen_source_code_commit: str,
    orchestration_code_commit: str,
) -> dict[str, object]:
    expected_frozen_commit = _require_lower_hex(
        "frozen_source_code_commit", frozen_source_code_commit, length=40
    )
    contract_hash = validate_cycle6_confirmation_contract(contract)
    validate_cycle6_frozen_source_blobs(repository_root, contract)
    attack_hashes: dict[int, set[str]] = {}
    corpus_hashes: dict[int, str] = {}
    plan_hashes: dict[int, str] = {}

    for seed in CYCLE6_CONFIRMATION_SEED_BASES:
        root = frozen_root / f"cycle6-freeze-{seed}"
        corpus_path = root / f"cycle6-corpus-{seed}.json"
        plan_path = root / f"cycle6-plan-{seed}.json"
        manifest_path = root / f"cycle6-freeze-manifest-{seed}.json"
        for path in (corpus_path, plan_path, manifest_path):
            if not path.is_file():
                raise FileNotFoundError(f"missing frozen file: {path}")

        corpus = load_tiny_dev_corpus_by_version_json(corpus_path)
        plan = _load_json_mapping(plan_path, name=f"seed {seed} plan")
        plan_hash = validate_cycle6_confirmation_plan(plan, corpus, contract=contract)
        if plan.get("source_code_commit") != expected_frozen_commit:
            raise ValueError(f"seed {seed}: plan source commit drifted")
        manifest = _load_json_mapping(manifest_path, name=f"seed {seed} freeze manifest")
        _validate_freeze_manifest(
            manifest,
            seed=seed,
            root=root,
            corpus_artifact_hash=corpus.artifact_hash,
            plan_hash=plan_hash,
            frozen_source_code_commit=expected_frozen_commit,
        )

        rows = plan["rows"]
        labels = {
            label: sum(row["source_label"] == label for row in rows)
            for label in ("watermarked", "unwatermarked")
        }
        if labels != {"watermarked": 64, "unwatermarked": 64}:
            raise ValueError(f"seed {seed}: attack label counts drifted: {labels}")
        hashes = {str(row["source_text_hash"]) for row in rows}
        if len(hashes) != 128:
            raise ValueError(f"seed {seed}: duplicate attack text hash")
        attack_hashes[seed] = hashes
        corpus_hashes[seed] = corpus.artifact_hash
        plan_hashes[seed] = plan_hash

    for index, left in enumerate(CYCLE6_CONFIRMATION_SEED_BASES):
        for right in CYCLE6_CONFIRMATION_SEED_BASES[index + 1 :]:
            overlap = attack_hashes[left] & attack_hashes[right]
            if overlap:
                raise ValueError(
                    f"attack text overlap between {left} and {right}: {len(overlap)}"
                )

    return build_cycle6_freeze_cross_check(
        contract_hash=contract_hash,
        corpus_artifact_hashes=corpus_hashes,
        plan_hashes=plan_hashes,
        frozen_source_code_commit=expected_frozen_commit,
        orchestration_code_commit=orchestration_code_commit,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-cycle6-freeze-cross-check")
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--frozen-source-code-commit", required=True)
    parser.add_argument("--orchestration-code-commit", required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--json", type=Path)
    output.add_argument("--expected-cross-check-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    contract = _load_json_mapping(args.contract_json, name="Cycle 6 contract")
    cross_check = cross_check_cycle6_frozen_artifacts(
        args.frozen_root,
        args.repository_root,
        contract,
        frozen_source_code_commit=args.frozen_source_code_commit,
        orchestration_code_commit=args.orchestration_code_commit,
    )
    if args.expected_cross_check_json is not None:
        expected_text = args.expected_cross_check_json.read_text(encoding="utf-8")
        expected = _require_mapping(
            "expected cross-check artifact", json.loads(expected_text)
        )
        if expected_text not in (canonical_json_text(expected), canonical_json_text(expected) + "\n"):
            raise ValueError("expected cross-check artifact is not canonical JSON")
        if canonical_json_text(expected) != canonical_json_text(cross_check):
            raise ValueError("frozen inputs do not reproduce the expected cross-check artifact")
    else:
        write_canonical_json_fsynced(args.json, cross_check)
    sys.stdout.write(f"artifact_hash={cross_check['artifact_hash']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
