from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture

from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_key_analysis import (
    E20KeyEffectStatus,
    build_e20_key_analysis_bundle,
    verify_e20_key_analysis_bundle,
)


def test_key_analysis_reports_failure_only_keys_without_fabricating_effects() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    key_bundle = build_e20_key_analysis_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    for summary in key_bundle.summaries:
        assert summary.complete_key_count == 0
        assert summary.incomplete_key_count == len(summary.effects)
        assert summary.tpr_change_mean is None
        assert summary.margin_drop_mean is None
        for effect in summary.effects:
            assert effect.status is E20KeyEffectStatus.NO_ANALYSABLE_ROWS
            assert effect.tpr_change is None
    verify_e20_key_analysis_bundle(
        key_bundle,
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )


def test_key_analysis_reports_key_level_effect_instead_of_hiding_key_distribution() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    chosen = condition_plan.conditions[0]
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
    key_bundle = build_e20_key_analysis_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    summary = next(value for value in key_bundle.summaries if value.condition_id == chosen.condition_id)
    assert summary.complete_key_count == 1
    assert summary.incomplete_key_count == 0
    assert len(summary.effects) == 1
    effect = summary.effects[0]
    assert effect.status is E20KeyEffectStatus.COMPLETE
    assert effect.pristine_tpr == 1.0
    assert effect.transformed_tpr == 0.0
    assert effect.tpr_change == -1.0
    assert summary.tpr_change_mean == -1.0
    assert summary.tpr_change_sd == 0.0
    assert summary.tpr_change_iqr == 0.0
