from dataclasses import replace

import pytest

from test_e20_bundle import _bundle_fixture
from test_e22_transformed_negative import _fixture_rows, _result_bundle
from fuckmark.experiments.e20_bundle import E20ResultBundleError, build_e20_result_bundle
from fuckmark.experiments.e22_transformed_negative import E22AnalysisStatus, build_e22_transformed_negative_report
from fuckmark.experiments.e22_transformed_negative_verified import (
    build_verified_e22_transformed_negative_report,
    verify_verified_e22_transformed_negative_report,
)
from fuckmark.hashing import sha256_text


def test_verified_e22_replays_from_fully_verified_e20_bundle() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )

    verified = build_verified_e22_transformed_negative_report(
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )

    assert verified.authorization_hash == authorization.authorization_hash
    assert verified.preregistration_hash == preregistration.preregistration_hash
    assert verified.report.status is E22AnalysisStatus.NO_ESTIMATE
    assert verified.report.negative_failure_count > 0
    verify_verified_e22_transformed_negative_report(
        verified,
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )


def test_verified_e22_rejects_structurally_hashed_but_unverified_synthetic_bundle() -> None:
    authorization, preregistration, _, _, _ = _bundle_fixture()
    corpus_manifest, condition_plan, _, _, first, second, _ = _fixture_rows()
    synthetic = _result_bundle(corpus_manifest, condition_plan, (first, second))

    raw = build_e22_transformed_negative_report(synthetic, corpus_manifest, condition_plan)
    assert raw.negative_outcome_count == 2

    with pytest.raises(E20ResultBundleError):
        build_verified_e22_transformed_negative_report(
            synthetic,
            authorization,
            preregistration,
            corpus_manifest,
            condition_plan,
        )


def test_verified_e22_hash_binds_authorization_and_preregistration() -> None:
    authorization, preregistration, corpus_manifest, condition_plan, failures = _bundle_fixture()
    result_bundle = build_e20_result_bundle(
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
        (),
        failures,
    )
    verified = build_verified_e22_transformed_negative_report(
        result_bundle,
        authorization,
        preregistration,
        corpus_manifest,
        condition_plan,
    )

    with pytest.raises(ValueError, match="verified_hash"):
        replace(
            verified,
            authorization_hash=sha256_text("different-e22-authorization"),
        )
