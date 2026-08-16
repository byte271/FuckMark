import pytest

from fuckmark.experiments.confirmatory_human_audit import (
    CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION,
    CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR,
    CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT,
    CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION,
    ConfirmatoryHumanAuditPlan,
)


def test_confirmatory_human_audit_plan_is_deterministic_and_seed_bound() -> None:
    first = ConfirmatoryHumanAuditPlan.create(50, 2718281828)
    second = ConfirmatoryHumanAuditPlan.create(50, 2718281828)
    changed = ConfirmatoryHumanAuditPlan.create(50, 2718281829)
    assert first == second
    assert first.plan_hash == second.plan_hash
    assert first.plan_hash != changed.plan_hash
    assert first.selection_algorithm_version == CONFIRMATORY_HUMAN_AUDIT_SELECTION_ALGORITHM_VERSION
    assert first.blinding_algorithm_version == CONFIRMATORY_HUMAN_AUDIT_BLINDING_ALGORITHM_VERSION
    assert first.quartile_count == CONFIRMATORY_HUMAN_AUDIT_QUARTILE_COUNT
    assert first.degradation_target_fpr == CONFIRMATORY_HUMAN_AUDIT_DEGRADATION_TARGET_FPR


def test_confirmatory_human_audit_plan_rejects_nonpositive_sample_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        ConfirmatoryHumanAuditPlan.create(0, 1)


def test_confirmatory_human_audit_plan_rejects_less_than_fifty_per_feasible_cell() -> None:
    with pytest.raises(ValueError, match="at least 50"):
        ConfirmatoryHumanAuditPlan.create(49, 1)
