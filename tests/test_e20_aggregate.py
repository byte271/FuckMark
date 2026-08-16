from math import isclose

from test_e20_bundle import _bundle_fixture
from fuckmark.corpus import WatermarkLabel
from fuckmark.experiments.e20_aggregate import (
    E20AnalysisPopulation,
    E20MetricId,
    E20MetricStatus,
    build_e20_aggregate_bundle,
)
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_execution import derive_e20_condition_seed
from fuckmark.experiments.e20_rows import (
    E20AlignmentFields,
    E20AuditFields,
    E20DetectorFields,
    E20FidelityFields,
    E20GValueFields,
    E20GenerationFields,
    E20HumanFidelityStatus,
    E20IdentityFields,
    E20ModelFields,
    E20ObservationFields,
    E20OutcomeRow,
    E20SourceFields,
    E20StatisticsFields,
    E20TextFields,
    E20TransformFields,
    E20WatermarkFields,
    ExperimentReasonCode,
)
from fuckmark.hashing import sha256_json, sha256_text


def _decision(score, threshold, operator):
    if operator.value == ">=":
        return score >= threshold
    return score > threshold


def _outcome_for(authorization, preregistration, corpus_manifest, condition, sample, failure):
    track = preregistration.watermark_tracks.track_for(sample.watermark.watermark_config_hash)
    bundle = next(value for value in preregistration.calibration_bundles if value.bundle_hash == condition.calibration_bundle_hash)
    threshold = next(value for value in bundle.thresholds if value.target_fpr == condition.target_fpr)
    if sample.label is WatermarkLabel.WATERMARKED:
        pristine_score = threshold.value
        transformed_score = max(0.0, threshold.value - 0.05)
    else:
        pristine_score = max(0.0, threshold.value - 0.20)
        transformed_score = pristine_score
    source_words = tuple(sample.text.split())
    transformed_hash = sha256_text(f"transformed:{sample.sample_id}:{condition.transform_condition_id}")
    schedule_seed = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
    detector_config_hash = bundle.detector_identity.detector_config_hash
    identity = E20IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E20",
        condition.condition_id,
        sample.sample_id,
        sample.match_id,
    )
    source = E20SourceFields(
        track.adapter_id,
        track.source_pin.commit,
        track.adapter_config_hash,
    )
    model = E20ModelFields(
        sample.model.model_id,
        sample.model.model_revision,
        sample.model.tokenizer_id,
        sample.model.tokenizer_revision,
    )
    watermark = E20WatermarkFields(
        sample.watermark.watermark_config_hash,
        sample.watermark.key_split,
        sample.watermark.key_id,
    )
    generation = E20GenerationFields(
        sample.generation.seed,
        sample.generation.temperature,
        sample.generation.top_k,
        sample.generation.top_p,
        sample.generation_realized_length,
    )
    text = E20TextFields(
        sample.text_sha256,
        transformed_hash,
        len(sample.text),
        max(1, len(sample.text) - 1),
        len(source_words),
        len(source_words),
        len(sample.generation_tokens.continuation_token_ids),
        len(sample.generation_tokens.continuation_token_ids),
    )
    transform = E20TransformFields(
        preregistration.transform_ruleset_hash,
        condition.schedule_policy,
        schedule_seed,
        condition.budget,
        condition.budget_unit,
        1,
        sha256_text(f"candidate-pool:{sample.sample_id}:{condition.transform_condition_id}"),
        sha256_text(f"scheduler-input:{sample.sample_id}:{condition.transform_condition_id}"),
        sha256_text(f"schedule-result:{sample.sample_id}:{condition.transform_condition_id}"),
        sha256_text(f"operation-trace:{sample.sample_id}:{condition.transform_condition_id}"),
        True,
    )
    fidelity = E20FidelityFields(
        True,
        (ExperimentReasonCode.OK,),
        1,
        1,
        1,
        E20HumanFidelityStatus.NOT_SELECTED,
        None,
    )
    alignment = E20AlignmentFields(
        "canonical-token-levenshtein-v1",
        sha256_text(f"alignment:{sample.sample_id}:{condition.transform_condition_id}"),
        0,
    )
    observation = E20ObservationFields(6, 6, 4, 2, 0, 0, 0, 0)
    gvalues = E20GValueFields(
        3,
        sha256_text(f"gvalues:{sample.sample_id}:{condition.transform_condition_id}"),
        6,
        2,
    )
    detector = E20DetectorFields(
        bundle.detector_identity.detector_family,
        detector_config_hash,
        None,
        bundle.bundle_hash,
        threshold.threshold_hash,
        threshold.comparison_operator,
        condition.target_fpr,
        threshold.value,
        bundle.robust_scale,
        pristine_score,
        transformed_score,
        (pristine_score - threshold.value) / bundle.robust_scale,
        (transformed_score - threshold.value) / bundle.robust_scale,
        _decision(pristine_score, threshold.value, threshold.comparison_operator),
        _decision(transformed_score, threshold.value, threshold.comparison_operator),
    )
    statistics = E20StatisticsFields(
        sha256_json(
            {
                "model_tokenizer_identity_hash": sample.model.identity_hash,
                "domain": sample.domain.value,
                "target_length": sample.target_length,
                "key_id": sample.watermark.key_id,
                "detector_config_hash": detector_config_hash,
                "target_fpr": condition.target_fpr,
            }
        ),
        sample.sample_id,
        condition.hypothesis_class,
    )
    audit = E20AuditFields(
        failure.audit.worker_version,
        failure.audit.timestamp_utc,
        failure.audit.environment_snapshot_hash,
        failure.audit.authorization_hash,
        failure.audit.run_ledger_hash,
        (sha256_text(f"aggregate-outcome:{sample.sample_id}:{condition.condition_id}"),),
    )
    return E20OutcomeRow.create(
        identity,
        source,
        model,
        watermark,
        generation,
        text,
        transform,
        fidelity,
        alignment,
        observation,
        gvalues,
        detector,
        statistics,
        audit,
    )


