from __future__ import annotations

from ..adapters import WatermarkAdapter
from ..corpus import CorpusManifest, CorpusSample, TextOnlyTokenRecord
from ..detectors import CalibratedDetectorResult, CalibrationBundle, UncalibratedDetectorEvidence
from ..native_observations import NativeObservationBatch
from ..transforms import KeyBlindScheduleInput, ScheduleResult
from ..transforms.trace import TransformResult
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization, E20RunLedger
from .e20_row_verification import (
    E20_ALIGNMENT_ALGORITHM_VERSION,
    E20_ROW_REPLAY_ALGORITHM_VERSION,
    E20_TEXT_METRIC_ALGORITHM_VERSION,
    E20RowVerificationError,
    build_e20_outcome_row as _build_e20_outcome_row,
    verify_e20_outcome_row as _verify_e20_outcome_row,
)
from .e20_rows import E20HumanFidelityStatus, E20OutcomeRow


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
) -> E20OutcomeRow:
    _require_condition_bundle(condition_plan, condition_id, calibration_bundle)
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
) -> None:
    _require_condition_bundle(condition_plan, condition_id, calibration_bundle)
    _verify_e20_outcome_row(
        row,
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


__all__ = [
    "E20_ALIGNMENT_ALGORITHM_VERSION",
    "E20_ROW_REPLAY_ALGORITHM_VERSION",
    "E20_TEXT_METRIC_ALGORITHM_VERSION",
    "E20RowVerificationError",
    "build_e20_outcome_row",
    "verify_e20_outcome_row",
]
