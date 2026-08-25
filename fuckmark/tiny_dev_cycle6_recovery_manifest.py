from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .config import canonical_json_text
from .durable_io import write_canonical_json_fsynced
from .experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    aggregate_cycle6_confirmation,
    validate_cycle6_confirmation_contract,
)
from .hashing import sha256_json
from .tiny_dev_cycle6_freeze_cross_check import CYCLE6_FREEZE_CROSS_CHECK_VERSION


CYCLE6_RECOVERY_MANIFEST_VERSION = "cycle6-frozen-artifact-recovery-manifest-v1"


def _require_lower_hex(name: str, value: object, *, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase {length}-character hexadecimal value")
    return value


def _load_canonical_mapping(path: Path, *, name: str) -> Mapping[str, object]:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} must be a string-keyed mapping")
    canonical = canonical_json_text(value)
    if text not in (canonical, canonical + "\n"):
        raise ValueError(f"{name} is not canonical JSON")
    return value


def _validate_hashed_artifact(name: str, artifact: Mapping[str, object]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    expected = sha256_json(payload)
    if artifact.get("artifact_hash") != expected:
        raise ValueError(f"{name} artifact hash drifted")
    return expected


def build_cycle6_recovery_manifest(
    *,
    source_workflow_run_id: int,
    recovery_workflow_run_id: int,
    source_artifacts: Mapping[int, Mapping[str, object]],
    frozen_source_code_commit: str,
    orchestration_code_commit: str,
    contract_hash: str,
    cross_check_artifact_hash: str,
    score_artifact_hashes: Mapping[int, str],
    score_provenance_hashes: Mapping[int, str],
    aggregate_artifact_hash: str,
    formal_outcome: str,
) -> dict[str, object]:
    expected_seeds = set(CYCLE6_CONFIRMATION_SEED_BASES)
    if set(source_artifacts) != expected_seeds:
        raise ValueError("source_artifacts must cover the three frozen Cycle 6 seed bases")
    if set(score_artifact_hashes) != expected_seeds:
        raise ValueError("score_artifact_hashes must cover the three frozen Cycle 6 seed bases")
    if set(score_provenance_hashes) != expected_seeds:
        raise ValueError("score_provenance_hashes must cover the three frozen Cycle 6 seed bases")
    if formal_outcome not in {"ZERO_RESIDUAL", "NONZERO_RESIDUAL", "INVALID_CONTROL"}:
        raise ValueError("formal_outcome is not authorized by the Cycle 6 contract")

    canonical_sources: dict[str, object] = {}
    for seed in CYCLE6_CONFIRMATION_SEED_BASES:
        record = source_artifacts[seed]
        artifact_id = record.get("artifact_id")
        if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
            raise ValueError(f"source artifact ID for seed {seed} is invalid")
        canonical_sources[str(seed)] = {
            "artifact_id": artifact_id,
            "artifact_name": f"cycle6-freeze-{seed}",
            "artifact_digest": "sha256:"
            + _require_lower_hex(
                f"source artifact digest for seed {seed}",
                str(record.get("artifact_digest", "")).removeprefix("sha256:"),
                length=64,
            ),
        }

    payload = {
        "algorithm_version": CYCLE6_RECOVERY_MANIFEST_VERSION,
        "recovered_from_workflow_run_id": source_workflow_run_id,
        "recovery_workflow_run_id": recovery_workflow_run_id,
        "source_artifacts": canonical_sources,
        "scientific_source_code_commit": _require_lower_hex(
            "frozen_source_code_commit", frozen_source_code_commit, length=40
        ),
        "orchestration_code_commit": _require_lower_hex(
            "orchestration_code_commit", orchestration_code_commit, length=40
        ),
        "contract_hash": _require_lower_hex("contract_hash", contract_hash, length=64),
        "cross_check_artifact_hash": _require_lower_hex(
            "cross_check_artifact_hash", cross_check_artifact_hash, length=64
        ),
        "score_artifact_hashes": {
            str(seed): _require_lower_hex(
                f"score_artifact_hashes[{seed}]", score_artifact_hashes[seed], length=64
            )
            for seed in CYCLE6_CONFIRMATION_SEED_BASES
        },
        "score_provenance_hashes": {
            str(seed): _require_lower_hex(
                f"score_provenance_hashes[{seed}]",
                score_provenance_hashes[seed],
                length=64,
            )
            for seed in CYCLE6_CONFIRMATION_SEED_BASES
        },
        "aggregate_artifact_hash": _require_lower_hex(
            "aggregate_artifact_hash", aggregate_artifact_hash, length=64
        ),
        "formal_outcome": formal_outcome,
        "scientific_artifacts_changed_by_recovery": False,
        "human_fidelity_claim_authorized": False,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def seal_cycle6_recovery_manifest(
    *,
    contract: Mapping[str, object],
    cross_check: Mapping[str, object],
    evidence: Sequence[Mapping[str, object]],
    provenance: Sequence[Mapping[str, object]],
    aggregate: Mapping[str, object],
    source_workflow_run_id: int,
    recovery_workflow_run_id: int,
    source_artifacts: Mapping[int, Mapping[str, object]],
    frozen_source_code_commit: str,
    orchestration_code_commit: str,
) -> dict[str, object]:
    contract_hash = validate_cycle6_confirmation_contract(contract)
    cross_check_hash = _validate_hashed_artifact("cross-check", cross_check)
    if cross_check.get("algorithm_version") != CYCLE6_FREEZE_CROSS_CHECK_VERSION:
        raise ValueError("unsupported Cycle 6 recovery cross-check version")
    if cross_check.get("contract_hash") != contract_hash:
        raise ValueError("recovery cross-check contract binding drifted")
    if cross_check.get("frozen_source_code_commit") != frozen_source_code_commit:
        raise ValueError("recovery cross-check frozen source commit drifted")
    if cross_check.get("orchestration_code_commit") != orchestration_code_commit:
        raise ValueError("recovery cross-check orchestration commit drifted")

    recomputed_aggregate = aggregate_cycle6_confirmation(evidence, contract=contract)
    if canonical_json_text(aggregate) != canonical_json_text(recomputed_aggregate):
        raise ValueError("recovered evidence does not reproduce the aggregate artifact")
    aggregate_hash = _validate_hashed_artifact("aggregate", aggregate)

    evidence_by_seed = {int(item["confirmation_seed_base"]): item for item in evidence}
    provenance_by_seed: dict[int, Mapping[str, object]] = {}
    for item in provenance:
        plan_hash = str(item.get("plan_hash"))
        matches = [
            seed
            for seed, scored in evidence_by_seed.items()
            if scored.get("plan_hash") == plan_hash
        ]
        if len(matches) != 1:
            raise ValueError("score provenance does not bind exactly one recovered seed")
        provenance_by_seed[matches[0]] = item
    if set(evidence_by_seed) != set(CYCLE6_CONFIRMATION_SEED_BASES):
        raise ValueError("recovered evidence seed set drifted")
    if set(provenance_by_seed) != set(CYCLE6_CONFIRMATION_SEED_BASES):
        raise ValueError("recovered provenance seed set drifted")

    corpus_hashes = cross_check.get("corpus_artifact_hashes")
    plan_hashes = cross_check.get("plan_hashes")
    if not isinstance(corpus_hashes, Mapping) or not isinstance(plan_hashes, Mapping):
        raise TypeError("cross-check corpus and plan hashes must be mappings")
    score_hashes: dict[int, str] = {}
    provenance_hashes: dict[int, str] = {}
    for seed in CYCLE6_CONFIRMATION_SEED_BASES:
        scored = evidence_by_seed[seed]
        score_hash = _validate_hashed_artifact(f"seed {seed} evidence", scored)
        if scored.get("tiny_dev_artifact_hash") != corpus_hashes.get(str(seed)):
            raise ValueError(f"seed {seed} recovered corpus binding drifted")
        if scored.get("plan_hash") != plan_hashes.get(str(seed)):
            raise ValueError(f"seed {seed} recovered plan binding drifted")
        item = provenance_by_seed[seed]
        provenance_payload = {
            key: value for key, value in item.items() if key != "provenance_hash"
        }
        provenance_hash = sha256_json(provenance_payload)
        if item.get("provenance_hash") != provenance_hash:
            raise ValueError(f"seed {seed} score provenance hash drifted")
        if item.get("source_code_commit") != frozen_source_code_commit:
            raise ValueError(f"seed {seed} scientific source provenance drifted")
        if item.get("github_checkout_sha") != orchestration_code_commit:
            raise ValueError(f"seed {seed} orchestration provenance drifted")
        if str(item.get("github_run_id")) != str(recovery_workflow_run_id):
            raise ValueError(f"seed {seed} recovery run provenance drifted")
        if item.get("contract_hash") != contract_hash:
            raise ValueError(f"seed {seed} provenance contract binding drifted")
        if item.get("artifact_hash") != score_hash:
            raise ValueError(f"seed {seed} provenance evidence binding drifted")
        score_hashes[seed] = score_hash
        provenance_hashes[seed] = provenance_hash

    return build_cycle6_recovery_manifest(
        source_workflow_run_id=source_workflow_run_id,
        recovery_workflow_run_id=recovery_workflow_run_id,
        source_artifacts=source_artifacts,
        frozen_source_code_commit=frozen_source_code_commit,
        orchestration_code_commit=orchestration_code_commit,
        contract_hash=contract_hash,
        cross_check_artifact_hash=cross_check_hash,
        score_artifact_hashes=score_hashes,
        score_provenance_hashes=provenance_hashes,
        aggregate_artifact_hash=aggregate_hash,
        formal_outcome=str(aggregate["outcome"]),
    )


def _source_artifact(value: str) -> tuple[int, Mapping[str, object]]:
    try:
        seed_text, artifact_id_text, digest = value.split(":", 2)
        seed = int(seed_text)
        artifact_id = int(artifact_id_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "source artifact must be SEED:ARTIFACT_ID:SHA256_DIGEST"
        ) from error
    return seed, {"artifact_id": artifact_id, "artifact_digest": digest}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-cycle6-recovery-manifest")
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--cross-check-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, action="append", required=True)
    parser.add_argument("--provenance-json", type=Path, action="append", required=True)
    parser.add_argument("--aggregate-json", type=Path, required=True)
    parser.add_argument("--source-workflow-run-id", type=int, required=True)
    parser.add_argument("--recovery-workflow-run-id", type=int, required=True)
    parser.add_argument("--source-artifact", type=_source_artifact, action="append", required=True)
    parser.add_argument("--frozen-source-code-commit", required=True)
    parser.add_argument("--orchestration-code-commit", required=True)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = seal_cycle6_recovery_manifest(
        contract=_load_canonical_mapping(args.contract_json, name="Cycle 6 contract"),
        cross_check=_load_canonical_mapping(args.cross_check_json, name="cross-check artifact"),
        evidence=tuple(
            _load_canonical_mapping(path, name=f"score evidence {path}")
            for path in args.evidence_json
        ),
        provenance=tuple(
            _load_canonical_mapping(path, name=f"score provenance {path}")
            for path in args.provenance_json
        ),
        aggregate=_load_canonical_mapping(args.aggregate_json, name="aggregate artifact"),
        source_workflow_run_id=args.source_workflow_run_id,
        recovery_workflow_run_id=args.recovery_workflow_run_id,
        source_artifacts=dict(args.source_artifact),
        frozen_source_code_commit=args.frozen_source_code_commit,
        orchestration_code_commit=args.orchestration_code_commit,
    )
    write_canonical_json_fsynced(args.json, manifest)
    sys.stdout.write(
        f"outcome={manifest['formal_outcome']} artifact_hash={manifest['artifact_hash']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
