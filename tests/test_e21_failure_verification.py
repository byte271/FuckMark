import pytest

from test_e21_bundle import _fixture
from fuckmark.experiments.e21_failure_verification import (
    E21FailureVerificationError,
    build_e21_failure_row,
    verify_e21_failure_row,
)
from fuckmark.experiments.e21_rows import E21FailureStage
from fuckmark.experiments.e20_rows import ExperimentReasonCode
from fuckmark.hashing import sha256_text


TIMESTAMP = "2026-08-16T21:03:00Z"


def _source_fixture():
    authorization, ledger, preregistration, manifest, condition_plan, _ = _fixture()
    source_sample = manifest.samples[0]
    condition_id = next(
        value.condition_id
        for value in condition_plan.conditions
        if value.calibration_bundle_hash in {
            bundle.bundle_hash
            for bundle in preregistration.calibration_bundles
            if preregistration.watermark_tracks.track_for(
                source_sample.watermark.watermark_config_hash
            ).matches_detector_identity(bundle.detector_identity)
        }
    )
    return authorization, ledger, preregistration, manifest, condition_plan, source_sample, condition_id


def test_e21_failure_row_replays_from_sealed_rerun_sources() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, source_sample, condition_id = _source_fixture()
    detail_hash = sha256_text("e21-source-replay-failure")
    row = build_e21_failure_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        manifest,
        source_sample,
        condition_id=condition_id,
        stage=E21FailureStage.TOKENIZATION,
        reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
        detail_hash=detail_hash,
        timestamp_utc=TIMESTAMP,
    )
    assert row.identity.experiment_id == "E21"
    assert row.source_sample_record_hash == source_sample.record_hash
    verify_e21_failure_row(
        row,
        authorization,
        ledger,
        preregistration,
        condition_plan,
        manifest,
        source_sample,
        condition_id=condition_id,
        stage=E21FailureStage.TOKENIZATION,
        reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
        detail_hash=detail_hash,
        timestamp_utc=TIMESTAMP,
    )


def test_e21_failure_row_rejects_source_detail_drift() -> None:
    authorization, ledger, preregistration, manifest, condition_plan, source_sample, condition_id = _source_fixture()
    detail_hash = sha256_text("e21-source-replay-failure")
    row = build_e21_failure_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        manifest,
        source_sample,
        condition_id=condition_id,
        stage=E21FailureStage.TOKENIZATION,
        reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
        detail_hash=detail_hash,
        timestamp_utc=TIMESTAMP,
    )
    with pytest.raises(E21FailureVerificationError, match="does not replay exactly"):
        verify_e21_failure_row(
            row,
            authorization,
            ledger,
            preregistration,
            condition_plan,
            manifest,
            source_sample,
            condition_id=condition_id,
            stage=E21FailureStage.TOKENIZATION,
            reason_code=ExperimentReasonCode.TOKENIZATION_FAILURE,
            detail_hash=sha256_text("different-e21-failure-detail"),
            timestamp_utc=TIMESTAMP,
        )
