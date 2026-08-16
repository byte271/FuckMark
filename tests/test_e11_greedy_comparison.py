import pytest

from fuckmark.experiments.schedule_analysis import (
    E11Status,
    HeldOutClaimStatus,
    run_e11_greedy_comparison,
)
from fuckmark.experiments.transform_analysis import TransformAnalysisInputError
from fuckmark.transforms import SchedulePolicy
from schedule_experiment_helpers import attack_sources, schedule_row
from tiny_dev_experiment_helpers import tiny_dev_artifact


def _paired_rows(secret_source_index: int | None = None):
    rows = []
    for index, source in enumerate(attack_sources()):
        pool = f"greedy-pool-{source.sample_id}"
        secret = secret_source_index == index
        rows.extend(
            (
                schedule_row(
                    source,
                    SchedulePolicy.RANDOM_VALID,
                    variant=index,
                    pool=pool,
                    seed=91,
                    realized_cost=2,
                    coverage=10,
                    replacement_count=10,
                    margin_drop=0.10,
                    secret_access_observed=False,
                ),
                schedule_row(
                    source,
                    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
                    variant=index,
                    pool=pool,
                    seed=91,
                    realized_cost=2,
                    coverage=14,
                    replacement_count=14,
                    margin_drop=0.14,
                    secret_access_observed=secret,
                ),
            )
        )
    return tuple(rows)


def test_e11_compares_replacement_per_edit_but_withholds_held_out_claim() -> None:
    result = run_e11_greedy_comparison(tiny_dev_artifact(), _paired_rows())
    assert result.status is E11Status.DESCRIPTIVE_DEV_ONLY
    assert result.held_out_claim_status is HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS
    assert result.expected_source_count == 4
    assert result.paired_source_count == 4
    assert result.missing_source_ids == ()
    assert result.contaminated_pair_count == 0
    assert result.mean_improvement_greedy_minus_random == pytest.approx(2.0)


def test_e11_any_secret_access_contaminates_t1_result() -> None:
    result = run_e11_greedy_comparison(tiny_dev_artifact(), _paired_rows(secret_source_index=1))
    assert result.status is E11Status.CONTAMINATED
    assert result.held_out_claim_status is HeldOutClaimStatus.WITHHELD_CONTAMINATED
    assert result.contaminated_pair_count == 1


def test_e11_preserves_missing_random_greedy_source_as_incomplete() -> None:
    missing_id = attack_sources()[-1].sample_id
    rows = tuple(row for row in _paired_rows() if row.source_sample_id != missing_id)
    result = run_e11_greedy_comparison(tiny_dev_artifact(), rows)
    assert result.status is E11Status.INCOMPLETE_BASELINE
    assert result.paired_source_count == 3
    assert result.missing_source_ids == (missing_id,)
    assert result.held_out_claim_status is HeldOutClaimStatus.WITHHELD_NO_HELD_OUT_KEYS


def test_e11_rejects_orphan_policy_row_and_wrong_policy() -> None:
    rows = list(_paired_rows())
    rows.pop()
    with pytest.raises(TransformAnalysisInputError, match="random and greedy"):
        run_e11_greedy_comparison(tiny_dev_artifact(), tuple(rows))
    wrong = list(_paired_rows())
    source = attack_sources()[0]
    wrong[1] = schedule_row(
        source,
        SchedulePolicy.EVEN_SPACING,
        variant=0,
        pool=f"greedy-pool-{source.sample_id}",
        seed=91,
        realized_cost=2,
        coverage=14,
        replacement_count=14,
        margin_drop=0.14,
    )
    with pytest.raises(TransformAnalysisInputError, match="RANDOM_VALID and COVERAGE_GREEDY"):
        run_e11_greedy_comparison(tiny_dev_artifact(), tuple(wrong))


def test_e11_rejects_candidate_pool_or_seed_mismatch_as_unpaired_input() -> None:
    rows = list(_paired_rows())
    source = attack_sources()[0]
    rows[1] = schedule_row(
        source,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        variant=0,
        pool="different-pool",
        seed=91,
        realized_cost=2,
        coverage=14,
        replacement_count=14,
        margin_drop=0.14,
    )
    with pytest.raises(TransformAnalysisInputError, match="random and greedy"):
        run_e11_greedy_comparison(tiny_dev_artifact(), tuple(rows))
