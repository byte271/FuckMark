from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from fuckmark.experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    aggregate_cycle6_confirmation,
    validate_cycle6_confirmation_contract,
)
from fuckmark.tiny_dev_cycle6_confirmation_score_hf import _require_scoring_authorization
from tools.build_cycle6_full_fidelity_packet import _validate_output_isolation


_HELPERS = runpy.run_path(
    str(Path(__file__).with_name("test_cycle6_confirmation_contract.py"))
)
_contract = _HELPERS["_contract"]
_evidence = _HELPERS["_evidence"]


def test_cycle6_scorer_rejects_pending_fidelity_contract() -> None:
    contract = _contract()
    validate_cycle6_confirmation_contract(contract)
    with pytest.raises(ValueError, match="independent fidelity review"):
        _require_scoring_authorization(contract)

    contract["fidelity_gate"]["status"] = "ACCEPTED_INDEPENDENT_HUMAN_REVIEW"
    contract["fidelity_gate"]["independent_audit_hash"] = "a" * 64
    contract["confirmation"]["scoring_authorized"] = True
    validate_cycle6_confirmation_contract(contract)
    _require_scoring_authorization(contract)


def test_cycle6_aggregate_accepts_canonical_json_roundtrip() -> None:
    contract = _contract()
    contract_hash = validate_cycle6_confirmation_contract(contract)
    evidence = tuple(
        _evidence(seed, contract_hash) for seed in CYCLE6_CONFIRMATION_SEED_BASES
    )
    reloaded = json.loads(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    aggregate = aggregate_cycle6_confirmation(reloaded, contract=contract)
    assert aggregate["outcome"] == "ZERO_RESIDUAL"
    assert aggregate["pooled"]["watermarked_detected_per_sanitizer"] == (0, 0, 0, 0)


def test_cycle6_accepted_fidelity_requires_all_lowercase_hex_hashes() -> None:
    contract = _contract()
    contract["fidelity_gate"]["status"] = "ACCEPTED_INDEPENDENT_HUMAN_REVIEW"
    contract["fidelity_gate"]["independent_audit_hash"] = "a" * 64
    contract["confirmation"]["scoring_authorized"] = True
    validate_cycle6_confirmation_contract(contract)

    contract["fidelity_gate"]["mechanical_artifact_hash"] = "A" * 64
    with pytest.raises(ValueError, match="mechanical_artifact_hash"):
        validate_cycle6_confirmation_contract(contract)


def test_cycle6_private_orientation_output_requires_separate_directory(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public" / "packet.json"
    mechanical = tmp_path / "public" / "mechanical.json"
    private = tmp_path / "private" / "orientation.json"
    _validate_output_isolation(public, private, mechanical)

    with pytest.raises(ValueError, match="private orientation output"):
        _validate_output_isolation(
            public,
            tmp_path / "public" / "orientation.json",
            mechanical,
        )
