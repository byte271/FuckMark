from test_e20_bundle import _bundle_fixture

import pytest

from fuckmark.experiments.e20_aggregate import (
    E20AggregateBundle,
    E20ConditionAggregate,
    E20MetricEstimate,
    E20MetricStatus,
    build_e20_aggregate_bundle,
)
from fuckmark.experiments.e20_aggregate_verification import (
    E20AggregateVerificationError,
    verify_e20_aggregate_bundle,
)
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.hashing import sha256_json


def test_e20_aggregate_replays_exactly_from_failure_complete_result_bundle() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    verify_e20_aggregate_bundle(
        aggregate,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )


def test_e20_aggregate_replay_rejects_rehashed_semantically_wrong_metric_status() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    condition = aggregate.conditions[0]
    metric = condition.metrics[0]
    forged_metric_payload = metric._payload()
    forged_metric_payload["status"] = E20MetricStatus.NO_PRISTINE_POSITIVES.value
    forged_metric = E20MetricEstimate(
        metric.metric_id,
        metric.population,
        E20MetricStatus.NO_PRISTINE_POSITIVES,
        metric.estimate,
        metric.confidence_interval,
        metric.expected_sample_count,
        metric.analysed_sample_count,
        metric.failure_sample_count,
        sha256_json(forged_metric_payload),
    )
    forged_metrics = (forged_metric, *condition.metrics[1:])
    forged_metrics = tuple(sorted(forged_metrics, key=lambda value: (value.population.value, value.metric_id.value)))
    condition_payload = condition._payload()
    condition_payload["metrics"] = forged_metrics
    forged_condition = E20ConditionAggregate(
        condition.condition_id,
        condition.transform_condition_id,
        condition.calibration_bundle_hash,
        condition.target_fpr,
        condition.hypothesis_class,
        condition.expected_row_count,
        condition.outcome_row_count,
        condition.failure_row_count,
        condition.reason_counts,
        condition.headline_eligible,
        forged_metrics,
        sha256_json(condition_payload),
    )
    forged_conditions = (forged_condition, *aggregate.conditions[1:])
    forged_conditions = tuple(sorted(forged_conditions, key=lambda value: value.condition_id))
    aggregate_payload = aggregate._payload()
    aggregate_payload["conditions"] = forged_conditions
    forged = E20AggregateBundle(
        aggregate.algorithm_version,
        aggregate.execution_id,
        aggregate.result_bundle_hash,
        aggregate.preregistration_hash,
        aggregate.bootstrap_plan_hash,
        aggregate.bootstrap_rng_version,
        aggregate.bootstrap_quantile_version,
        forged_conditions,
        sha256_json(aggregate_payload),
    )
    with pytest.raises(E20AggregateVerificationError, match="does not replay exactly"):
        verify_e20_aggregate_bundle(
            forged,
            result_bundle,
            preregistration,
            corpus_manifest,
            condition_plan,
            authorization,
        )
