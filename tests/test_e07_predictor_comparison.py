from dataclasses import replace

import pytest

from fuckmark.corpus import CorpusSplit, KeySplit, WatermarkLabel
from fuckmark.experiments.development_calibration import calibrate_tiny_dev_detector
from fuckmark.experiments.transform_analysis import (
    DEVELOPMENT_TRANSFORM_ROW_VERSION,
    DevelopmentClaimStatus,
    DevelopmentTransformRow,
    PredictorMetric,
    TransformAnalysisInputError,
    run_e07_predictor_comparison,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import SchedulePolicy
from tiny_dev_experiment_helpers import calibration_evidence, tiny_dev_artifact


def _threshold_identity():
    binding = calibrate_tiny_dev_detector(tiny_dev_artifact(), calibration_evidence())
    threshold = next(value for value in binding.calibration_bundle.thresholds if value.target_fpr == 0.01)
    return binding.calibration_bundle.detector_identity.identity_hash, threshold.threshold_hash, threshold.value


def _rows():
    artifact = tiny_dev_artifact()
    detector_identity_hash, threshold_hash, threshold_value = _threshold_identity()
    sources = tuple(
        sorted(
            (
                sample
                for sample in artifact.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
                and sample.label is WatermarkLabel.WATERMARKED
            ),
            key=lambda sample: sample.sample_id,
        )
    )
    output = []
    for source_index, sample in enumerate(sources):
        pristine_score = 0.82 + source_index * 0.01
        candidate_pool_hash = sha256_text(f"pool-{sample.sample_id}")
        for variant_index, replacement_count in enumerate((10, 20, 30), start=1):
            margin_drop = replacement_count / 200.0
            output.append(
                DevelopmentTransformRow.create(
                    source_sample_id=sample.sample_id,
                    prompt_family_id=sample.prompt_family_id,
                    source_text_hash=sha256_text(sample.text),
                    transformed_text_hash=sha256_text(f"{sample.text}|variant-{variant_index}"),
                    key_split=KeySplit.DEV,
                    detector_identity_hash=detector_identity_hash,
                    threshold_hash=threshold_hash,
                    threshold_value=threshold_value,
                    candidate_pool_hash=candidate_pool_hash,
                    scheduler_input_hash=sha256_text(f"scheduler-input-{sample.sample_id}-{variant_index}"),
                    schedule_result_hash=sha256_text(f"schedule-result-{sample.sample_id}-{variant_index}"),
                    schedule_policy=SchedulePolicy.LEFT_TO_RIGHT,
                    schedule_seed=variant_index,
                    budget=3,
                    budget_unit="operation",
                    realized_edit_cost=1,
                    scheduler_covered_interval_size=replacement_count,
                    word_edit_count=1,
                    word_count=100,
                    observation_replacement_count=replacement_count,
                    original_observation_count=100,
                    pristine_score=pristine_score,
                    transformed_score=pristine_score - margin_drop,
                    eligible=True,
                )
            )
    return tuple(output)


def test_transform_row_preserves_integer_metric_denominators_and_derived_rates() -> None:
    row = _rows()[0]
    assert row.algorithm_version == DEVELOPMENT_TRANSFORM_ROW_VERSION
    assert row.word_edit_rate == 0.01
    assert row.observation_replacement_ratio == 0.1
    assert row.margin_drop == pytest.approx(0.05)
    assert row.replacement_per_edit == 10.0
    assert row.pristine_detected
    assert row.transformed_detected


def test_e07_uses_leave_one_source_out_and_withholds_dev_only_superiority_claim() -> None:
    result = run_e07_predictor_comparison(tiny_dev_artifact(), _rows())
    assert result.source_count == 4
    assert result.variant_count == 12
    assert result.observation_replacement_rmse < result.word_edit_rmse
    assert result.lower_error_metric is PredictorMetric.OBSERVATION_REPLACEMENT
    assert result.claim_status is DevelopmentClaimStatus.WITHHELD_DEV_ONLY


def test_e07_requires_every_watermarked_attack_source_and_frozen_detector_threshold() -> None:
    rows = _rows()
    first_source = rows[0].source_sample_id
    missing_source = tuple(row for row in rows if row.source_sample_id != first_source)
    with pytest.raises(TransformAnalysisInputError, match="cover every"):
        run_e07_predictor_comparison(tiny_dev_artifact(), missing_source)
    drifted = list(rows)
    drifted[-1] = DevelopmentTransformRow.create(
        source_sample_id=drifted[-1].source_sample_id,
        prompt_family_id=drifted[-1].prompt_family_id,
        source_text_hash=drifted[-1].source_text_hash,
        transformed_text_hash=drifted[-1].transformed_text_hash,
        key_split=drifted[-1].key_split,
        detector_identity_hash=drifted[-1].detector_identity_hash,
        threshold_hash="f" * 64,
        threshold_value=drifted[-1].threshold_value,
        candidate_pool_hash=drifted[-1].candidate_pool_hash,
        scheduler_input_hash=drifted[-1].scheduler_input_hash,
        schedule_result_hash=drifted[-1].schedule_result_hash,
        schedule_policy=drifted[-1].schedule_policy,
        schedule_seed=drifted[-1].schedule_seed,
        budget=drifted[-1].budget,
        budget_unit=drifted[-1].budget_unit,
        realized_edit_cost=drifted[-1].realized_edit_cost,
        scheduler_covered_interval_size=drifted[-1].scheduler_covered_interval_size,
        word_edit_count=drifted[-1].word_edit_count,
        word_count=drifted[-1].word_count,
        observation_replacement_count=drifted[-1].observation_replacement_count,
        original_observation_count=drifted[-1].original_observation_count,
        pristine_score=drifted[-1].pristine_score,
        transformed_score=drifted[-1].transformed_score,
        eligible=drifted[-1].eligible,
    )
    with pytest.raises(TransformAnalysisInputError, match="one frozen detector and threshold"):
        run_e07_predictor_comparison(tiny_dev_artifact(), tuple(drifted))


def test_e07_rejects_duplicate_artifacts() -> None:
    rows = _rows()
    with pytest.raises(TransformAnalysisInputError, match="duplicate"):
        run_e07_predictor_comparison(tiny_dev_artifact(), (*rows, rows[0]))


def test_ineligible_policy_row_must_preserve_source_and_zero_realized_metrics() -> None:
    sample = next(
        sample
        for sample in tiny_dev_artifact().manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT and sample.label is WatermarkLabel.WATERMARKED
    )
    detector_identity_hash, threshold_hash, threshold_value = _threshold_identity()
    source_hash = sha256_text(sample.text)
    row = DevelopmentTransformRow.create(
        source_sample_id=sample.sample_id,
        prompt_family_id=sample.prompt_family_id,
        source_text_hash=source_hash,
        transformed_text_hash=source_hash,
        key_split=KeySplit.DEV,
        detector_identity_hash=detector_identity_hash,
        threshold_hash=threshold_hash,
        threshold_value=threshold_value,
        candidate_pool_hash=sha256_text("empty-pool"),
        scheduler_input_hash=sha256_text("empty-scheduler-input"),
        schedule_result_hash=sha256_text("empty-schedule-result"),
        schedule_policy=SchedulePolicy.RANDOM_VALID,
        schedule_seed=0,
        budget=2,
        budget_unit="operation",
        realized_edit_cost=0,
        scheduler_covered_interval_size=0,
        word_edit_count=0,
        word_count=100,
        observation_replacement_count=0,
        original_observation_count=100,
        pristine_score=0.8,
        transformed_score=0.8,
        eligible=False,
    )
    assert not row.eligible
    with pytest.raises(ValueError, match="preserve text and detector score"):
        DevelopmentTransformRow.create(
            source_sample_id=sample.sample_id,
            prompt_family_id=sample.prompt_family_id,
            source_text_hash=source_hash,
            transformed_text_hash=sha256_text("changed"),
            key_split=KeySplit.DEV,
            detector_identity_hash=detector_identity_hash,
            threshold_hash=threshold_hash,
            threshold_value=threshold_value,
            candidate_pool_hash=sha256_text("empty-pool"),
            scheduler_input_hash=sha256_text("empty-scheduler-input"),
            schedule_result_hash=sha256_text("empty-schedule-result"),
            schedule_policy=SchedulePolicy.RANDOM_VALID,
            schedule_seed=0,
            budget=2,
            budget_unit="operation",
            realized_edit_cost=0,
            scheduler_covered_interval_size=0,
            word_edit_count=0,
            word_count=100,
            observation_replacement_count=0,
            original_observation_count=100,
            pristine_score=0.8,
            transformed_score=0.7,
            eligible=False,
        )


def test_transform_row_and_e07_result_reject_hash_tampering() -> None:
    row = _rows()[0]
    with pytest.raises(ValueError, match="row_hash"):
        replace(row, row_hash="f" * 64)
    result = run_e07_predictor_comparison(tiny_dev_artifact(), _rows())
    forged_payload = result._payload()
    forged_payload["observation_replacement_rmse"] = result.observation_replacement_rmse + 0.1
    with pytest.raises(ValueError, match="lower_error_metric|result_hash"):
        replace(
            result,
            observation_replacement_rmse=result.observation_replacement_rmse + 0.1,
            result_hash=sha256_json(forged_payload),
        )
