from dataclasses import replace

import pytest

from confirmatory_helpers import preregistration_inputs
from fuckmark.experiments.confirmatory import (
    ConfirmatoryBootstrapPlan,
    ConfirmatoryFidelityGate,
    ConfirmatoryHypothesis,
    ConfirmatoryPrimaryOutcome,
    create_confirmatory_preregistration,
)
from fuckmark.transforms import build_task29_fidelity_readiness, development_syntax_rules
from fuckmark.types import SourcePin


def test_confirmatory_preregistration_freezes_core_matrix_without_generating_test_data() -> None:
    preregistration = create_confirmatory_preregistration(preregistration_inputs())
    assert preregistration.final_n_per_core_cell == 200
    assert preregistration.watermarked_base_sample_count == 8_000
    assert preregistration.matched_negative_base_sample_count == 8_000
    assert preregistration.task29_readiness.selection_frozen
    assert preregistration.task29_readiness.confirmatory_scale_ready
    assert preregistration.human_audit_plan.target_sample_count == 50
    assert preregistration.human_audit_plan.quartile_count == 4
    assert tuple(threshold.target_fpr for threshold in preregistration.calibration_bundles[0].thresholds) == (0.01,)


def test_final_n_is_power_analysis_driven_not_hardcoded_to_two_hundred() -> None:
    preregistration = create_confirmatory_preregistration(preregistration_inputs(final_n_per_core_cell=150))
    assert preregistration.watermarked_base_sample_count == 6_000


def test_unfrozen_task29_selection_blocks_preregistration() -> None:
    inputs = preregistration_inputs()
    forged = replace(inputs, task29_readiness=build_task29_fidelity_readiness())
    with pytest.raises(ValueError, match="selection must be frozen"):
        create_confirmatory_preregistration(forged)


def test_unselected_syntax_rule_cannot_be_smuggled_into_final_ruleset() -> None:
    inputs = preregistration_inputs()
    forged = replace(inputs, transform_rules=(*inputs.transform_rules, development_syntax_rules()[0]))
    with pytest.raises(ValueError, match="base contractions plus selected Task 29 rules"):
        create_confirmatory_preregistration(forged)


def test_confirmatory_preregistration_requires_two_distinct_model_tokenizer_families() -> None:
    inputs = preregistration_inputs()
    forged = replace(inputs, model_tokenizers=(inputs.model_tokenizers[0],))
    with pytest.raises(TypeError, match="at least two"):
        create_confirmatory_preregistration(forged)


def test_confirmatory_preregistration_requires_primary_one_percent_fpr() -> None:
    inputs = preregistration_inputs(target_fprs=(0.05,))
    with pytest.raises(ValueError, match="include the primary 1% FPR"):
        create_confirmatory_preregistration(inputs)


def test_duplicate_target_fprs_are_rejected_not_silently_deduplicated() -> None:
    inputs = preregistration_inputs()
    forged = replace(inputs, target_fprs=(0.01, 0.01))
    with pytest.raises(ValueError, match="unique and sorted"):
        create_confirmatory_preregistration(forged)


def test_duplicate_verification_hashes_are_rejected_not_silently_deduplicated() -> None:
    inputs = preregistration_inputs()
    value = inputs.verification_test_hashes[0]
    forged = replace(inputs, verification_test_hashes=(value, value))
    with pytest.raises(ValueError, match="unique and canonically ordered"):
        create_confirmatory_preregistration(forged)


def test_calibration_source_commit_must_match_frozen_source_pin() -> None:
    inputs = preregistration_inputs()
    original = inputs.source_pins[0]
    forged_pin = SourcePin(
        source_id=original.source_id,
        repository=original.repository,
        commit="0" * 40,
        license_id=original.license_id,
        critical_files=original.critical_files,
    )
    forged = replace(inputs, source_pins=(forged_pin, inputs.source_pins[1]))
    with pytest.raises(ValueError, match="adapter source is not frozen"):
        create_confirmatory_preregistration(forged)


def test_preregistration_rejects_unresolved_hypothesis_placeholders() -> None:
    with pytest.raises(ValueError, match="unresolved preregistration placeholder"):
        ConfirmatoryHypothesis.create(
            "H13-TODO",
            "TODO determine the confirmatory effect direction",
            ConfirmatoryPrimaryOutcome.TPR_CHANGE_AT_ONE_PERCENT_FPR,
        )


def test_confirmatory_bootstrap_and_fidelity_gates_cannot_be_weakened() -> None:
    with pytest.raises(ValueError, match="10,000"):
        ConfirmatoryBootstrapPlan.create(replicates=9_999)
    with pytest.raises(ValueError, match="95%"):
        ConfirmatoryFidelityGate.create(minimum_equivalent_or_minor_rate=0.94)
    with pytest.raises(ValueError, match="zero hard-invariant"):
        ConfirmatoryFidelityGate.create(maximum_hard_invariant_violations=1)
