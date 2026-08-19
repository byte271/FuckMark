from pathlib import Path

from fuckmark.experiments.mid_dev_calibration_readiness import FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN


def test_frozen_readiness_shard_ids_cover_exact_250_ranges():
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    for plan in (readiness.select_plan, readiness.audit_plan):
        assert len(plan.shards) == 16
        for shard in plan.shards:
            assert shard.end_index_exclusive - shard.start_index == 250
            assert len(shard.prompt_ids) == 250
            assert len(shard.seeds) == 250
            assert tuple(range(shard.start_index, shard.end_index_exclusive)) == tuple(
                range(shard.start_index, shard.end_index_exclusive)
            )


def test_shard_generator_has_no_user_control_over_seed_or_range_or_count():
    source = Path("fuckmark/mid_dev_calibration_shard_hf.py").read_text(encoding="utf-8").lower()
    assert "--shard-id" in source
    assert "--role" in source
    for forbidden in (
        "--seed",
        "--start-index",
        "--end-index",
        "--negatives-per-target",
        "--shard-size",
    ):
        assert forbidden not in source
    assert "frozen_mid_dev_calibration_readiness_plan" in source
    assert "build_real_mid_dev_calibration_shard" in source


def test_calibration_shard_io_has_no_experiments_layer_dependency():
    source = Path("fuckmark/corpus/mid_dev_calibration_shard_io.py").read_text(encoding="utf-8").lower()
    assert "experiments" not in source
    assert "object_pairs_hook=_unique_object" in source
    assert "parse_constant=_reject_constant" in source
