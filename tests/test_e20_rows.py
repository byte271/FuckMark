from dataclasses import replace

import pytest

from fuckmark.corpus import KeySplit
from fuckmark.detectors import ComparisonOperator, DetectorFamily
from fuckmark.experiments.e20_rows import (
    E20AlignmentFields,
    E20AuditFields,
    E20DetectorFields,
    E20FailureRow,
    E20FailureStage,
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
from fuckmark.hashing import sha256_text
from fuckmark.transforms import SchedulePolicy


def _identity() -> E20IdentityFields:
    execution_id = sha256_text("e20-execution")
    return E20IdentityFields(
        execution_id,
        execution_id,
        "E20",
        "random-valid-budget-1",
        "sample-001",
        "pair-001",
    )


def _audit() -> E20AuditFields:
    return E20AuditFields(
        "e20-worker-v1",
        "2026-08-16T20:00:00Z",
        sha256_text("environment"),
        sha256_text("authorization"),
        sha256_text("ledger"),
        tuple(sorted((sha256_text("artifact-a"), sha256_text("artifact-b")))),
    )


def _detector(pristine: float = 0.8, transformed: float = 0.4) -> E20DetectorFields:
    threshold = 0.5
    scale = 0.1
    return E20DetectorFields(
        DetectorFamily.MEAN,
        sha256_text("detector-config"),
        None,
        sha256_text("calibration-bundle"),
        sha256_text("threshold"),
        ComparisonOperator.GREATER_THAN_OR_EQUAL,
        0.01,
        threshold,
        scale,
        pristine,
        transformed,
        (pristine - threshold) / scale,
        (transformed - threshold) / scale,
        pristine >= threshold,
        transformed >= threshold,
    )


def _common_groups():
    return {
        "identity": _identity(),
        "source": E20SourceFields(
            "deepmind-synthid-reference-v1",
            "a" * 40,
            sha256_text("adapter-config"),
        ),
        "model": E20ModelFields(
            "example/model",
            "b" * 40,
            "example/tokenizer",
            "c" * 40,
        ),
        "watermark": E20WatermarkFields(
            sha256_text("watermark-config"),
            KeySplit.TEST,
            "test-key-0",
        ),
        "generation": E20GenerationFields(7, 0.8, 40, 0.95, 10),
        "alignment": E20AlignmentFields(
            "token-alignment-v1",
            sha256_text("edit-script"),
            0,
        ),
        "statistics": E20StatisticsFields(
            "model-domain-length-key-detector",
            "sample-001",
            "H13-primary",
        ),
        "audit": _audit(),
    }


def _changed_row() -> E20OutcomeRow:
    values = _common_groups()
    return E20OutcomeRow.create(
        **values,
        text=E20TextFields(
            sha256_text("source text"),
            sha256_text("transformed text"),
            100,
            98,
            20,
            20,
            10,
            10,
        ),
        transform=E20TransformFields(
            sha256_text("ruleset"),
            SchedulePolicy.RANDOM_VALID,
            11,
            2,
            "edit-cost",
            1,
            sha256_text("candidate-pool"),
            sha256_text("scheduler-input"),
            sha256_text("schedule-result"),
            sha256_text("operation-trace"),
            True,
        ),
        fidelity=E20FidelityFields(
            True,
            (ExperimentReasonCode.OK,),
            3,
            1,
            1,
            E20HumanFidelityStatus.NOT_SELECTED,
            None,
        ),
        observation=E20ObservationFields(8, 8, 5, 3, 0, 0, 1, 1),
        gvalues=E20GValueFields(3, sha256_text("per-depth"), 8, 2),
        detector=_detector(),
    )


def _no_eligible_row() -> E20OutcomeRow:
    values = _common_groups()
    text_hash = sha256_text("source text")
    return E20OutcomeRow.create(
        **values,
        text=E20TextFields(text_hash, text_hash, 100, 100, 20, 20, 10, 10),
        transform=E20TransformFields(
            sha256_text("ruleset"),
            SchedulePolicy.RANDOM_VALID,
            11,
            2,
            "edit-cost",
            0,
            sha256_text("candidate-pool"),
            sha256_text("scheduler-input"),
            sha256_text("schedule-result-noop"),
            sha256_text("operation-trace-noop"),
            False,
        ),
        fidelity=E20FidelityFields(
            True,
            (ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM,),
            0,
            0,
            0,
            E20HumanFidelityStatus.NOT_SELECTED,
            None,
        ),
        observation=E20ObservationFields(8, 8, 8, 0, 0, 0, 1, 1),
        gvalues=E20GValueFields(3, sha256_text("per-depth-noop"), 8, 0),
        detector=_detector(0.8, 0.8),
    )


def test_changed_e20_outcome_exposes_primary_mechanistic_metrics() -> None:
    row = _changed_row()
    assert row.observation_replacement_ratio == 3 / 8
    assert row.standardized_margin_drop == 4.0
    assert row.decision_loss is True


def test_no_eligible_transform_is_a_complete_unchanged_policy_row() -> None:
    row = _no_eligible_row()
    assert row.transform.eligible is False
    assert row.text.source_text_hash == row.text.transformed_text_hash
    assert row.observation.replaced_count == 0
    assert row.gvalues.hamming_difference_count == 0
    assert row.detector.pristine_decision == row.detector.transformed_decision


def test_no_eligible_transform_rejects_hidden_gvalue_drift() -> None:
    row = _no_eligible_row()
    with pytest.raises(ValueError, match="g-value geometry"):
        E20OutcomeRow.create(
            identity=row.identity,
            source=row.source,
            model=row.model,
            watermark=row.watermark,
            generation=row.generation,
            text=row.text,
            transform=row.transform,
            fidelity=row.fidelity,
            alignment=row.alignment,
            observation=row.observation,
            gvalues=E20GValueFields(3, sha256_text("bad-g"), 8, 1),
            detector=row.detector,
            statistics=row.statistics,
            audit=row.audit,
        )


def test_detector_decision_must_replay_fixed_threshold_semantics() -> None:
    with pytest.raises(ValueError, match="transformed_decision"):
        E20DetectorFields(
            DetectorFamily.MEAN,
            sha256_text("detector-config"),
            None,
            sha256_text("calibration-bundle"),
            sha256_text("threshold"),
            ComparisonOperator.GREATER_THAN_OR_EQUAL,
            0.01,
            0.5,
            0.1,
            0.8,
            0.4,
            3.0,
            -1.0,
            True,
            True,
        )


def test_detector_margin_must_replay_score_threshold_and_scale() -> None:
    with pytest.raises(ValueError, match="transformed_standardized_margin"):
        E20DetectorFields(
            DetectorFamily.MEAN,
            sha256_text("detector-config"),
            None,
            sha256_text("calibration-bundle"),
            sha256_text("threshold"),
            ComparisonOperator.GREATER_THAN_OR_EQUAL,
            0.01,
            0.5,
            0.1,
            0.8,
            0.4,
            3.0,
            -0.5,
            True,
            False,
        )


def test_e20_outcome_rejects_generation_token_count_drift() -> None:
    row = _changed_row()
    with pytest.raises(ValueError, match="generated continuation length"):
        E20OutcomeRow.create(
            identity=row.identity,
            source=row.source,
            model=row.model,
            watermark=row.watermark,
            generation=replace(row.generation, realized_length=9),
            text=row.text,
            transform=row.transform,
            fidelity=row.fidelity,
            alignment=row.alignment,
            observation=row.observation,
            gvalues=row.gvalues,
            detector=row.detector,
            statistics=row.statistics,
            audit=row.audit,
        )


def test_e20_outcome_rejects_gvalue_alignment_count_drift() -> None:
    row = _changed_row()
    with pytest.raises(ValueError, match="matched observation count"):
        E20OutcomeRow.create(
            identity=row.identity,
            source=row.source,
            model=row.model,
            watermark=row.watermark,
            generation=row.generation,
            text=row.text,
            transform=row.transform,
            fidelity=row.fidelity,
            alignment=row.alignment,
            observation=row.observation,
            gvalues=E20GValueFields(3, sha256_text("bad-match"), 7, 2),
            detector=row.detector,
            statistics=row.statistics,
            audit=row.audit,
        )


def test_failure_row_reason_code_must_match_failure_stage() -> None:
    identity = _identity()
    audit = _audit()
    row = E20FailureRow.create(
        identity,
        E20FailureStage.TOKENIZATION,
        ExperimentReasonCode.TOKENIZATION_FAILURE,
        sha256_text("source-record"),
        sha256_text("failure-detail"),
        audit,
    )
    assert row.reason_code is ExperimentReasonCode.TOKENIZATION_FAILURE
    with pytest.raises(ValueError, match="required failure stage"):
        E20FailureRow.create(
            identity,
            E20FailureStage.DETECTOR,
            ExperimentReasonCode.SOURCE_PIN_MISMATCH,
            sha256_text("source-record"),
            sha256_text("failure-detail"),
            audit,
        )


def test_failure_row_cannot_hide_no_eligible_policy_row() -> None:
    with pytest.raises(ValueError, match="complete outcome reason codes"):
        E20FailureRow.create(
            _identity(),
            E20FailureStage.TRANSFORM,
            ExperimentReasonCode.NO_ELIGIBLE_TRANSFORM,
            sha256_text("source-record"),
            sha256_text("detail"),
            _audit(),
        )


def test_reason_code_catalog_matches_frozen_spec() -> None:
    assert tuple(value.value for value in ExperimentReasonCode) == (
        "OK",
        "NO_ELIGIBLE_TRANSFORM",
        "REALIZED_BUDGET_EXCEEDED",
        "PROTECTED_SPAN_CONFLICT",
        "HARD_INVARIANT_FAILURE",
        "ALIGNMENT_AMBIGUOUS",
        "TOKENIZATION_FAILURE",
        "GENERATION_EARLY_EOS",
        "DETECTOR_SCORE_NA",
        "ZERO_VALID_OBSERVATIONS",
        "CALIBRATION_MISSING",
        "SOURCE_PIN_MISMATCH",
        "SEALED_KEY_CONTAMINATION",
        "HUMAN_FIDELITY_MATERIAL_CHANGE",
        "UPSTREAM_API_CHANGED",
        "EXTERNAL_INTERFACE_UNAVAILABLE",
    )


def test_audit_timestamp_must_be_real_utc_time_not_regex_only() -> None:
    with pytest.raises(ValueError):
        E20AuditFields(
            "worker-v1",
            "2026-99-99T20:00:00Z",
            sha256_text("env"),
            sha256_text("auth"),
            sha256_text("ledger"),
            (sha256_text("artifact"),),
        )
