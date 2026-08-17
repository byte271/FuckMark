from dataclasses import replace
from functools import lru_cache

import pytest

from test_e20_aggregate import _decision
from test_e20_human_audit import _apply_audit as _apply_e20_audit
from test_e20_human_audit import _audit_for_selection as _audit_for_selection
from test_e20_human_audit import _partial_outcome_bundle
from test_e21_bundle import _fixture as _e21_bundle_fixture

from fuckmark.corpus import WatermarkLabel
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_human_audit import build_e20_human_audit_selection
from fuckmark.experiments.e20_rows import E20FidelityFields, E20HumanFidelityStatus, ExperimentReasonCode
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_human_audit_v2 import build_e21_human_audit_selection
from fuckmark.experiments.e21_rows import (
    E21AlignmentFields,
    E21AuditFields,
    E21DetectorFields,
    E21FidelityFields,
    E21GValueFields,
    E21GenerationFields,
    E21HumanFidelityStatus,
    E21IdentityFields,
    E21ModelFields,
    E21ObservationFields,
    E21OutcomeRow,
    E21SourceFields,
    E21StatisticsFields,
    E21TextFields,
    E21TransformFields,
    E21WatermarkFields,
)
from fuckmark.experiments.e21_seed import derive_e21_condition_seed
from fuckmark.experiments.e25_blind_fidelity import E25BlindFidelityReport, build_e25_blind_fidelity_report, verify_e25_blind_fidelity_report
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.transforms import BlindReviewJudgment, FidelityLabel, FidelityReviewSample, create_blind_human_fidelity_audit


@lru_cache(maxsize=1)
def _reviewed_e20():
    authorization, preregistration, manifest, condition_plan, bundle, remaining_failures = _partial_outcome_bundle()
    selection = build_e20_human_audit_selection(bundle, preregistration, manifest, condition_plan)
    audit = _audit_for_selection(selection, preregistration, manifest)
    reviewed_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        manifest,
        condition_plan,
        _apply_e20_audit(bundle.outcome_rows, condition_plan, selection, audit),
        remaining_failures,
    )
    return authorization, preregistration, manifest, condition_plan, reviewed_bundle, selection, audit


def _e21_outcome_for(authorization, preregistration, manifest, condition, sample, failure):
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
    schedule_seed = derive_e21_condition_seed(
        authorization,
        manifest,
        sample.sample_id,
        condition.transform_condition_id,
        "schedule",
    )
    detector_config_hash = bundle.detector_identity.detector_config_hash
    return E21OutcomeRow.create(
        E21IdentityFields(
            authorization.execution_id,
            authorization.execution_id,
            "E21",
            condition.condition_id,
            sample.sample_id,
            sample.match_id,
        ),
        E21SourceFields(track.adapter_id, track.source_pin.commit, track.adapter_config_hash),
        E21ModelFields(sample.model.model_id, sample.model.model_revision, sample.model.tokenizer_id, sample.model.tokenizer_revision),
        E21WatermarkFields(sample.watermark.watermark_config_hash, sample.watermark.key_split, sample.watermark.key_id),
        E21GenerationFields(sample.generation.seed, sample.generation.temperature, sample.generation.top_k, sample.generation.top_p, sample.generation_realized_length),
        E21TextFields(sample.text_sha256, transformed_hash, len(sample.text), max(1, len(sample.text) - 1), len(source_words), len(source_words), len(sample.generation_tokens.continuation_token_ids), len(sample.generation_tokens.continuation_token_ids)),
        E21TransformFields(preregistration.transform_ruleset_hash, condition.schedule_policy, schedule_seed, condition.budget, condition.budget_unit, 1, sha256_text(f"candidate-pool:{sample.sample_id}:{condition.transform_condition_id}"), sha256_text(f"scheduler-input:{sample.sample_id}:{condition.transform_condition_id}"), sha256_text(f"schedule-result:{sample.sample_id}:{condition.transform_condition_id}"), sha256_text(f"operation-trace:{sample.sample_id}:{condition.transform_condition_id}"), True),
        E21FidelityFields(True, (ExperimentReasonCode.OK,), 1, 1, 1, E21HumanFidelityStatus.NOT_SELECTED, None),
        E21AlignmentFields("canonical-token-levenshtein-v1", sha256_text(f"alignment:{sample.sample_id}:{condition.transform_condition_id}"), 0),
        E21ObservationFields(6, 6, 4, 2, 0, 0, 0, 0),
        E21GValueFields(bundle.detector_identity.depth, sha256_text(f"gvalues:{sample.sample_id}:{condition.transform_condition_id}"), 6, min(2, 6 * bundle.detector_identity.depth)),
        E21DetectorFields(bundle.detector_identity.detector_family, detector_config_hash, bundle.detector_identity.checkpoint_hash, bundle.bundle_hash, threshold.threshold_hash, threshold.comparison_operator, condition.target_fpr, threshold.value, bundle.robust_scale, pristine_score, transformed_score, (pristine_score - threshold.value) / bundle.robust_scale, (transformed_score - threshold.value) / bundle.robust_scale, _decision(pristine_score, threshold.value, threshold.comparison_operator), _decision(transformed_score, threshold.value, threshold.comparison_operator)),
        E21StatisticsFields(sha256_json({"model_tokenizer_identity_hash": sample.model.identity_hash, "domain": sample.domain.value, "target_length": sample.target_length, "key_id": sample.watermark.key_id, "detector_config_hash": detector_config_hash, "target_fpr": condition.target_fpr}), sample.sample_id, condition.hypothesis_class),
        E21AuditFields(failure.audit.worker_version, failure.audit.timestamp_utc, failure.audit.environment_snapshot_hash, failure.audit.authorization_hash, failure.audit.ledger_hash, tuple(sorted({sample.record_hash, sha256_text(f"e25-outcome:{sample.sample_id}:{condition.condition_id}")}))),
    )


