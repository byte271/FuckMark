from test_e21_bundle import _fixture
from fuckmark.experiments.e20_inference import E20InferenceStatus
from fuckmark.experiments.e21_analysis import (
    build_e21_headline_evidence,
    build_e21_primary_analysis,
    verify_e21_primary_analysis,
)
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_inference import (
    build_e21_primary_inference,
    verify_e21_primary_inference,
)


def test_e21_primary_analysis_and_inference_replay_from_sealed_failure_population() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    result_bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (),
        failures,
    )
    analysis = build_e21_primary_analysis(
        result_bundle,
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
    )
    verify_e21_primary_analysis(
        analysis,
        result_bundle,
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
    )
    inference = build_e21_primary_inference(
        result_bundle,
        analysis,
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
    )
    verify_e21_primary_inference(
        inference,
        result_bundle,
        analysis,
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
    )
    assert all(value.status is E20InferenceStatus.INCOMPLETE_FAILURE_ROWS for value in inference.inferences)
    evidence = build_e21_headline_evidence(analysis, inference)
    assert {value.condition_id for value in evidence} == {value.condition_id for value in condition_plan.conditions}
    assert all(value.source_result_bundle_hash == result_bundle.bundle_hash for value in evidence)
    assert all(value.headline_eligible is False for value in evidence)
    assert all(value.holm_adjusted_p_value is None for value in evidence)
