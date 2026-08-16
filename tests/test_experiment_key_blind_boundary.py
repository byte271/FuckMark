import pytest

from fuckmark.experiments.e08_dose import run_e08_dose_response
from fuckmark.experiments.schedule_analysis import E11Status, run_e09_random_baseline, run_e10_spacing_comparison, run_e11_greedy_comparison
from fuckmark.experiments.transform_analysis import TransformAnalysisInputError, run_e07_predictor_comparison
from fuckmark.transforms import SchedulePolicy
from schedule_experiment_helpers import attack_sources, schedule_row
from tiny_dev_experiment_helpers import tiny_dev_artifact


def _single_policy_rows(policy: SchedulePolicy):
    rows = []
    for index, source in enumerate(attack_sources()):
        rows.append(
            schedule_row(
                source,
                policy,
                variant=index,
                pool=f"key-blind-single-{source.sample_id}",
                seed=123,
                realized_cost=1,
                coverage=10 + index,
                replacement_count=10 + index,
                margin_drop=0.10 + index * 0.01,
                secret_access_observed=index == 0,
            )
        )
    return tuple(rows)


def _paired_rows(left: SchedulePolicy, right: SchedulePolicy):
    rows = []
    for index, source in enumerate(attack_sources()):
        pool = f"key-blind-pair-{source.sample_id}"
        rows.extend(
            (
                schedule_row(
                    source,
                    left,
                    variant=index,
                    pool=pool,
                    seed=321,
                    realized_cost=1,
                    coverage=10,
                    replacement_count=10,
                    margin_drop=0.10,
                    secret_access_observed=False,
                ),
                schedule_row(
                    source,
                    right,
                    variant=index,
                    pool=pool,
                    seed=321,
                    realized_cost=1,
                    coverage=12,
                    replacement_count=12,
                    margin_drop=0.12,
                    secret_access_observed=index == 0,
                ),
            )
        )
    return tuple(rows)


def test_e07_and_e08_reject_secret_contaminated_key_blind_rows() -> None:
    rows = _single_policy_rows(SchedulePolicy.LEFT_TO_RIGHT)
    with pytest.raises(TransformAnalysisInputError, match="secret access"):
        run_e07_predictor_comparison(tiny_dev_artifact(), rows)
    with pytest.raises(TransformAnalysisInputError, match="secret access"):
        run_e08_dose_response(tiny_dev_artifact(), rows)


def test_e09_rejects_secret_contaminated_random_baseline() -> None:
    with pytest.raises(TransformAnalysisInputError, match="secret access"):
        run_e09_random_baseline(
            tiny_dev_artifact(),
            _single_policy_rows(SchedulePolicy.RANDOM_VALID),
        )


def test_e10_rejects_secret_contaminated_spacing_comparison() -> None:
    with pytest.raises(TransformAnalysisInputError, match="secret access"):
        run_e10_spacing_comparison(
            tiny_dev_artifact(),
            _paired_rows(SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING),
        )


def test_e11_preserves_secret_contamination_as_a_result_artifact() -> None:
    result = run_e11_greedy_comparison(
        tiny_dev_artifact(),
        _paired_rows(SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND),
    )
    assert result.status is E11Status.CONTAMINATED
    assert result.contaminated_pair_count == 1
