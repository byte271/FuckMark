from __future__ import annotations

from ..adapters import WatermarkAdapter
from ..corpus import CorpusManifest, CorpusSample, TextOnlyTokenRecord
from ..detectors import (
    CalibratedDetectorResult,
    CalibrationBundle,
    DetectorFamily,
    UncalibratedDetectorEvidence,
)
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..native_observations import NativeObservationBatch
from ..transforms import KeyBlindScheduleInput, ScheduleResult
from ..transforms.trace import TransformResult
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_outcome_replay import (
    ConfirmatoryOutcomeReplayError,
    build_confirmatory_outcome_fields,
)
from .e20_conditions import E20ConditionPlan
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    E20RunState,
    derive_e20_condition_seed,
    verify_e20_run_ledger,
)
from .e20_row_verification import (
    E20_ALIGNMENT_ALGORITHM_VERSION,
    E20_ROW_REPLAY_ALGORITHM_VERSION,
    E20_TEXT_METRIC_ALGORITHM_VERSION,
    E20RowVerificationError,
    build_e20_outcome_row as _build_e20_outcome_row,
)
from .e20_rows import E20HumanFidelityStatus, E20IdentityFields, E20OutcomeRow


def _require_condition_bundle(
    condition_plan: E20ConditionPlan,
    condition_id: str,
    calibration_bundle: CalibrationBundle,
) -> None:
    if not isinstance(condition_plan, E20ConditionPlan):
        raise TypeError("condition_plan must be an E20ConditionPlan")
    if not isinstance(calibration_bundle, CalibrationBundle):
        raise TypeError("calibration_bundle must be a CalibrationBundle")
    condition = condition_plan.condition(condition_id)
    if condition.calibration_bundle_hash != calibration_bundle.bundle_hash:
        raise E20RowVerificationError(
            "runtime calibration bundle does not match the detector bundle frozen in the E20 condition"
        )


def _require_generation_track(
    preregistration: ConfirmatoryPreregistration,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    calibration_bundle: CalibrationBundle,
) -> None:
    try:
        track = preregistration.watermark_tracks.track_for(
            source_sample.watermark.watermark_config_hash
        )
    except KeyError as error:
        raise E20RowVerificationError(
            "source sample watermark configuration is outside the sealed generation tracks"
        ) from error
    if (
        adapter.adapter_id != track.adapter_id
        or adapter.algorithm_version != track.adapter_algorithm_version
        or adapter.configuration_fingerprint() != track.adapter_config_hash
        or adapter.source_pin.source_id != track.source_pin.source_id
        or adapter.source_pin.commit != track.source_pin.commit
    ):
        raise E20RowVerificationError(
            "observation adapter does not match the source sample sealed generation track"
        )
    if not track.matches_detector_identity(calibration_bundle.detector_identity):
        raise E20RowVerificationError(
            "runtime detector bundle is not source/config compatible with the source sample generation track"
        )


def _preflight(
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    calibration_bundle: CalibrationBundle,
    condition_id: str,
) -> None:
    _require_condition_bundle(condition_plan, condition_id, calibration_bundle)
    _require_generation_track(preregistration, source_sample, adapter, calibration_bundle)


def _build_bayesian_e20_outcome_row(
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    calibration_bundle: CalibrationBundle,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    *,
    condition_id: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus,
    human_adjudication_hash: str | None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None,
) -> E20OutcomeRow:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(ledger, E20RunLedger):
        raise TypeError("ledger must be an E20RunLedger")
    verify_e20_run_ledger(ledger, authorization)
    if ledger.state is not E20RunState.STARTED:
        raise E20RowVerificationError(
            "E20 outcome rows may be built only while the sealed run is STARTED"
        )
    expected_seed = derive_e20_condition_seed(
        authorization,
        corpus_manifest,
        source_sample.sample_id,
        condition_plan.condition(condition_id).transform_condition_id,
        "schedule",
    )
    try:
        fields = build_confirmatory_outcome_fields(
            preregistration,
            condition_plan,
            corpus_manifest,
            authorization.corpus_manifest_hash,
            source_sample,
            adapter,
            transformed_tokens,
            schedule_input,
            schedule_result,
            transform_result,
            original_batch,
            transformed_batch,
            original_evidence,
            transformed_evidence,
            calibration_bundle,
            original_detector_result,
            transformed_detector_result,
            condition_id=condition_id,
            expected_schedule_seed=expected_seed,
            worker_version=authorization.worker_version,
            environment_snapshot_hash=authorization.environment_snapshot_hash,
            authorization_hash=authorization.authorization_hash,
            ledger_hash=ledger.ledger_hash,
            timestamp_utc=timestamp_utc,
            human_status=human_status,
            human_adjudication_hash=human_adjudication_hash,
            bayesian_artifacts=bayesian_artifacts,
        )
    except ConfirmatoryOutcomeReplayError as error:
        raise E20RowVerificationError(str(error)) from error
    identity = E20IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E20",
        condition_id,
        source_sample.sample_id,
        source_sample.match_id,
    )
    return E20OutcomeRow.create(identity, *fields)


