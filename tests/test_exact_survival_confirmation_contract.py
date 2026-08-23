from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fuckmark.experiments.exact_survival_effectiveness_plan import (
    CONFIRMATION_SEED_BASES,
    EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT,
    EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH,
    INHERITED_THRESHOLD_VALUE,
    validate_exact_survival_confirmation_contract,
)
from fuckmark.tiny_dev_exact_survival_confirmation_aggregate import classify_confirmation


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "fuckmark-exact-survival-confirmation-v4.contract.json"


def _contract() -> dict[str, object]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _row(seed: int, pristine: int = 64, baseline_wm: int = 8, exact_wm: int = 5, baseline_control: int = 1, exact_control: int = 1):
    return {
        "confirmation_seed_base": seed,
        "pristine_watermarked_detected_count": pristine,
        "baseline_watermarked_detected_count": baseline_wm,
        "exact_watermarked_detected_count": exact_wm,
        "baseline_unwatermarked_detected_count": baseline_control,
        "exact_unwatermarked_detected_count": exact_control,
    }


def test_cycle4_contract_freezes_scheduler_threshold_and_new_seed_ledger() -> None:
    contract = _contract()
    contract_hash = validate_exact_survival_confirmation_contract(contract)
    assert len(contract_hash) == 64
    assert contract["candidate"]["scheduler_source_commit"] == EXACT_SURVIVAL_FROZEN_SOURCE_COMMIT
    assert contract["candidate"]["promotion_artifact_hash"] == EXACT_SURVIVAL_PROMOTION_ARTIFACT_HASH
    assert contract["measurement"]["threshold"] == INHERITED_THRESHOLD_VALUE
    assert tuple(contract["confirmation"]["seed_bases"]) == CONFIRMATION_SEED_BASES
    assert contract["confirmation"]["freeze_before_score"] is True
    assert contract["claim_boundary"]["release_authorized"] is False


def test_cycle4_contract_rejects_threshold_or_scheduler_drift() -> None:
    contract = _contract()
    changed = deepcopy(contract)
    changed["measurement"]["threshold"] = 0.5
    with pytest.raises(ValueError, match="threshold drifted"):
        validate_exact_survival_confirmation_contract(changed)
    changed = deepcopy(contract)
    changed["candidate"]["scheduler_source_commit"] = "0" * 40
    with pytest.raises(ValueError, match="scheduler source commit drifted"):
        validate_exact_survival_confirmation_contract(changed)


def test_confirmation_classification_is_preregistered_and_not_detector_tuned() -> None:
    rows = tuple(_row(seed) for seed in CONFIRMATION_SEED_BASES)
    assert classify_confirmation(rows) == "CONFIRMATORY_IMPROVEMENT"
    neutral = tuple(_row(seed, baseline_wm=5, exact_wm=5) for seed in CONFIRMATION_SEED_BASES)
    assert classify_confirmation(neutral) == "NEUTRAL"
    regression = tuple(_row(seed, baseline_wm=5, exact_wm=6) for seed in CONFIRMATION_SEED_BASES)
    assert classify_confirmation(regression) == "REGRESSION"
    invalid = list(rows)
    invalid[1] = _row(CONFIRMATION_SEED_BASES[1], pristine=59)
    assert classify_confirmation(tuple(invalid)) == "INVALID_CONTROL"
    partial = list(rows)
    partial[2] = _row(CONFIRMATION_SEED_BASES[2], baseline_wm=4, exact_wm=6)
    assert classify_confirmation(tuple(partial)) == "PARTIAL_IMPROVEMENT"
