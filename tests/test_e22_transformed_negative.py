from collections import Counter
from dataclasses import replace

import pytest

from test_e20_bundle import _bundle_fixture, _synthetic_outcome
from fuckmark.corpus import WatermarkLabel
from fuckmark.detectors import ComparisonOperator
from fuckmark.experiments.e20_bundle import (
    E20_RESULT_BUNDLE_ALGORITHM_VERSION,
    E20ReasonCount,
    E20ResultBundle,
)
from fuckmark.experiments.e20_rows import E20DetectorFields, ExperimentReasonCode
from fuckmark.experiments.e22_transformed_negative import (
    E22AnalysisStatus,
    E22CellStatus,
    E22Estimand,
    build_e22_transformed_negative_report,
    verify_e22_transformed_negative_report,
)
from fuckmark.hashing import sha256_json, sha256_text


def _decision(operator, score, threshold):
    if operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
        return score >= threshold
    return score > threshold


def _with_scores(row, pristine_score, transformed_score):
    detector = row.detector
    replacement = E20DetectorFields(
        detector.detector_family,
        detector.detector_config_hash,
        detector.checkpoint_hash,
        detector.calibration_bundle_hash,
        detector.threshold_hash,
        detector.comparison_operator,
        detector.target_fpr,
        detector.threshold_value,
        detector.robust_scale,
        pristine_score,
        transformed_score,
        (pristine_score - detector.threshold_value) / detector.robust_scale,
        (transformed_score - detector.threshold_value) / detector.robust_scale,
        _decision(detector.comparison_operator, pristine_score, detector.threshold_value),
        _decision(detector.comparison_operator, transformed_score, detector.threshold_value),
    )
    payload = row._payload()
    payload["detector"] = replacement
    return replace(row, detector=replacement, row_hash=sha256_json(payload))


def _result_bundle(corpus_manifest, condition_plan, outcomes, failures=()):
    ordered_outcomes = tuple(
        sorted(outcomes, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash))
    )
    ordered_failures = tuple(
        sorted(failures, key=lambda value: (value.identity.sample_id, value.identity.condition_id, value.row_hash))
    )
    counts = Counter()
    for row in ordered_outcomes:
        counts[row.fidelity.reason_codes[0]] += 1
    for row in ordered_failures:
        counts[row.reason_code] += 1
    reason_counts = tuple(E20ReasonCount(reason, counts[reason]) for reason in ExperimentReasonCode)
    source = ordered_outcomes[0] if ordered_outcomes else ordered_failures[0]
    payload = {
        "algorithm_version": E20_RESULT_BUNDLE_ALGORITHM_VERSION,
        "execution_id": source.identity.execution_id,
        "authorization_hash": source.audit.authorization_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "condition_plan_hash": condition_plan.plan_hash,
        "outcome_rows": ordered_outcomes,
        "failure_rows": ordered_failures,
        "reason_counts": reason_counts,
        "expected_row_count": len(ordered_outcomes) + len(ordered_failures),
        "observed_row_count": len(ordered_outcomes) + len(ordered_failures),
        "outcome_row_count": len(ordered_outcomes),
        "failure_row_count": len(ordered_failures),
    }
    return E20ResultBundle(
        E20_RESULT_BUNDLE_ALGORITHM_VERSION,
        source.identity.execution_id,
        source.audit.authorization_hash,
        corpus_manifest.manifest_hash,
        condition_plan.plan_hash,
        ordered_outcomes,
        ordered_failures,
        reason_counts,
        len(ordered_outcomes) + len(ordered_failures),
        len(ordered_outcomes) + len(ordered_failures),
        len(ordered_outcomes),
        len(ordered_failures),
        sha256_json(payload),
    )


def _fixture_rows():
    _, _, corpus_manifest, condition_plan, failures = _bundle_fixture()
    labels = {value.sample_id: value.label for value in corpus_manifest.samples}
    negative_failures = tuple(
        value for value in failures if labels[value.identity.sample_id] is WatermarkLabel.UNWATERMARKED
    )
    condition_id = negative_failures[0].identity.condition_id
    same_condition = tuple(value for value in negative_failures if value.identity.condition_id == condition_id)
    condition = condition_plan.condition(condition_id)
    first = _with_scores(
        _synthetic_outcome(
            same_condition[0],
            condition,
            transformed_hash=sha256_text("e22-negative-1"),
            transform_suffix="e22-negative-1",
        ),
        0.4,
        0.6,
    )
    second = _with_scores(
        _synthetic_outcome(
            same_condition[1],
            condition,
            transformed_hash=sha256_text("e22-negative-2"),
            transform_suffix="e22-negative-2",
        ),
        0.4,
        0.4,
    )
    return corpus_manifest, condition_plan, failures, condition_id, first, second, same_condition