def _metric(condition, population, metric_id):
    return next(
        value
        for value in condition.metrics
        if value.population is population and value.metric_id is metric_id
    )


def test_e20_aggregate_preserves_policy_all_negative_controls_and_fixed_fpr_metrics() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    chosen = condition_plan.conditions[0]
    failure_by_key = {(value.identity.sample_id, value.identity.condition_id): value for value in failures}
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    chosen_failures = tuple(value for value in failures if value.identity.condition_id == chosen.condition_id)
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
    removed = {(value.identity.sample_id, value.identity.condition_id) for value in chosen_failures}
    remaining_failures = tuple(
        value for value in failures if (value.identity.sample_id, value.identity.condition_id) not in removed
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
    replay = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    assert aggregate == replay
    assert aggregate.aggregate_hash == replay.aggregate_hash
    chosen_aggregate = next(value for value in aggregate.conditions if value.condition_id == chosen.condition_id)
    assert chosen_aggregate.headline_eligible is True
    assert chosen_aggregate.failure_row_count == 0
    pristine_tpr = _metric(chosen_aggregate, E20AnalysisPopulation.POLICY_ALL, E20MetricId.PRISTINE_TPR)
    transformed_tpr = _metric(chosen_aggregate, E20AnalysisPopulation.POLICY_ALL, E20MetricId.TRANSFORMED_TPR)
    tpr_change = _metric(chosen_aggregate, E20AnalysisPopulation.POLICY_ALL, E20MetricId.TPR_CHANGE)
    decision_loss = _metric(chosen_aggregate, E20AnalysisPopulation.PRISTINE_POSITIVE, E20MetricId.DECISION_LOSS_RATE)
    transformed_fpr = _metric(chosen_aggregate, E20AnalysisPopulation.NEGATIVE_CONTROL_ALL, E20MetricId.TRANSFORMED_FPR)
    pristine_auc = _metric(chosen_aggregate, E20AnalysisPopulation.COMBINED_CLASSIFICATION, E20MetricId.PRISTINE_ROC_AUC)
    for metric in (pristine_tpr, transformed_tpr, tpr_change, decision_loss, transformed_fpr, pristine_auc):
        assert metric.status is E20MetricStatus.COMPLETE
        assert metric.confidence_interval is not None
    assert pristine_tpr.estimate == 1.0
    assert transformed_tpr.estimate == 0.0
    assert tpr_change.estimate == -1.0
    assert decision_loss.estimate == 1.0
    assert transformed_fpr.estimate == 0.0
    assert pristine_auc.estimate == 1.0
    assert pristine_tpr.confidence_interval.lower == 1.0
    assert pristine_tpr.confidence_interval.upper == 1.0
    assert tpr_change.confidence_interval.lower == -1.0
    assert tpr_change.confidence_interval.upper == -1.0


def test_e20_aggregate_marks_failure_only_conditions_ineligible_for_headline_claims() -> None:
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
    for condition in aggregate.conditions:
        assert condition.headline_eligible is False
        assert condition.failure_row_count == condition.expected_row_count
        tpr = _metric(condition, E20AnalysisPopulation.POLICY_ALL, E20MetricId.TRANSFORMED_TPR)
        assert tpr.estimate is None
        assert tpr.status is E20MetricStatus.NO_ANALYSABLE_ROWS
        assert tpr.failure_sample_count > 0
