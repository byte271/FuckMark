from __future__ import annotations

from ..adapters import WatermarkAdapter
from ..corpus import CorpusManifest, CorpusSample, TextOnlyTokenRecord
from ..detectors import CalibratedDetectorResult, CalibrationBundle, UncalibratedDetectorEvidence
from ..detectors.bayesian_artifacts import BayesianReadinessArtifactBundle
from ..hashing import sha256_text
from ..native_observations import NativeObservationBatch
from ..transforms import KeyBlindScheduleInput, ScheduleResult
from ..transforms.trace import TransformResult
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_outcome_replay import (
    ConfirmatoryOutcomeReplayError,
    build_confirmatory_outcome_fields,
)
from .e20_conditions import E20ConditionPlan
from .e21_execution import E21RunLedger, E21RunState, verify_e21_run_ledger
from .e21_rerun import E21ExecutionAuthorization
from .e21_rows import (
    E21AuditFields,
    E21HumanFidelityStatus,
    E21IdentityFields,
    E21OutcomeRow,
)
from .e21_seed import derive_e21_condition_seed


E21_ROW_REPLAY_ALGORITHM_VERSION = "e21-row-replay-v1"


class E21RowVerificationError(ValueError):
    pass


def build_e21_outcome_row(
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
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
    human_status: E21HumanFidelityStatus = E21HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> E21OutcomeRow:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    if not isinstance(ledger, E21RunLedger):
        raise TypeError("ledger must be an E21RunLedger")
    verify_e21_run_ledger(ledger, authorization)
    if ledger.state is not E21RunState.STARTED:
        raise E21RowVerificationError(
            "E21 outcome rows may be built only while the sealed rerun is STARTED"
        )
    expected_seed = derive_e21_condition_seed(
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
            authorization.e21_corpus_manifest_hash,
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
        raise E21RowVerificationError(str(error)) from error
    audit = fields[-1]
    audit = E21AuditFields(
        audit.worker_version,
        audit.timestamp_utc,
        audit.environment_snapshot_hash,
        audit.authorization_hash,
        audit.ledger_hash,
        tuple(
            sorted(
                set(audit.artifact_hashes)
                | {sha256_text(E21_ROW_REPLAY_ALGORITHM_VERSION)}
            )
        ),
    )
    fields = (*fields[:-1], audit)
    identity = E21IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E21",
        condition_id,
        source_sample.sample_id,
        source_sample.match_id,
    )
    return E21OutcomeRow.create(identity, *fields)


def verify_e21_outcome_row(
    row: E21OutcomeRow,
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
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
    human_status: E21HumanFidelityStatus = E21HumanFidelityStatus.NOT_SELECTED,
    human_adjudication_hash: str | None = None,
    bayesian_artifacts: BayesianReadinessArtifactBundle | None = None,
) -> None:
    if not isinstance(row, E21OutcomeRow):
        raise TypeError("row must be an E21OutcomeRow")
    expected = build_e21_outcome_row(
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
        raise E21RowVerificationError(
            "E21 outcome row does not replay exactly from sealed source artifacts"
        )
