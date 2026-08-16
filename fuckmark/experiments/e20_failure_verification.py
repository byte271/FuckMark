from __future__ import annotations

from .._validation import require_sha256
from ..corpus import CorpusManifest, CorpusSample
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_execution import (
    E20ExecutionAuthorization,
    E20RunLedger,
    E20RunState,
    verify_e20_run_ledger,
)
from .e20_rows import (
    E20AuditFields,
    E20FailureRow,
    E20FailureStage,
    E20IdentityFields,
    ExperimentReasonCode,
)


E20_FAILURE_REPLAY_ALGORITHM_VERSION = "e20-failure-replay-v1"


class E20FailureVerificationError(ValueError):
    pass


def build_e20_failure_row(
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    *,
    condition_id: str,
    stage: E20FailureStage,
    reason_code: ExperimentReasonCode,
    detail_hash: str,
    timestamp_utc: str,
) -> E20FailureRow:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    if not isinstance(ledger, E20RunLedger):
        raise TypeError("ledger must be an E20RunLedger")
    verify_e20_run_ledger(ledger, authorization)
    if ledger.state is not E20RunState.STARTED:
        raise E20FailureVerificationError(
            "E20 failure rows may be built only while the sealed run is STARTED"
        )
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    verify_e20_condition_plan(condition_plan, preregistration)
    condition = condition_plan.condition(condition_id)
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if corpus_manifest.manifest_hash != authorization.corpus_manifest_hash:
        raise E20FailureVerificationError(
            "corpus manifest does not match E20 authorization"
        )
    if not isinstance(source_sample, CorpusSample):
        raise TypeError("source_sample must be a CorpusSample")
    matches = tuple(
        value for value in corpus_manifest.samples if value.sample_id == source_sample.sample_id
    )
    if len(matches) != 1 or matches[0] != source_sample:
        raise E20FailureVerificationError(
            "source sample does not replay exactly from the authorized corpus manifest"
        )
    if source_sample.model not in preregistration.model_tokenizers:
        raise E20FailureVerificationError(
            "source sample model/tokenizer is not preregistered"
        )
    require_sha256("detail_hash", detail_hash)
    identity = E20IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E20",
        condition.condition_id,
        source_sample.sample_id,
        source_sample.match_id,
    )
    audit = E20AuditFields(
        authorization.worker_version,
        timestamp_utc,
        authorization.environment_snapshot_hash,
        authorization.authorization_hash,
        ledger.ledger_hash,
        tuple(sorted({source_sample.record_hash, detail_hash, condition.condition_hash})),
    )
    return E20FailureRow.create(
        identity,
        stage,
        reason_code,
        source_sample.record_hash,
        detail_hash,
        audit,
    )


def verify_e20_failure_row(
    row: E20FailureRow,
    authorization: E20ExecutionAuthorization,
    ledger: E20RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    *,
    condition_id: str,
    stage: E20FailureStage,
    reason_code: ExperimentReasonCode,
    detail_hash: str,
    timestamp_utc: str,
) -> None:
    if not isinstance(row, E20FailureRow):
        raise TypeError("row must be an E20FailureRow")
    expected = build_e20_failure_row(
        authorization,
        ledger,
        preregistration,
        condition_plan,
        corpus_manifest,
        source_sample,
        condition_id=condition_id,
        stage=stage,
        reason_code=reason_code,
        detail_hash=detail_hash,
        timestamp_utc=timestamp_utc,
    )
    if row != expected:
        raise E20FailureVerificationError(
            "E20 failure row does not replay exactly from sealed source artifacts"
        )
