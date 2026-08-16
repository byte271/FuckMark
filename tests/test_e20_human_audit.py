from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture
from fuckmark.corpus import WatermarkLabel
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_human_audit import (
    build_e20_human_audit_selection,
    verify_e20_human_audit_evidence,
    verify_e20_human_audit_selection,
)
from fuckmark.experiments.e20_report import _human_fidelity_summary
from fuckmark.experiments.e20_rows import (
    E20FidelityFields,
    E20HumanFidelityStatus,
    E20OutcomeRow,
    ExperimentReasonCode,
)
from fuckmark.transforms import (
    BlindReviewJudgment,
    FidelityLabel,
    FidelityReviewSample,
    create_blind_human_fidelity_audit,
)


def _partial_outcome_bundle():
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
    bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        outcomes,
        remaining_failures,
    )
    return authorization, preregistration, corpus_manifest, condition_plan, bundle, remaining_failures


def _audit_for_selection(selection, preregistration, corpus_manifest):
    sample_by_id = {value.sample_id: value for value in corpus_manifest.samples}
    entries = {}
    for value in selection.entries:
        entries.setdefault(value.review_sample_id, value)
    review_samples = []
    judgments = []
    for review_id, entry in sorted(entries.items()):
        sample = sample_by_id[entry.sample_id]
        transformed_text = f"transformed:{entry.sample_id}:{entry.transform_condition_id}"
        review = FidelityReviewSample.create(
            preregistration.transform_ruleset_hash,
            review_id,
            sample.text,
            transformed_text,
        )
        review_samples.append(review)
        judgments.append(
            BlindReviewJudgment.create(
                review,
                "reviewer-a",
                FidelityLabel.EQUIVALENT_OR_MINOR,
            )
        )
        judgments.append(
            BlindReviewJudgment.create(
                review,
                "reviewer-b",
                FidelityLabel.EQUIVALENT_OR_MINOR,
            )
        )
    return create_blind_human_fidelity_audit(
        preregistration.transform_ruleset_hash,
        tuple(review_samples),
        tuple(judgments),
    )


def _apply_audit(outcomes, condition_plan, selection, audit):
    condition_by_id = {value.condition_id: value for value in condition_plan.conditions}
    selected = {
        (value.sample_id, value.transform_condition_id): value.review_sample_id
        for value in selection.entries
    }
    adjudication_by_id = {value.sample_id: value for value in audit.adjudications}
    updated = []
    for row in outcomes:
        condition = condition_by_id[row.identity.condition_id]
        review_id = selected.get((row.identity.sample_id, condition.transform_condition_id))
        if review_id is None:
            updated.append(row)
            continue
        adjudication = adjudication_by_id[review_id]
        fidelity = E20FidelityFields(
            True,
            (ExperimentReasonCode.OK,),
            row.fidelity.char_edit_distance,
            row.fidelity.word_edit_distance,
            row.fidelity.token_edit_distance,
            E20HumanFidelityStatus.EQUIVALENT_OR_MINOR,
            adjudication.adjudication_hash,
        )
        updated.append(
            E20OutcomeRow.create(
                row.identity,
                row.source,
                row.model,
                row.watermark,
                row.generation,
                row.text,
                row.transform,
                fidelity,
                row.alignment,
                row.observation,
                row.gvalues,
                row.detector,
                row.statistics,
                row.audit,
            )
        )
    return tuple(updated)


def test_human_audit_selection_is_cell_stratified_and_label_blind() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, bundle, remaining_failures = _partial_outcome_bundle()
    selection = build_e20_human_audit_selection(
        bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    assert len(selection.cells) == 4
    assert selection.unique_selected_transform_count == 20
    assert all(value.candidate_count == 5 for value in selection.cells)
    assert all(value.selected_count == 5 for value in selection.cells)
    assert all(value.quartile_candidate_counts == (2, 1, 1, 1) for value in selection.cells)
    assert all(value.quartile_selected_counts == (2, 1, 1, 1) for value in selection.cells)
    assert all(
        next(
            sample
            for sample in corpus_manifest.samples
            if sample.sample_id == entry.sample_id
        ).label
        is WatermarkLabel.WATERMARKED
        for entry in selection.entries
    )
    verify_e20_human_audit_selection(
        selection,
        bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    audit = _audit_for_selection(selection, preregistration, corpus_manifest)
    reviewed_outcomes = _apply_audit(bundle.outcome_rows, condition_plan, selection, audit)
    reviewed_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        reviewed_outcomes,
        remaining_failures,
    )
    replayed = build_e20_human_audit_selection(
        reviewed_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    assert replayed == selection
    verify_e20_human_audit_evidence(
        selection,
        audit,
        reviewed_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    summary = _human_fidelity_summary(
        reviewed_bundle,
        condition_plan,
        preregistration,
        corpus_manifest,
        selection,
        audit,
    )
    assert summary.audit_verified is True
    assert summary.selection_hash == selection.selection_hash
    assert summary.audit_hash == audit.audit_hash
    assert summary.reviewed_transform_count == 20
    assert summary.gate_passed is False


def test_human_fidelity_gate_fails_closed_without_replayed_selection_evidence() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, bundle, remaining_failures = _partial_outcome_bundle()
    selection = build_e20_human_audit_selection(
        bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
    )
    audit = _audit_for_selection(selection, preregistration, corpus_manifest)
    reviewed_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        _apply_audit(bundle.outcome_rows, condition_plan, selection, audit),
        remaining_failures,
    )
    summary = _human_fidelity_summary(
        reviewed_bundle,
        condition_plan,
        preregistration,
    )
    assert summary.reviewed_transform_count == 20
    assert summary.audit_verified is False
    assert summary.selection_hash is None
    assert summary.audit_hash is None
    assert summary.gate_passed is False
