from __future__ import annotations

from fuckmark.config import canonical_json_bytes
from fuckmark.experiments.cycle6_confirmation import CYCLE6_CONFIRMATION_SEED_BASES
from fuckmark.hashing import sha256_json
from fuckmark.tiny_dev_cycle6_recovery_manifest import build_cycle6_recovery_manifest


def _hashes(kind: str) -> dict[int, str]:
    return {
        seed: sha256_json({"kind": kind, "confirmation_seed_base": seed})
        for seed in CYCLE6_CONFIRMATION_SEED_BASES
    }


def _build() -> dict[str, object]:
    return build_cycle6_recovery_manifest(
        source_workflow_run_id=32_873_260_399,
        recovery_workflow_run_id=40_000_000_000,
        source_artifacts={
            seed: {"artifact_id": seed, "artifact_digest": sha256_json({"seed": seed})}
            for seed in CYCLE6_CONFIRMATION_SEED_BASES
        },
        frozen_source_code_commit="a" * 40,
        orchestration_code_commit="b" * 40,
        contract_hash=sha256_json({"contract": "cycle6-v2"}),
        cross_check_artifact_hash=sha256_json({"cross-check": "cycle6-v2"}),
        score_artifact_hashes=_hashes("score"),
        score_provenance_hashes=_hashes("provenance"),
        aggregate_artifact_hash=sha256_json({"aggregate": "cycle6-v2"}),
        formal_outcome="ZERO_RESIDUAL",
    )


def test_cycle6_recovery_manifest_uses_canonical_seed_keys_and_separates_commits() -> None:
    manifest = _build()

    assert tuple(manifest["source_artifacts"]) == ("760000", "770000", "780000")
    assert tuple(manifest["score_artifact_hashes"]) == ("760000", "770000", "780000")
    assert manifest["scientific_source_code_commit"] == "a" * 40
    assert manifest["orchestration_code_commit"] == "b" * 40
    assert manifest["scientific_artifacts_changed_by_recovery"] is False
    assert manifest["human_fidelity_claim_authorized"] is False


def test_cycle6_recovery_manifest_is_byte_stable() -> None:
    first = _build()
    second = _build()

    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
