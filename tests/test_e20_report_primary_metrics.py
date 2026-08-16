from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture
from fuckmark.experiments.confirmatory_detector_readiness import build_confirmatory_detector_readiness
from fuckmark.experiments.e20_aggregate import (
    E20AnalysisPopulation,
    E20MetricId,
    build_e20_aggregate_bundle,
)
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_inference import build_e20_inference_bundle
from fuckmark.experiments.e20_key_analysis import build_e20_key_analysis_bundle
from fuckmark.experiments.e20_report import build_e20_confirmatory_report


def test_report_carries_normalized_coverage_efficiency_primary_metric() -> None:
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
    remaining_failures = tuple(
        value
        for value in failures
        if (value.identity.sample_id, value.identity.condition_id) not in removed
    )
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        remaining_failures,
    )
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    key_analysis = build_e20_key_analysis_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    inference = build_e20_inference_bundle(
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    readiness = build_confirmatory_detector_readiness(preregistration)
    report = build_e20_confirmatory_report(
        result_bundle,
        aggregate,
        key_analysis,
        inference,
        readiness,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    aggregate_condition = next(
        value for value in aggregate.conditions if value.condition_id == chosen.condition_id
    )
    metric = next(
        value
        for value in aggregate_condition.metrics
        if value.population is E20AnalysisPopulation.POLICY_ALL
        and value.metric_id is E20MetricId.COVERAGE_EFFICIENCY
    )
    headline = next(
        value for value in report.headlines if value.condition_id == chosen.condition_id
    )
    assert headline.coverage_efficiency == metric.estimate
    assert headline.coverage_efficiency is not None
