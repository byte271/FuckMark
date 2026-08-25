from __future__ import annotations

import json
from pathlib import Path

import pytest

from fuckmark.experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    CYCLE6_EFFECTIVENESS_CONTRACT_VERSION,
    CYCLE6_THRESHOLD,
    validate_cycle6_confirmation_contract,
    validate_cycle6_frozen_source_blobs,
)
from fuckmark.tiny_dev_cycle6_confirmation_score_hf import _require_scoring_authorization


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "specs" / "fuckmark-cycle6-confirmation-v2.contract.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_cycle6_v2_preregisters_effectiveness_without_human_gate() -> None:
    contract = _contract()
    digest = validate_cycle6_confirmation_contract(contract)
    assert len(digest) == 64
    assert contract["algorithm_version"] == CYCLE6_EFFECTIVENESS_CONTRACT_VERSION
    assert contract["status"] == "PREREGISTERED_UNSCORED_EFFECTIVENESS"
    assert tuple(contract["confirmation"]["seed_bases"]) == CYCLE6_CONFIRMATION_SEED_BASES
    assert contract["confirmation"]["scoring_authorized"] is True
    assert contract["measurement"]["threshold"] == CYCLE6_THRESHOLD
    assert contract["attack"]["budget"] == 14
    assert contract["protocol_change"]["prior_formal_detector_scoring_performed"] is False
    assert contract["effectiveness_authorization"]["human_fidelity_required_for_effectiveness"] is False
    assert contract["fidelity_endpoint"]["status"] == "SECONDARY_NOT_GATING"
    assert contract["fidelity_endpoint"]["human_review_completed"] is False
    assert contract["fidelity_endpoint"]["independent_audit_hash"] is None
    assert contract["claim_boundary"]["human_fidelity_claim"] is False
    assert validate_cycle6_frozen_source_blobs(ROOT, contract)
    _require_scoring_authorization(contract)


def test_cycle6_v2_rejects_post_score_protocol_adoption() -> None:
    contract = _contract()
    contract["protocol_change"]["prior_formal_detector_scoring_performed"] = True
    with pytest.raises(ValueError, match="after formal detector scoring"):
        validate_cycle6_confirmation_contract(contract)


def test_cycle6_v2_rejects_human_gate_reintroduction_or_fidelity_claim() -> None:
    contract = _contract()
    contract["effectiveness_authorization"]["human_fidelity_required_for_effectiveness"] = True
    with pytest.raises(ValueError, match="secondary, not gating"):
        validate_cycle6_confirmation_contract(contract)

    contract = _contract()
    contract["fidelity_endpoint"]["human_fidelity_claim_authorized"] = True
    with pytest.raises(ValueError, match="cannot claim human fidelity"):
        validate_cycle6_confirmation_contract(contract)


def test_cycle6_v2_keeps_attack_and_measurement_frozen() -> None:
    contract = _contract()
    contract["attack"]["budget"] = 15
    with pytest.raises(ValueError, match="budget or n-gram"):
        validate_cycle6_confirmation_contract(contract)

    contract = _contract()
    contract["measurement"]["threshold"] = 0.5
    with pytest.raises(ValueError, match="threshold identity"):
        validate_cycle6_confirmation_contract(contract)
