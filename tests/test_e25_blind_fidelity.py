from dataclasses import replace
from functools import lru_cache

import pytest

from test_e20_human_audit import _apply_audit as _apply_e20_audit
from test_e20_human_audit import _audit_for_selection as _e20_audit_for_selection
from test_e20_human_audit import _partial_outcome_bundle
from test_e21_outcome import _fixture as _e21_outcome_fixture

from fuckmark.experiments.e20_bundle import _compatible_condition_ids, build_e20_result_bundle
from fuckmark.experiments.e20_human_audit import build_e20_human_audit_selection
from fuckmark.experiments.e20_rows import E20FidelityFields, E20HumanFidelityStatus, ExperimentReasonCode
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_failure_verification import build_e21_failure_row
from fuckmark.experiments.e21_human_audit_v2 import build_e21_human_audit_selection
from fuckmark.experiments.e21_outcome import build_e21_outcome_row
from fuckmark.experiments.e21_rows import E21FailureStage, E21OutcomeRow
from fuckmark.experiments.e25_blind_fidelity import (
    E25BlindFidelityReport,
    build_e25_blind_fidelity_report,
    verify_e25_blind_fidelity_report,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import BlindReviewJudgment, FidelityLabel, FidelityReviewSample, create_blind_human_fidelity_audit


@lru_cache(maxsize=1)
def _reviewed_e20():
    authorization, preregistration, manifest, condition_plan, bundle, remaining_failures = _partial_outcome_bundle()
    selection = build_e20_human_audit_selection(bundle, preregistration, manifest, condition_plan)
    audit = _e20_audit_for_selection(selection, preregistration, manifest)
    reviewed_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        manifest,
        condition_plan,
        _apply_e20_audit(bundle.outcome_rows, condition_plan, selection, audit),
        remaining_failures,
    )
    return authorization, preregistration, manifest, condition_plan, reviewed_bundle, selection, audit


@lru_cache(maxsize=1)
def _reviewed_e21():
    artifacts = _e21_outcome_fixture()
    authorization = artifacts["authorization"]
    ledger = artifacts["ledger"]
    preregistration = artifacts["preregistration"]
    manifest = artifacts["corpus_manifest"]
    condition_plan = artifacts["condition_plan"]
    chosen_sample = artifacts["source_sample"]
    chosen_condition_id = artifacts["condition_id"]
    outcome = build_e21_outcome_row(**artifacts)
    failures = []
    for sample in manifest.samples:
        for condition_id in _compatible_condition_ids(
            preregistration,
            condition_plan,
            sample.watermark.watermark_config_hash,
        ):
            if sample.sample_id == chosen_sample.sample_id and condition_id == chosen_condition_id:
                continue
            failures.append(
                build_e21_failure_row(
                    authorization,
                    ledger,
                    preregistration,
                    condition_plan,
                    manifest,
                    sample,
                    condition_id=condition_id,
                    stage=E21FailureStage.TOKENIZATION,
                    reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
                    detail_hash=sha256_text(f"e25-e21-tokenization:{sample.sample_id}:{condition_id}"),
                    timestamp_utc="2026-08-16T21:21:00Z",
                )
            )
    bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (outcome,),
        tuple(failures),
    )
    selection = build_e21_human_audit_selection(bundle, preregistration, manifest, condition_plan)
    assert selection.unique_selected_transform_count == 1
    entry = selection.entries[0]
    review = FidelityReviewSample.create(
        preregistration.transform_ruleset_hash,
        entry.review_sample_id,
        chosen_sample.text,
        artifacts["transform_result"].output_text,
    )
    audit = create_blind_human_fidelity_audit(
        preregistration.transform_ruleset_hash,
        (review,),
        (
            BlindReviewJudgment.create(review, "reviewer-a", FidelityLabel.EQUIVALENT_OR_MINOR),
            BlindReviewJudgment.create(review, "reviewer-b", FidelityLabel.EQUIVALENT_OR_MINOR),
        ),
    )
    adjudication = audit.adjudications[0]
    fidelity = E20FidelityFields(
        True,
        outcome.fidelity.reason_codes,
        outcome.fidelity.char_edit_distance,
        outcome.fidelity.word_edit_distance,
        outcome.fidelity.token_edit_distance,
        E20HumanFidelityStatus.EQUIVALENT_OR_MINOR,
        adjudication.adjudication_hash,
    )
    reviewed_outcome = E21OutcomeRow.create(
        outcome.identity,
        outcome.source,
        outcome.model,
        outcome.watermark,
        outcome.generation,
        outcome.text,
        outcome.transform,
        fidelity,
        outcome.alignment,
        outcome.observation,
        outcome.gvalues,
        outcome.detector,
        outcome.statistics,
        outcome.audit,
    )
    reviewed_bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (reviewed_outcome,),
        tuple(failures),
    )
    assert build_e21_human_audit_selection(reviewed_bundle, preregistration, manifest, condition_plan) == selection
    return authorization, ledger, preregistration, manifest, condition_plan, reviewed_bundle, selection, audit


def _report_fixture():
    e20_authorization, preregistration, e20_manifest, condition_plan, e20_bundle, e20_selection, e20_audit = _reviewed_e20()
    e21_authorization, e21_ledger, e21_preregistration, e21_manifest, e21_condition_plan, e21_bundle, e21_selection, e21_audit = _reviewed_e21()
    assert e21_preregistration.preregistration_hash == preregistration.preregistration_hash
    assert e21_condition_plan.plan_hash == condition_plan.plan_hash
    args = (
        preregistration,
        condition_plan,
        e20_bundle,
        e20_authorization,
        e20_manifest,
        e20_selection,
        e20_audit,
        e21_bundle,
        e21_authorization,
        e21_ledger,
        e21_manifest,
        e21_selection,
        e21_audit,
    )
    return build_e25_blind_fidelity_report(*args), args


def test_e25_consolidates_two_source_verified_blind_audits() -> None:
    report, args = _report_fixture()
    assert isinstance(report, E25BlindFidelityReport)
    assert report.e20.reviewed_transform_count == 20
    assert report.e21.reviewed_transform_count == 1
    assert report.combined_reviewed_transform_count == 21
    assert report.combined_equivalent_or_minor_count == 21
    assert report.combined_equivalent_or_minor_rate == 1.0
    assert report.overall_gate_passed is False
    assert any(value.selected_count == 0 and value.equivalent_or_minor_rate is None for value in report.e21.cells)
    verify_e25_blind_fidelity_report(report, *args)


def test_e25_does_not_allow_pooled_fidelity_to_override_failed_run_gate() -> None:
    report, _ = _report_fixture()
    assert report.combined_equivalent_or_minor_rate == 1.0
    assert not report.e20.gate_passed
    assert not report.e21.gate_passed
    with pytest.raises(ValueError, match="both independently verified run gates"):
        replace(report, overall_gate_passed=True)
