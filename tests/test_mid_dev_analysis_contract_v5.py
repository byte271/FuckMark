import pytest

from fuckmark.experiments.mid_dev_analysis_contract_v5 import (
    FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT,
    MID_DEV_V5_ALLOW_CONFIRMATORY_P_VALUES,
    MID_DEV_V5_MATCHED_COMPARISONS,
    MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES,
    legacy_primary_cell_ids,
    source_level_bootstrap_mean,
    validate_usable_random_replicates,
)
from fuckmark.experiments.mid_dev_pre_run_lock import (
    PRE_RUN_BOOTSTRAP_REPLICATES,
    PRE_RUN_BOOTSTRAP_SEED_BASE,
    PRE_RUN_NORMALIZED_PRIMARY_CELLS,
)


def test_v5_analysis_contract_freezes_source_group_unit_and_all_primary_cells():
    contract = FROZEN_MID_DEV_V5_ANALYSIS_CONTRACT
    assert contract.independent_unit == "SOURCE_GROUP"
    assert contract.planned_source_group_count == 36
    assert contract.minimum_eligible_source_groups == 32
    assert contract.random_replicates_per_source == 16
    assert contract.minimum_usable_random_replicates == 8
    assert contract.bootstrap_replicates == 10_000
    assert contract.bootstrap_seed_base == PRE_RUN_BOOTSTRAP_SEED_BASE
    assert len(legacy_primary_cell_ids()) == 6
    assert contract.normalized_primary_cell_ids == PRE_RUN_NORMALIZED_PRIMARY_CELLS
    assert contract.matched_comparison_ids == MID_DEV_V5_MATCHED_COMPARISONS
    assert contract.allow_confirmatory_p_values is MID_DEV_V5_ALLOW_CONFIRMATORY_P_VALUES is False


def test_random_replicate_gate_is_frozen_to_at_least_eight_of_sixteen():
    validate_usable_random_replicates(8)
    validate_usable_random_replicates(16)
    with pytest.raises(ValueError, match="at least eight"):
        validate_usable_random_replicates(7)
    with pytest.raises(ValueError, match="exceeds"):
        validate_usable_random_replicates(17)


def test_source_level_bootstrap_is_deterministic_and_requires_32_groups():
    values = tuple(index / 100.0 for index in range(32))
    first = source_level_bootstrap_mean(values, seed=PRE_RUN_BOOTSTRAP_SEED_BASE)
    second = source_level_bootstrap_mean(values, seed=PRE_RUN_BOOTSTRAP_SEED_BASE)
    assert first == second
    assert first[1] <= first[0] <= first[2]
    with pytest.raises(ValueError, match="at least 32"):
        source_level_bootstrap_mean(values[:31], seed=PRE_RUN_BOOTSTRAP_SEED_BASE)
    with pytest.raises(ValueError, match="10,000"):
        source_level_bootstrap_mean(values, seed=PRE_RUN_BOOTSTRAP_SEED_BASE, replicates=9999)


def test_bootstrap_contract_is_exactly_10000_replicates():
    assert PRE_RUN_BOOTSTRAP_REPLICATES == 10_000
    assert MID_DEV_V5_MINIMUM_USABLE_RANDOM_REPLICATES == 8
