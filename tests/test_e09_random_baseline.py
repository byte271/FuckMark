from dataclasses import replace

import pytest

from fuckmark.experiments.schedule_analysis import (
    E09_ALGORITHM_VERSION,
    E09BaselineStatus,
    run_e09_random_baseline,
)
from fuckmark.experiments.transform_analysis import TransformAnalysisInputError
from fuckmark.transforms import SchedulePolicy
from schedule_experiment_helpers import attack_sources, schedule_row
from tiny_dev_experiment_helpers import tiny_dev_artifact


def _complete_rows():
    sources = attack_sources()
    rows = [
        schedule_row(sources[0], SchedulePolicy.RANDOM_VALID, variant=0, replacement_count=1, realized_cost=1, margin_drop=0.01),
        schedule_row(sources[0], SchedulePolicy.RANDOM_VALID, variant=1, replacement_count=3, realized_cost=1, margin_drop=0.03),
    ]
    for index, source in enumerate(sources[1:], start=1):
        rows.append(
            schedule_row(
                source,
                SchedulePolicy.RANDOM_VALID,
                variant=index,
                replacement_count=5,
                realized_cost=1,
                margin_drop=0.05,
            )
        )
    return tuple(rows)


def test_e09_random_baseline_is_source_balanced_and_complete() -> None:
    result = run_e09_random_baseline(tiny_dev_artifact(), _complete_rows())
    assert result.algorithm_version == E09_ALGORITHM_VERSION
    assert result.status is E09BaselineStatus.COMPLETE
    assert result.expected_source_count == 4
    assert result.observed_source_count == 4
    assert result.missing_source_ids == ()
    assert result.random_variant_count == 5
    assert result.mean_replacement_per_edit == pytest.approx((2.0 + 5.0 + 5.0 + 5.0) / 4)
    assert result.mean_margin_drop == pytest.approx((0.02 + 0.05 + 0.05 + 0.05) / 4)


def test_e09_preserves_missing_baseline_sources_as_incomplete() -> None:
    rows = tuple(row for row in _complete_rows() if row.source_sample_id != attack_sources()[-1].sample_id)
    result = run_e09_random_baseline(tiny_dev_artifact(), rows)
    assert result.status is E09BaselineStatus.INCOMPLETE
    assert result.observed_source_count == 3
    assert result.missing_source_ids == (attack_sources()[-1].sample_id,)


def test_e09_rejects_non_random_rows_and_duplicate_artifacts() -> None:
    rows = _complete_rows()
    bad = list(rows)
    bad[-1] = schedule_row(
        attack_sources()[-1],
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        variant=99,
    )
    with pytest.raises(TransformAnalysisInputError, match="RANDOM_VALID"):
        run_e09_random_baseline(tiny_dev_artifact(), tuple(bad))
    with pytest.raises(TransformAnalysisInputError, match="duplicate"):
        run_e09_random_baseline(tiny_dev_artifact(), (*rows, rows[0]))


def test_e09_result_rejects_tampering() -> None:
    result = run_e09_random_baseline(tiny_dev_artifact(), _complete_rows())
    with pytest.raises(ValueError, match="result_hash|status"):
        replace(result, status=E09BaselineStatus.INCOMPLETE, result_hash="f" * 64)
