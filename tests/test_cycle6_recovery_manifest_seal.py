from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path

import pytest

from fuckmark.experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    aggregate_cycle6_confirmation,
    validate_cycle6_confirmation_contract,
)
from fuckmark.config import canonical_json_text
from fuckmark.durable_io import write_canonical_json_fsynced
from fuckmark.hashing import sha256_json
from fuckmark.tiny_dev_cycle6_freeze_cross_check import (
    build_cycle6_freeze_cross_check,
)
from fuckmark.tiny_dev_cycle6_recovery_manifest import (
    _load_canonical_mapping,
    main as seal_main,
    seal_cycle6_recovery_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "specs" / "fuckmark-cycle6-confirmation-v2.contract.json"
FROZEN_COMMIT = "a" * 40
ORCHESTRATION_COMMIT = "b" * 40
RECOVERY_RUN_ID = 40_000_000_000
_CONTRACT_HELPERS = runpy.run_path(
    str(Path(__file__).with_name("test_cycle6_confirmation_contract.py"))
)


def _chain() -> tuple[
    dict[str, object],
    dict[str, object],
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
    dict[str, object],
]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_hash = validate_cycle6_confirmation_contract(contract)
    evidence = tuple(
        _CONTRACT_HELPERS["_evidence"](seed, contract_hash)
        for seed in CYCLE6_CONFIRMATION_SEED_BASES
    )
    cross_check = build_cycle6_freeze_cross_check(
        contract_hash=contract_hash,
        corpus_artifact_hashes={
            seed: str(item["tiny_dev_artifact_hash"])
            for seed, item in zip(CYCLE6_CONFIRMATION_SEED_BASES, evidence, strict=True)
        },
        plan_hashes={
            seed: str(item["plan_hash"])
            for seed, item in zip(CYCLE6_CONFIRMATION_SEED_BASES, evidence, strict=True)
        },
        frozen_source_code_commit=FROZEN_COMMIT,
        orchestration_code_commit=ORCHESTRATION_COMMIT,
    )
    provenance = []
    for item in evidence:
        payload = {
            "algorithm_version": "cycle6-confirmation-score-provenance-v1",
            "source_code_commit": FROZEN_COMMIT,
            "contract_hash": contract_hash,
            "plan_hash": item["plan_hash"],
            "artifact_hash": item["artifact_hash"],
            "scoring_started_at_utc": "2026-08-25T12:00:00Z",
            "scoring_fsynced_at_utc": "2026-08-25T12:01:00Z",
            "scoring_fsync_success": True,
            "github_run_id": str(RECOVERY_RUN_ID),
            "github_run_attempt": "1",
            "github_event_name": "workflow_dispatch",
            "github_checkout_sha": ORCHESTRATION_COMMIT,
        }
        provenance.append({**payload, "provenance_hash": sha256_json(payload)})
    aggregate = aggregate_cycle6_confirmation(evidence, contract=contract)
    return contract, cross_check, evidence, tuple(provenance), aggregate


def _seal(provenance: tuple[dict[str, object], ...]) -> dict[str, object]:
    contract, cross_check, evidence, _, aggregate = _chain()
    return seal_cycle6_recovery_manifest(
        contract=contract,
        cross_check=cross_check,
        evidence=evidence,
        provenance=provenance,
        aggregate=aggregate,
        source_workflow_run_id=32_873_260_399,
        recovery_workflow_run_id=RECOVERY_RUN_ID,
        source_artifacts={
            seed: {
                "artifact_id": seed,
                "artifact_digest": sha256_json({"seed": seed}),
            }
            for seed in CYCLE6_CONFIRMATION_SEED_BASES
        },
        frozen_source_code_commit=FROZEN_COMMIT,
        orchestration_code_commit=ORCHESTRATION_COMMIT,
    )


def test_seal_validates_the_complete_recovered_chain() -> None:
    _, _, _, provenance, aggregate = _chain()

    manifest = _seal(provenance)

    assert manifest["formal_outcome"] == aggregate["outcome"] == "ZERO_RESIDUAL"
    assert manifest["scientific_source_code_commit"] == FROZEN_COMMIT
    assert manifest["orchestration_code_commit"] == ORCHESTRATION_COMMIT
    assert manifest["scientific_artifacts_changed_by_recovery"] is False


def test_seal_rejects_rehashed_provenance_from_another_orchestration_commit() -> None:
    _, _, _, provenance, _ = _chain()
    tampered = copy.deepcopy(provenance)
    tampered[0]["github_checkout_sha"] = "c" * 40
    payload = {key: value for key, value in tampered[0].items() if key != "provenance_hash"}
    tampered[0]["provenance_hash"] = sha256_json(payload)

    with pytest.raises(ValueError, match="orchestration provenance drifted"):
        _seal(tuple(tampered))


def test_pretty_printed_v2_contract_is_rejected_as_canonical_artifact() -> None:
    with pytest.raises(ValueError, match="is not canonical JSON"):
        _load_canonical_mapping(CONTRACT_PATH, name="Cycle 6 contract")


def test_seal_cli_accepts_the_pretty_printed_v2_contract(tmp_path: Path) -> None:
    contract, cross_check, evidence, provenance, aggregate = _chain()
    assert canonical_json_text(contract) != CONTRACT_PATH.read_text(encoding="utf-8").rstrip("\n")

    cross_check_path = tmp_path / "cross-check.json"
    aggregate_path = tmp_path / "aggregate.json"
    output = tmp_path / "recovery-manifest.json"
    write_canonical_json_fsynced(cross_check_path, cross_check)
    write_canonical_json_fsynced(aggregate_path, aggregate)
    evidence_args: list[str] = []
    provenance_args: list[str] = []
    source_args: list[str] = []
    for seed, item, provenance_item in zip(
        CYCLE6_CONFIRMATION_SEED_BASES, evidence, provenance, strict=True
    ):
        evidence_path = tmp_path / f"evidence-{seed}.json"
        provenance_path = tmp_path / f"provenance-{seed}.json"
        write_canonical_json_fsynced(evidence_path, item)
        write_canonical_json_fsynced(provenance_path, provenance_item)
        evidence_args.extend(["--evidence-json", str(evidence_path)])
        provenance_args.extend(["--provenance-json", str(provenance_path)])
        source_args.extend(
            ["--source-artifact", f"{seed}:{seed}:{sha256_json({'seed': seed})}"]
        )

    argv = [
        "--contract-json",
        str(CONTRACT_PATH),
        "--cross-check-json",
        str(cross_check_path),
        *evidence_args,
        *provenance_args,
        "--aggregate-json",
        str(aggregate_path),
        "--source-workflow-run-id",
        "32873260399",
        "--recovery-workflow-run-id",
        str(RECOVERY_RUN_ID),
        *source_args,
        "--frozen-source-code-commit",
        FROZEN_COMMIT,
        "--orchestration-code-commit",
        ORCHESTRATION_COMMIT,
        "--json",
        str(output),
    ]

    assert seal_main(argv) == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["formal_outcome"] == "ZERO_RESIDUAL"
    assert manifest["scientific_source_code_commit"] == FROZEN_COMMIT