def build_e20_outcome_row(
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    calibration_bundle: CalibrationBundle,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    *,
    condition_id: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus = E20HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> E20OutcomeRow:
    _preflight(
        preregistration,
        condition_plan,
        source_sample,
        adapter,
        calibration_bundle,
        condition_id,
    )
    if original_evidence.detector_family is DetectorFamily.BAYESIAN:
        return _build_bayesian_e20_outcome_row(
            authorization,
            ledger,
            preregistration,
            condition_plan,
            corpus_manifest,
            source_sample,
            adapter,
            transformed_tokens,
            schedule_input,
            schedule_result,
            transform_result,
            original_batch,
            transformed_batch,
            original_evidence,
            transformed_evidence,
            calibration_bundle,
            original_detector_result,
            transformed_detector_result,
            condition_id=condition_id,
            timestamp_utc=timestamp_utc,
            human_status=human_status,
            human_adjudication_hash=human_adjudication_hash,
            bayesian_artifacts=bayesian_artifacts,
        )
    if bayesian_artifacts is not None:
        raise E20RowVerificationError(
            "non-Bayesian E20 outcome rows cannot carry Bayesian readiness artifacts"
        )
    return _build_e20_outcome_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        corpus_manifest,
        source_sample,
        adapter,
        transformed_tokens,
        schedule_input,
        schedule_result,
        transform_result,
        original_batch,
        transformed_batch,
        original_evidence,
        transformed_evidence,
        calibration_bundle,
        original_detector_result,
        transformed_detector_result,
        condition_id=condition_id,
        timestamp_utc=timestamp_utc,
        human_status=human_status,
        human_adjudication_hash=human_adjudication_hash,
    )


def verify_e20_outcome_row(
    row: E20OutcomeRow,
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    adapter: WatermarkAdapter,
    transformed_tokens: TextOnlyTokenRecord,
    schedule_input: KeyBlindScheduleInput,
    schedule_result: ScheduleResult,
    transform_result: TransformResult,
    original_batch: NativeObservationBatch,
    transformed_batch: NativeObservationBatch,
    original_evidence: UncalibratedDetectorEvidence,
    transformed_evidence: UncalibratedDetectorEvidence,
    calibration_bundle: CalibrationBundle,
    original_detector_result: CalibratedDetectorResult,
    transformed_detector_result: CalibratedDetectorResult,
    *,
    condition_id: str,
    timestamp_utc: str,
    human_status: E20HumanFidelityStatus = E20HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> None:
    if not isinstance(row, E20OutcomeRow):
        raise TypeError("row must be an E20OutcomeRow")
    expected = build_e20_outcome_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        corpus_manifest,
        source_sample,
        adapter,
        transformed_tokens,
        schedule_input,
        schedule_result,
        transform_result,
        original_batch,
        transformed_batch,
        original_evidence,
        transformed_evidence,
        calibration_bundle,
        original_detector_result,
        transformed_detector_result,
        condition_id=condition_id,
        timestamp_utc=timestamp_utc,
        human_status=human_status,
        human_adjudication_hash=human_adjudication_hash,
        bayesian_artifacts=bayesian_artifacts,
    )
    if row != expected:
        raise E20RowVerificationError(
            "E20 outcome row does not replay exactly from sealed source artifacts"
        )


__all__ = [
    "E20_ALIGNMENT_ALGORITHM_VERSION",
    "E20_ROW_REPLAY_ALGORITHM_VERSION",
    "E20_TEXT_METRIC_ALGORITHM_VERSION",
    "E20RowVerificationError",
    "build_e20_outcome_row",
    "verify_e20_outcome_row",
]