def _apply_e21_audit(outcomes, condition_plan, selection, audit):
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    selected = {(value.sample_id, value.transform_condition_id): value.review_sample_id for value in selection.entries}
    adjudication_by_id = {value.sample_id: value for value in audit.adjudications}
    updated = []
    for row in outcomes:
        condition = condition_by_id[row.identity.condition_id]
        review_id = selected.get((row.identity.sample_id, condition.transform_condition_id))
        if review_id is None:
            updated.append(row)
            continue
        adjudication = adjudication_by_id[review_id]
        fidelity = E20FidelityFields(True, (ExperimentReasonCode.OK,), row.fidelity.char_edit_distance, row.fidelity.word_edit_distance, row.fidelity.token_edit_distance, E20HumanFidelityStatus.EQUIVALENT_OR_MINOR, adjudication.adjudication_hash)
        updated.append(E21OutcomeRow.create(row.identity, row.source, row.model, row.watermark, row.generation, row.text, row.transform, fidelity, row.alignment, row.observation, row.gvalues, row.detector, row.statistics, row.audit))
    return tuple(updated)


@lru_cache(maxsize=1)
def _reviewed_e21():
    authorization, ledger, preregistration, manifest, condition_plan, failures = _e21_bundle_fixture()
    chosen = condition_plan.conditions[0]
    sample_by_id = {value.sample_id: value for value in manifest.samples}
    chosen_failures = tuple(value for value in failures if value.identity.condition_id == chosen.condition_id)
    outcomes = tuple(_e21_outcome_for(authorization, preregistration, manifest, chosen, sample_by_id[value.identity.sample_id], value) for value in chosen_failures)
    removed = {(value.identity.sample_id, value.identity.condition_id) for value in chosen_failures}
    remaining_failures = tuple(value for value in failures if (value.identity.sample_id, value.identity.condition_id) not in removed)
    bundle = build_e21_result_bundle(authorization, ledger, preregistration, manifest, condition_plan, outcomes, remaining_failures)
    selection = build_e21_human_audit_selection(bundle, preregistration, manifest, condition_plan)
    assert selection.unique_selected_transform_count == 20
    review_samples = []
    judgments = []
    entries = {}
    for value in selection.entries:
        entries.setdefault(value.review_sample_id, value)
    for review_id, entry in sorted(entries.items()):
        sample = sample_by_id[entry.sample_id]
        review = FidelityReviewSample.create(preregistration.transform_ruleset_hash, review_id, sample.text, f"transformed:{entry.sample_id}:{entry.transform_condition_id}")
        review_samples.append(review)
        judgments.append(BlindReviewJudgment.create(review, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR))
        judgments.append(BlindReviewJudgment.create(review, "reviewer-b", FidelityLabel.EQUIVALENT_OR_MINOR))
    audit = create_blind_human_fidelity_audit(preregistration.transform_ruleset_hash, tuple(review_samples), tuple(judgments))
    reviewed_bundle = build_e21_result_bundle(authorization, ledger, preregistration, manifest, condition_plan, _apply_e21_audit(bundle.outcome_rows, condition_plan, selection, audit), remaining_failures)
    assert build_e21_human_audit_selection(reviewed_bundle, preregistration, manifest, condition_plan) == selection
    return authorization, ledger, preregistration, manifest, condition_plan, reviewed_bundle, selection, audit


def _report_fixture():
    e20_authorization, preregistration, e20_manifest, condition_plan, e20_bundle, e20_selection, e20_audit = _reviewed_e20()
    e21_authorization, e21_ledger, e21_preregistration, e21_manifest, e21_condition_plan, e21_bundle, e21_selection, e21_audit = _reviewed_e21()
    assert e21_preregistration.preregistration_hash == preregistration.preregistration_hash
    assert e21_condition_plan.plan_hash == condition_plan.plan_hash
    args = (preregistration, condition_plan, e20_bundle, e20_authorization, e20_manifest, e20_selection, e20_audit, e21_bundle, e21_authorization, e21_ledger, e21_manifest, e21_selection, e21_audit)
    return build_e25_blind_fidelity_report(*args), args


def test_e25_consolidates_two_source_verified_blind_audits() -> None:
    report, args = _report_fixture()
    assert isinstance(report, E25BlindFidelityReport)
    assert report.e20.reviewed_transform_count == 20
    assert report.e21.reviewed_transform_count == 20
    assert report.combined_reviewed_transform_count == 40
    assert report.combined_equivalent_or_minor_count == 40
    assert report.combined_equivalent_or_minor_rate == 1.0
    assert report.overall_gate_passed is False
    assert all(value.quartile_selected_counts == (2, 1, 1, 1) for value in report.e20.cells)
    assert all(value.quartile_selected_counts == (2, 1, 1, 1) for value in report.e21.cells)
    verify_e25_blind_fidelity_report(report, *args)


def test_e25_does_not_allow_pooled_fidelity_to_override_failed_run_gate() -> None:
    report, _ = _report_fixture()
    assert report.combined_equivalent_or_minor_rate == 1.0
    assert not report.e20.gate_passed
    assert not report.e21.gate_passed
    with pytest.raises(ValueError, match="both independently verified run gates"):
        replace(report, overall_gate_passed=True)
