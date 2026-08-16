from math import isclose
from types import SimpleNamespace

from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture
from fuckmark.experiments.e20_aggregate import (
    E20AnalysisPopulation,
    E20MetricId,
    E20MetricStatus,
    _coverage_efficiency_estimate,
    build_e20_aggregate_bundle,
)
from fuckmark.experiments.e20_bundle import build_e20_result_bundle


def test_coverage_efficiency_uses_observation_replacement_per_normalized_token_edit() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    chosen = condition_plan.conditions[0]
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    chosen_failures = tuple(
        value for value in failures if value.identity.condition_id == chosen.condition_id
    )
    outcomes = tuple(
        _outcome_for(
            authorization,
            preregistration,
            corpus_manifest,
            chosen,
            sample_by_id[value.identity.sample_id],
            value,
        )
        for value in chosen_failures
    )
    removed = {
        (value.identity.sample_id, value.identity.condition_id)
        for value in chosen_failures
    }
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        tuple(
            value
            for value in failures
            if (value.identity.sample_id, value.identity.condition_id) not in removed
        ),
    )
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    condition = next(
        value for value in aggregate.conditions if value.condition_id == chosen.condition_id
    )
    metric = next(
        value
        for value in condition.metrics
        if value.population is E20AnalysisPopulation.POLICY_ALL
        and value.metric_id is E20MetricId.COVERAGE_EFFICIENCY
    )
    assert E20MetricId.COVERAGE_EFFICIENCY.value == (
        "observation_replacement_per_normalized_token_edit"
    )
    assert isclose(metric.estimate, (2 / 6) / (1 / 8), rel_tol=0.0, abs_tol=1e-15)


def test_coverage_efficiency_fails_closed_for_zero_token_edit_denominator() -> None:
    row = SimpleNamespace(fidelity=SimpleNamespace(token_edit_distance=0))
    metric = _coverage_efficiency_estimate(
        "a" * 64,
        "zero-token-edit-condition",
        E20AnalysisPopulation.POLICY_ALL,
        (row,),
        {},
        1,
        0,
        object(),
    )
    assert metric.status is E20MetricStatus.ZERO_TOKEN_EDIT_DENOMINATOR
    assert metric.estimate is None
    assert metric.confidence_interval is None