def test_e22_quantifies_transformed_negative_fpr_and_score_shift() -> None:
    corpus_manifest, condition_plan, _, condition_id, first, second, _ = _fixture_rows()
    bundle = _result_bundle(corpus_manifest, condition_plan, (first, second))

    report = build_e22_transformed_negative_report(bundle, corpus_manifest, condition_plan)

    assert report.status is E22AnalysisStatus.COMPLETE
    assert report.negative_outcome_count == 2
    assert report.negative_failure_count == 0
    assert report.negative_row_count == 2
    policy = next(
        value
        for value in report.cells
        if value.condition_id == condition_id and value.estimand is E22Estimand.POLICY_ALL
    )
    eligible = next(
        value
        for value in report.cells
        if value.condition_id == condition_id and value.estimand is E22Estimand.ELIGIBLE_ONLY
    )
    assert policy.status is E22CellStatus.ESTIMATED
    assert policy.pristine_fpr.positive_count == 0
    assert policy.pristine_fpr.trial_count == 2
    assert policy.transformed_fpr.positive_count == 1
    assert policy.transformed_fpr.trial_count == 2
    assert policy.fpr_shift == 0.5
    assert policy.false_to_true_count == 1
    assert policy.true_to_false_count == 0
    assert policy.mean_raw_score_shift == pytest.approx(0.1)
    assert policy.mean_standardized_margin_shift == pytest.approx(1.0)
    assert eligible.fpr_shift == policy.fpr_shift
    assert report.maximum_positive_fpr_shift == 0.5
    verify_e22_transformed_negative_report(report, bundle, corpus_manifest, condition_plan)


def test_e22_ignores_watermarked_rows_and_accounts_negative_failures() -> None:
    corpus_manifest, condition_plan, failures, condition_id, first, second, same_condition = _fixture_rows()
    labels = {value.sample_id: value.label for value in corpus_manifest.samples}
    watermarked_failure = next(
        value
        for value in failures
        if value.identity.condition_id == condition_id
        and labels[value.identity.sample_id] is WatermarkLabel.WATERMARKED
    )
    condition = condition_plan.condition(condition_id)
    watermarked = _with_scores(
        _synthetic_outcome(
            watermarked_failure,
            condition,
            transformed_hash=sha256_text("e22-watermarked"),
            transform_suffix="e22-watermarked",
        ),
        0.1,
        0.9,
    )
    bundle = _result_bundle(
        corpus_manifest,
        condition_plan,
        (first, second, watermarked),
        (same_condition[2],),
    )

    report = build_e22_transformed_negative_report(bundle, corpus_manifest, condition_plan)

    assert report.negative_outcome_count == 2
    assert report.negative_failure_count == 1
    assert report.negative_row_count == 3
    policy = next(
        value
        for value in report.cells
        if value.condition_id == condition_id and value.estimand is E22Estimand.POLICY_ALL
    )
    assert policy.negative_outcome_count == 2
    assert policy.negative_failure_count == 1
    assert policy.fpr_shift == 0.5


def test_e22_report_hash_binds_source_bundle() -> None:
    corpus_manifest, condition_plan, _, _, first, second, _ = _fixture_rows()
    bundle = _result_bundle(corpus_manifest, condition_plan, (first, second))
    report = build_e22_transformed_negative_report(bundle, corpus_manifest, condition_plan)

    with pytest.raises(ValueError, match="report_hash"):
        replace(report, result_bundle_hash=sha256_text("tampered-e22-bundle"))


def test_e22_rejects_bundle_with_mismatched_corpus_binding() -> None:
    corpus_manifest, condition_plan, _, _, first, second, _ = _fixture_rows()
    bundle = _result_bundle(corpus_manifest, condition_plan, (first, second))
    payload = bundle._payload()
    payload["corpus_manifest_hash"] = sha256_text("different-e22-corpus")
    forged = replace(
        bundle,
        corpus_manifest_hash=payload["corpus_manifest_hash"],
        bundle_hash=sha256_json(payload),
    )

    with pytest.raises(ValueError, match="corpus manifest does not match"):
        build_e22_transformed_negative_report(forged, corpus_manifest, condition_plan)
