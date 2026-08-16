import pytest

from fuckmark.experiments.schedule_analysis import (
    E10PairStatus,
    E10Status,
    run_e10_spacing_comparison,
)
from fuckmark.experiments.transform_analysis import TransformAnalysisInputError
from fuckmark.transforms import SchedulePolicy
from schedule_experiment_helpers import attack_sources, schedule_row
from tiny_dev_experiment_helpers import tiny_dev_artifact


def _paired_rows(unmatched_source_index: int | None = None):
    rows = []
    for index, source in enumerate(attack_sources()):
        pool = f"spacing-pool-{source.sample_id}"
        clustered_cost = 1
        even_cost = 2 if unmatched_source_index == index else 1
        rows.extend(
            (
                schedule_row(
                    source,
                    SchedulePolicy.CLUSTERED,
                    variant=index,
                    pool=pool,
                    seed=31,
                    realized_cost=clustered_cost,
                    coverage=10 + index,
                    replacement_count=10 + index,
                    margin_drop=0.10 + index * 0.01,
                ),
                schedule_row(
                    source,
                    SchedulePolicy.EVEN_SPACING,
                    variant=index,
                    pool=pool,
                    seed=31,
                    realized_cost=even_cost,
                    coverage=14 + index,
                    replacement_count=14 + index,
                    margin_drop=0.14 + index * 0.01,
                ),
            )
        )
    return tuple(rows)


def test_e10_compares_same_pool_budget_seed_at_matched_realized_cost() -> None:
    result = run_e10_spacing_comparison(tiny_dev_artifact(), _paired_rows())
    assert result.status is E10Status.COMPLETE_MATCHED
    assert result.expected_source_count == 4
    assert result.observed_source_count == 4
    assert result.missing_source_ids == ()
    assert result.matched_pair_count == 4
    assert result.unmatched_cost_pair_count == 0
    assert result.mean_coverage_difference_even_minus_clustered == pytest.approx(4.0)
    assert result.mean_observation_ratio_difference_even_minus_clustered == pytest.approx(0.04)
    assert result.mean_margin_drop_difference_even_minus_clustered == pytest.approx(0.04)


def test_e10_withholds_unmatched_cost_pair_metrics_without_dropping_pair() -> None:
    result = run_e10_spacing_comparison(tiny_dev_artifact(), _paired_rows(unmatched_source_index=2))
    assert result.status is E10Status.WITHHELD_UNMATCHED_COST
    assert result.matched_pair_count == 3
    assert result.unmatched_cost_pair_count == 1
    assert len(result.pair_hashes) == 4


def test_e10_preserves_missing_source_status() -> None:
    missing_id = attack_sources()[-1].sample_id
    rows = tuple(row for row in _paired_rows() if row.source_sample_id != missing_id)
    result = run_e10_spacing_comparison(tiny_dev_artifact(), rows)
    assert result.status is E10Status.INCOMPLETE
    assert result.observed_source_count == 3
    assert result.missing_source_ids == (missing_id,)


def test_e10_rejects_orphan_policy_row_instead_of_silent_deletion() -> None:
    rows = list(_paired_rows())
    rows.pop()
    with pytest.raises(TransformAnalysisInputError, match="both clustered and even"):
        run_e10_spacing_comparison(tiny_dev_artifact(), tuple(rows))


def test_e10_rejects_pairing_when_seed_or_candidate_pool_differs() -> None:
    rows = list(_paired_rows())
    source = attack_sources()[0]
    rows[1] = schedule_row(
        source,
        SchedulePolicy.EVEN_SPACING,
        variant=0,
        pool="different-pool",
        seed=31,
        realized_cost=1,
        coverage=14,
        replacement_count=14,
        margin_drop=0.14,
    )
    with pytest.raises(TransformAnalysisInputError, match="both clustered and even"):
        run_e10_spacing_comparison(tiny_dev_artifact(), tuple(rows))


def test_e10_pair_statuses_are_materialized_in_result_artifacts() -> None:
    from fuckmark.experiments.schedule_analysis import E10SpacingPair
    result = run_e10_spacing_comparison(tiny_dev_artifact(), _paired_rows(unmatched_source_index=0))
    assert result.unmatched_cost_pair_count == 1
    assert result.status is E10Status.WITHHELD_UNMATCHED_COST
    assert E10PairStatus.MATCHED.value == "MATCHED"
    assert E10SpacingPair.__name__ == "E10SpacingPair"
