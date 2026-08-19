from fuckmark.experiments.mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES
from fuckmark.experiments.mid_dev_v5_execution_contract import (
    MID_DEV_V5_LEGACY_ROW_COUNT,
    MID_DEV_V5_NORMALIZED_ROW_COUNT,
    MID_DEV_V5_NORMALIZED_ROWS_PER_SAMPLE,
    MID_DEV_V5_SAMPLE_COUNT,
    MID_DEV_V5_SOURCE_GROUP_COUNT,
    expected_normalized_keys,
)


def test_v5_execution_matrix_dimensions_are_frozen():
    assert MID_DEV_V5_LEGACY_ROW_COUNT == 5688
    assert MID_DEV_V5_SOURCE_GROUP_COUNT == 36
    assert MID_DEV_V5_SAMPLE_COUNT == 72
    assert MID_DEV_V5_NORMALIZED_ROWS_PER_SAMPLE == 34
    assert MID_DEV_V5_NORMALIZED_ROWS_PER_SAMPLE == 2 * (1 + MID_DEV_RANDOM_REPLICATES)
    assert MID_DEV_V5_NORMALIZED_ROW_COUNT == 2448


def test_each_sample_has_exact_beam_and_sixteen_random_cells_per_tier():
    keys = expected_normalized_keys("sample")
    assert len(keys) == 34
    assert len(set(keys)) == 34
    strict = [value for value in keys if value[2] == "STRICT"]
    relaxed = [value for value in keys if value[2] == "RELAXED"]
    assert len(strict) == 17
    assert len(relaxed) == 17
    assert sum(value[1] == "CONTEXT_SURVIVAL_BEAM_V2" for value in strict) == 1
    assert sum(value[1] == "CONTEXT_SURVIVAL_BEAM_V2" for value in relaxed) == 1
    assert sum(value[1] == "RANDOM_SAFE_MATCHED_COST" for value in strict) == 16
    assert sum(value[1] == "RANDOM_SAFE_MATCHED_COST" for value in relaxed) == 16
