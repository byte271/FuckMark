import pytest

from fuckmark.experiments.confirmatory_human_audit import (
    CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION,
    CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
    ConfirmatoryHumanAuditPlan,
)


def test_confirmatory_human_audit_plan_is_deterministic_and_seed_bound() -> None:
    first = ConfirmatoryHumanAuditPlan.create(200, 2718281828)
    second = ConfirmatoryHumanAuditPlan.create(200, 2718281828)
    changed = ConfirmatoryHumanAuditPlan.create(200, 2718281829)
    assert first == second
    assert first.plan_hash == second.plan_hash
    assert first.plan_hash != changed.plan_hash
    assert first.selection_algorithm_version == CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION
    assert first.blinding_algorithm_version == CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION


def test_confirmatory_human_audit_plan_rejects_nonpositive_sample_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        ConfirmatoryHumanAuditPlan.create(0, 1)
