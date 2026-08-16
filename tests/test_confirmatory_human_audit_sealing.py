from dataclasses import replace

from confirmatory_helpers import preregistration_inputs
from fuckmark.experiments.confirmatory import (
    CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION,
    create_confirmatory_preregistration,
)
from fuckmark.experiments.confirmatory_human_audit import ConfirmatoryHumanAuditPlan


def test_preregistration_seals_human_audit_plan_and_seed() -> None:
    inputs = preregistration_inputs()
    first = create_confirmatory_preregistration(inputs)
    changed_plan = ConfirmatoryHumanAuditPlan.create(
        inputs.human_audit_plan.target_sample_count,
        inputs.human_audit_plan.sampling_seed + 1,
    )
    second = create_confirmatory_preregistration(
        replace(inputs, human_audit_plan=changed_plan)
    )
    assert CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION == "confirmatory-preregistration-v3"
    assert first.human_audit_plan == inputs.human_audit_plan
    assert first.preregistration_hash != second.preregistration_hash
