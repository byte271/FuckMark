from math import comb, isclose

from test_e20_aggregate import _outcome_for
from test_e20_bundle import _bundle_fixture
from fuckmark.experiments.e20_aggregate import build_e20_aggregate_bundle
from fuckmark.experiments.e20_bundle import build_e20_result_bundle
from fuckmark.experiments.e20_inference import (
    E20InferenceStatus,
    _exact_binomial_two_sided,
    build_e20_inference_bundle,
    verify_e20_inference_bundle,
)


def _chosen_complete_result():
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
    aggregate = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    return authorization, preregistration, corpus_manifest, condition_plan, chosen, result_bundle, aggregate


def test_exact_mcnemar_binomial_two_sided_known_value() -> None:
    assert _exact_binomial_two_sided(0, 10) == 2.0 / (2 ** 10)
    assert _exact_binomial_two_sided(0, 0) == 1.0
    assert _exact_binomial_two_sided(5, 10) == 1.0


def test_exact_mcnemar_binomial_matches_direct_small_reference() -> None:
    expected = 2.0 * sum(comb(100, index) for index in range(41)) / (2 ** 100)
    assert isclose(
        _exact_binomial_two_sided(40, 100),
        expected,
        rel_tol=0.0,
        abs_tol=2e-15,
    )


def test_exact_mcnemar_binomial_remains_finite_at_confirmatory_scale() -> None:
    value = _exact_binomial_two_sided(1800, 4000)
    assert 0.0 < value < 1.0
    assert isclose(value, 2.721567768251934e-10, rel_tol=1e-12, abs_tol=0.0)
    assert _exact_binomial_two_sided(2000, 4000) == 1.0
    assert _exact_binomial_two_sided(0, 4000) > 0.0


def test_inference_uses_paired_decision_changes_and_holm_family_size_without_dropping_failed_cells() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, chosen, result_bundle, aggregate = _chosen_complete_result()
    inference = build_e20_inference_bundle(
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    assert inference.family_size == len(condition_plan.conditions)
    chosen_inference = next(value for value in inference.inferences if value.condition_id == chosen.condition_id)
    assert chosen_inference.status is E20InferenceStatus.COMPLETE
    assert chosen_inference.effect_estimate == -1.0
    expected_raw = 2.0 / (2 ** 20)
    assert isclose(chosen_inference.raw_p_value, expected_raw, rel_tol=0.0, abs_tol=1e-15)
    assert isclose(
        chosen_inference.holm_adjusted_p_value,
        min(1.0, expected_raw * inference.family_size),
        rel_tol=0.0,
        abs_tol=1e-15,
    )
    incomplete = tuple(value for value in inference.inferences if value.condition_id != chosen.condition_id)
    assert incomplete
    assert all(value.status is E20InferenceStatus.INCOMPLETE_FAILURE_ROWS for value in incomplete)
    assert all(value.raw_p_value is None and value.holm_adjusted_p_value is None for value in incomplete)
    verify_e20_inference_bundle(
        inference,
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )


def test_failure_only_result_never_produces_confirmatory_p_values() -> None:
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
    inference = build_e20_inference_bundle(
        result_bundle,
        aggregate,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    assert all(value.status is E20InferenceStatus.INCOMPLETE_FAILURE_ROWS for value in inference.inferences)
    assert all(value.raw_p_value is None for value in inference.inferences)
    assert all(value.holm_adjusted_p_value is None for value in inference.inferences)
