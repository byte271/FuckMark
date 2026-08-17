from __future__ import annotations

from .._validation import require_sha256
from ..corpus import CorpusManifest, CorpusSample
from ..hashing import sha256_text
from .confirmatory import ConfirmatoryPreregistration
from .e20_conditions import E20ConditionPlan, verify_e20_condition_plan
from .e20_rows import ExperimentReasonCode
from .e21_execution import (
    E21RunLedger,
    E21RunState,
    verify_e21_run_ledger,
)
from .e21_rerun import E21ExecutionAuthorization
from .e21_rows import (
    E21AuditFields,
    E21FailureRow,
    E21FailureStage,
    E21IdentityFields,
)


E21_FAILURE_REPLAY_ALGORITHM_VERSION = "e21-failure-replay-v1"


class E21FailureVerificationError(ValueError):
    pass


def build_e21_failure_row(
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    *,
    condition_id: str,
    stage: E21FailureStage,
    reason_code: ExperimentReasonCode,
    detail_hash: str,
    timestamp_utc: str,
) -> E21FailureRow:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    if not isinstance(ledger, E21RunLedger):
        raise TypeError("ledger must be an E21RunLedger")
    verify_e21_run_ledger(ledger, authorization)
    if ledger.state is not E21RunState.STARTED:
        raise E21FailureVerificationError(
            "E21 failure rows may be built only while the sealed rerun is STARTED"
        )
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    verify_e20_condition_plan(condition_plan, preregistration)
    condition = condition_plan.condition(condition_id)
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if corpus_manifest.manifest_hash != authorization.e21_corpus_manifest_hash:
        raise E21FailureVerificationError(
            "corpus manifest does not match E21 authorization"
        )
    if not isinstance(source_sample, CorpusSample):
        raise TypeError("source_sample must be a CorpusSample")
    matches = tuple(
        value for value in corpus_manifest.samples if value.sample_id == source_sample.sample_id
    )
    if len(matches) != 1 or matches[0] != source_sample:
        raise E21FailureVerificationError(
            "source sample does not replay exactly from the authorized E21 corpus manifest"
        )
    if source_sample.model not in preregistration.model_tokenizers:
        raise E21FailureVerificationError(
            "source sample model/tokenizer is not preregistered"
        )
    require_sha256("detail_hash", detail_hash)
    identity = E21IdentityFields(
        authorization.execution_id,
        authorization.execution_id,
        "E21",
        condition.condition_id,
        source_sample.sample_id,
        source_sample.match_id,
    )
    audit = E21AuditFields(
        authorization.worker_version,
        timestamp_utc,
        authorization.environment_snapshot_hash,
        authorization.authorization_hash,
        ledger.ledger_hash,
        tuple(
            sorted(
                {
                    source_sample.record_hash,
                    detail_hash,
                    condition.condition_hash,
                    sha256_text(E21_FAILURE_REPLAY_ALGORITHM_VERSION),
                }
            )
        ),
    )
    return E21FailureRow.create(
        identity,
        stage,
        reason_code,
        source_sample.record_hash,
        detail_hash,
        audit,
    )


def verify_e21_failure_row(
    row: E21FailureRow,
    authorization: E21ExecutionAuthorization,
    ledger: E21RunLedger,
    preregistration: ConfirmatoryPreregistration,
    condition_plan: E20ConditionPlan,
    corpus_manifest: CorpusManifest,
    source_sample: CorpusSample,
    *,
    condition_id: str,
    stage: E21FailureStage,
    reason_code: ExperimentReasonCode,
    detail_hash: str,
    timestamp_utc: str,
) -> None:
    if not isinstance(row, E21FailureRow):
        raise TypeError("row must be an E21FailureRow")
    expected = build_e21_failure_row(
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
        raise E21FailureVerificationError(
            "E21 failure row does not replay exactly from sealed source artifacts"
        )
