import pytest

from test_e21_bundle import _fixture
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.e20_rows import ExperimentReasonCode
from fuckmark.experiments.e21_bundle import build_e21_result_bundle
from fuckmark.experiments.e21_failure_verification import build_e21_failure_row
from fuckmark.experiments.e21_fidelity_summary import (
    E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION,
    E21VerifiedFidelitySummary,
    e21_hard_invariant_failure_count,
)
from fuckmark.experiments.e21_rows import E21FailureStage
from fuckmark.hashing import sha256_json, sha256_text


def test_e21_hard_invariant_failure_count_includes_failure_rows() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, failures = _fixture()
    first = failures[0]
    source_sample = next(
        value for value in manifest.samples if value.sample_id == first.identity.sample_id
    )
    hard_failure = build_e21_failure_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        manifest,
        source_sample,
        condition_id=first.identity.condition_id,
        stage=E21FailureStage.FIDELITY,
        reason_code=ExperimentReasonCode.HARD_INVARIANT_FAILURE,
        detail_hash=sha256_text("e21-hard-invariant-failure"),
        timestamp_utc="2026-08-16T21:03:00Z",
    )
    bundle = build_e21_result_bundle(
        authorization,
        ledger,
        preregistration,
        manifest,
        condition_plan,
        (),
        (hard_failure, *failures[1:]),
    )
    assert e21_hard_invariant_failure_count(bundle) == 1


def test_e21_fidelity_gate_cannot_pass_with_hard_invariant_failure() -> None:
    interval = exact_binomial_interval(50, 50, 0.95)
    payload = {
        "algorithm_version": E21_HUMAN_FIDELITY_SUMMARY_ALGORITHM_VERSION,
        "selection_hash": sha256_text("e21-fidelity-selection"),
        "audit_hash": sha256_text("e21-fidelity-audit"),
        "reviewed_transform_count": 50,
        "equivalent_or_minor_count": 50,
        "material_change_count": 0,
        "cannot_judge_count": 0,
        "hard_invariant_failure_count": 1,
        "equivalent_or_minor_rate": 1.0,
        "equivalent_or_minor_interval": interval,
        "gate_passed": True,
    }
    with pytest.raises(ValueError, match="hard-invariant failure"):
        E21VerifiedFidelitySummary(
            payload["selection_hash"],
            payload["audit_hash"],
            50,
            50,
            0,
            0,
            1,
            1.0,
            interval,
            True,
            sha256_json(payload),
        )
