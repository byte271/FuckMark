from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..corpus import CorpusManifest, ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence
from ..environment import EnvironmentSnapshot
from ..hashing import derive_seed, sha256_json
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration
from .confirmatory_corpus import ConfirmatoryCorpusSeal, verify_confirmatory_corpus_seal
from .confirmatory_keys import ConfirmatoryTestKeyManifest
from .confirmatory_verification import verify_confirmatory_preregistration


E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION = "e20-execution-authorization-v1"
E20_RUN_LEDGER_ALGORITHM_VERSION = "e20-run-ledger-v1"
E20_SEED_DERIVATION_ALGORITHM_VERSION = "e20-seed-derivation-v1"
E20_EXPERIMENT_ID = "E20"
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class E20RunState(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    INVALIDATED = "INVALIDATED"


class E20InvalidationReason(str, Enum):
    SOFTWARE_BUG = "SOFTWARE_BUG"
    POST_HOC_CHANGE = "POST_HOC_CHANGE"
    CALIBRATION_LEAKAGE = "CALIBRATION_LEAKAGE"
    SEALED_KEY_CONTAMINATION = "SEALED_KEY_CONTAMINATION"
    SOURCE_PIN_MISMATCH = "SOURCE_PIN_MISMATCH"
    TOKENIZER_DRIFT = "TOKENIZER_DRIFT"
    UPSTREAM_API_CHANGED = "UPSTREAM_API_CHANGED"
    HARD_INVARIANT_FAILURE = "HARD_INVARIANT_FAILURE"


class E20AuthorizationError(ValueError):
    pass


class E20RunTransitionError(ValueError):
    pass


def _require_utc_timestamp(name: str, value: str) -> None:
    require_clean_string(name, value)
    if _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must use canonical second-resolution UTC form")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{name} must represent UTC")


def _execution_id(preregistration_hash: str, corpus_seal_hash: str) -> str:
    return sha256_json(
        {
            "experiment_id": E20_EXPERIMENT_ID,
            "preregistration_hash": preregistration_hash,
            "corpus_seal_hash": corpus_seal_hash,
        }
    )


@dataclass(frozen=True, slots=True)
class E20ExecutionAuthorization:
    algorithm_version: str
    experiment_id: str
    execution_id: str
    preregistration_hash: str
    corpus_seal_hash: str
    corpus_manifest_hash: str
    test_key_manifest_hash: str
    code_commit: str
    environment_snapshot_hash: str
    dependency_lock_hash: str
    worker_version: str
    shard_count: int
    output_namespace: str
    seed_derivation_version: str
    authorization_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 execution authorization algorithm version")
        if self.experiment_id != E20_EXPERIMENT_ID:
            raise ValueError("E20 execution authorization must use experiment_id E20")
        for name, value in (
            ("execution_id", self.execution_id),
            ("preregistration_hash", self.preregistration_hash),
            ("corpus_seal_hash", self.corpus_seal_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("test_key_manifest_hash", self.test_key_manifest_hash),
            ("environment_snapshot_hash", self.environment_snapshot_hash),
            ("dependency_lock_hash", self.dependency_lock_hash),
            ("authorization_hash", self.authorization_hash),
        ):
            require_sha256(name, value)
        require_clean_string("code_commit", self.code_commit)
        if not re.fullmatch(r"[0-9a-f]{40}", self.code_commit):
            raise ValueError("code_commit must be a full lowercase 40-character Git revision")
        require_clean_string("worker_version", self.worker_version)
        require_int("shard_count", self.shard_count)
        if self.shard_count <= 0 or self.shard_count > 4096:
            raise ValueError("shard_count must be between 1 and 4096")
        require_clean_string("output_namespace", self.output_namespace)
        if self.output_namespace != f"e20/{self.execution_id}":
            raise ValueError("output_namespace must be derived from execution_id")
        if self.seed_derivation_version != E20_SEED_DERIVATION_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 seed derivation version")
        expected_execution_id = _execution_id(self.preregistration_hash, self.corpus_seal_hash)
        if self.execution_id != expected_execution_id:
            raise ValueError("execution_id does not match preregistration and corpus seal")
        if self.authorization_hash != sha256_json(self._payload()):
            raise ValueError("authorization_hash does not match E20 execution authorization")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "experiment_id": self.experiment_id,
            "execution_id": self.execution_id,
            "preregistration_hash": self.preregistration_hash,
            "corpus_seal_hash": self.corpus_seal_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "test_key_manifest_hash": self.test_key_manifest_hash,
            "code_commit": self.code_commit,
            "environment_snapshot_hash": self.environment_snapshot_hash,
            "dependency_lock_hash": self.dependency_lock_hash,
            "worker_version": self.worker_version,
            "shard_count": self.shard_count,
            "output_namespace": self.output_namespace,
            "seed_derivation_version": self.seed_derivation_version,
        }


@dataclass(frozen=True, slots=True)
class E20RunEvent:
    sequence: int
    state: E20RunState
    occurred_at_utc: str
    artifact_hash: str | None
    invalidation_reason: E20InvalidationReason | None
    evidence_hash: str | None
    outcomes_could_influence_fix: bool
    fresh_seal_required: bool
    event_hash: str

    def __post_init__(self) -> None:
        require_int("sequence", self.sequence)
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.state, E20RunState):
            raise TypeError("state must be an E20RunState")
        _require_utc_timestamp("occurred_at_utc", self.occurred_at_utc)
        require_bool("outcomes_could_influence_fix", self.outcomes_could_influence_fix)
        require_bool("fresh_seal_required", self.fresh_seal_required)
        if self.artifact_hash is not None:
            require_sha256("artifact_hash", self.artifact_hash)
        if self.evidence_hash is not None:
            require_sha256("evidence_hash", self.evidence_hash)
        if self.state is E20RunState.INVALIDATED:
            if not isinstance(self.invalidation_reason, E20InvalidationReason):
                raise TypeError("invalidated events require an E20InvalidationReason")
            if self.evidence_hash is None:
                raise ValueError("invalidated events require an evidence hash")
            if self.artifact_hash is not None:
                raise ValueError("invalidated events cannot name a completed result artifact")
            if self.outcomes_could_influence_fix and not self.fresh_seal_required:
                raise ValueError("outcome-influenced invalidation requires a fresh seal")
            if self.invalidation_reason in (
                E20InvalidationReason.CALIBRATION_LEAKAGE,
                E20InvalidationReason.SEALED_KEY_CONTAMINATION,
                E20InvalidationReason.POST_HOC_CHANGE,
            ) and not self.fresh_seal_required:
                raise ValueError("this invalidation reason requires a fresh seal")
        else:
            if self.invalidation_reason is not None or self.evidence_hash is not None:
                raise ValueError("non-invalidated events cannot contain invalidation evidence")
            if self.outcomes_could_influence_fix or self.fresh_seal_required:
                raise ValueError("non-invalidated events cannot require a fresh seal")
            if self.state is E20RunState.COMPLETED:
                if self.artifact_hash is None:
                    raise ValueError("completed events require a result artifact hash")
            elif self.artifact_hash is not None:
                raise ValueError("only completed events may contain a result artifact hash")
        require_sha256("event_hash", self.event_hash)
        if self.event_hash != sha256_json(self._payload()):
            raise ValueError("event_hash does not match E20 run event")

    def _payload(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "state": self.state.value,
            "occurred_at_utc": self.occurred_at_utc,
            "artifact_hash": self.artifact_hash,
            "invalidation_reason": None if self.invalidation_reason is None else self.invalidation_reason.value,
            "evidence_hash": self.evidence_hash,
            "outcomes_could_influence_fix": self.outcomes_could_influence_fix,
            "fresh_seal_required": self.fresh_seal_required,
        }

    @classmethod
    def create(
        cls,
        sequence: int,
        state: E20RunState,
        occurred_at_utc: str,
        *,
        artifact_hash: str | None = None,
        invalidation_reason: E20InvalidationReason | None = None,
        evidence_hash: str | None = None,
        outcomes_could_influence_fix: bool = False,
        fresh_seal_required: bool = False,
    ) -> E20RunEvent:
        payload = {
            "sequence": sequence,
            "state": state.value if isinstance(state, E20RunState) else state,
            "occurred_at_utc": occurred_at_utc,
            "artifact_hash": artifact_hash,
            "invalidation_reason": None if invalidation_reason is None else invalidation_reason.value,
            "evidence_hash": evidence_hash,
            "outcomes_could_influence_fix": outcomes_could_influence_fix,
            "fresh_seal_required": fresh_seal_required,
        }
        return cls(
            sequence,
            state,
            occurred_at_utc,
            artifact_hash,
            invalidation_reason,
            evidence_hash,
            outcomes_could_influence_fix,
            fresh_seal_required,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E20RunLedger:
    algorithm_version: str
    execution_id: str
    authorization_hash: str
    events: tuple[E20RunEvent, ...]
    ledger_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E20_RUN_LEDGER_ALGORITHM_VERSION:
            raise ValueError("unsupported E20 run ledger algorithm version")
        require_sha256("execution_id", self.execution_id)
        require_sha256("authorization_hash", self.authorization_hash)
        if not isinstance(self.events, tuple) or not self.events:
            raise TypeError("events must be a non-empty tuple")
        if any(not isinstance(value, E20RunEvent) for value in self.events):
            raise TypeError("events must contain E20RunEvent values")
        if tuple(value.sequence for value in self.events) != tuple(range(len(self.events))):
            raise ValueError("E20 run events must use contiguous zero-based sequence numbers")
        states = tuple(value.state for value in self.events)
        if states[0] is not E20RunState.AUTHORIZED:
            raise ValueError("E20 run ledger must begin with AUTHORIZED")
        allowed = {
            (E20RunState.AUTHORIZED, E20RunState.STARTED),
            (E20RunState.AUTHORIZED, E20RunState.INVALIDATED),
            (E20RunState.STARTED, E20RunState.COMPLETED),
            (E20RunState.STARTED, E20RunState.INVALIDATED),
            (E20RunState.COMPLETED, E20RunState.INVALIDATED),
        }
        for previous, current in zip(states, states[1:]):
            if (previous, current) not in allowed:
                raise ValueError("invalid E20 run ledger state transition")
        terminal_count = sum(value in (E20RunState.COMPLETED, E20RunState.INVALIDATED) for value in states)
        if terminal_count > 1:
            raise ValueError("E20 run ledger can contain only one terminal event")
        if states[-1] in (E20RunState.COMPLETED, E20RunState.INVALIDATED) and len(states) > 1:
            if any(value in (E20RunState.COMPLETED, E20RunState.INVALIDATED) for value in states[:-1]):
                raise ValueError("E20 run ledger cannot continue after a terminal state")
        require_sha256("ledger_hash", self.ledger_hash)
        if self.ledger_hash != sha256_json(self._payload()):
            raise ValueError("ledger_hash does not match E20 run ledger")

    @property
    def state(self) -> E20RunState:
        return self.events[-1].state

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "authorization_hash": self.authorization_hash,
            "events": self.events,
        }


def authorize_e20_execution(
    preregistration: ConfirmatoryPreregistration,
    corpus_seal: ConfirmatoryCorpusSeal,
    corpus_manifest: CorpusManifest,
    test_key_manifest: ConfirmatoryTestKeyManifest,
    environment: EnvironmentSnapshot,
    *,
    dependency_lock_hash: str,
    worker_version: str,
    shard_count: int,
    dirty_worktree: bool,
    prior_ledgers: Sequence[E20RunLedger],
    code_commit: str,
    spec_revision_hash: str,
    power_analysis_hash: str,
    budget_config_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
) -> E20ExecutionAuthorization:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if not isinstance(corpus_seal, ConfirmatoryCorpusSeal):
        raise TypeError("corpus_seal must be a ConfirmatoryCorpusSeal")
    if not isinstance(corpus_manifest, CorpusManifest):
        raise TypeError("corpus_manifest must be a CorpusManifest")
    if not isinstance(test_key_manifest, ConfirmatoryTestKeyManifest):
        raise TypeError("test_key_manifest must be a ConfirmatoryTestKeyManifest")
    if not isinstance(environment, EnvironmentSnapshot):
        raise TypeError("environment must be an EnvironmentSnapshot")
    require_sha256("dependency_lock_hash", dependency_lock_hash)
    require_clean_string("worker_version", worker_version)
    require_int("shard_count", shard_count)
    require_bool("dirty_worktree", dirty_worktree)
    if dirty_worktree:
        raise E20AuthorizationError("E20 authorization requires a clean worktree in the v1 sealed runner")
    if code_commit != preregistration.code_commit:
        raise E20AuthorizationError("runtime code commit does not match the sealed preregistration")
    try:
        verify_confirmatory_preregistration(
            preregistration,
            code_commit=code_commit,
            spec_revision_hash=spec_revision_hash,
            power_analysis_hash=power_analysis_hash,
            budget_config_hash=budget_config_hash,
            verification_test_hashes=verification_test_hashes,
            model_tokenizers=model_tokenizers,
            calibration_negative_evidence=calibration_negative_evidence,
            sealed_test_key_hash=test_key_manifest.manifest_hash,
            sealed_test_corpus_hash=corpus_manifest.manifest_hash,
            task29_lexical_evidence=task29_lexical_evidence,
            task29_syntax_evidence=task29_syntax_evidence,
            task29_tokenizers=task29_tokenizers,
        )
    except Exception as error:
        raise E20AuthorizationError("confirmatory preregistration preflight did not replay exactly") from error
    try:
        verify_confirmatory_corpus_seal(corpus_seal, preregistration, corpus_manifest, test_key_manifest)
    except Exception as error:
        raise E20AuthorizationError("confirmatory corpus seal did not replay exactly") from error
    execution_id = _execution_id(preregistration.preregistration_hash, corpus_seal.seal_hash)
    previous = tuple(prior_ledgers)
    if any(not isinstance(value, E20RunLedger) for value in previous):
        raise TypeError("prior_ledgers must contain E20RunLedger values")
    if any(value.execution_id == execution_id for value in previous):
        raise E20AuthorizationError("this sealed E20 execution_id already has a run ledger and cannot be authorized again")
    output_namespace = f"e20/{execution_id}"
    payload = {
        "algorithm_version": E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        "experiment_id": E20_EXPERIMENT_ID,
        "execution_id": execution_id,
        "preregistration_hash": preregistration.preregistration_hash,
        "corpus_seal_hash": corpus_seal.seal_hash,
        "corpus_manifest_hash": corpus_manifest.manifest_hash,
        "test_key_manifest_hash": test_key_manifest.manifest_hash,
        "code_commit": code_commit,
        "environment_snapshot_hash": environment.snapshot_hash,
        "dependency_lock_hash": dependency_lock_hash,
        "worker_version": worker_version,
        "shard_count": shard_count,
        "output_namespace": output_namespace,
        "seed_derivation_version": E20_SEED_DERIVATION_ALGORITHM_VERSION,
    }
    return E20ExecutionAuthorization(
        E20_EXECUTION_AUTHORIZATION_ALGORITHM_VERSION,
        E20_EXPERIMENT_ID,
        execution_id,
        preregistration.preregistration_hash,
        corpus_seal.seal_hash,
        corpus_manifest.manifest_hash,
        test_key_manifest.manifest_hash,
        code_commit,
        environment.snapshot_hash,
        dependency_lock_hash,
        worker_version,
        shard_count,
        output_namespace,
        E20_SEED_DERIVATION_ALGORITHM_VERSION,
        sha256_json(payload),
    )


def create_e20_run_ledger(authorization: E20ExecutionAuthorization, occurred_at_utc: str) -> E20RunLedger:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    event = E20RunEvent.create(0, E20RunState.AUTHORIZED, occurred_at_utc)
    payload = {
        "algorithm_version": E20_RUN_LEDGER_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "authorization_hash": authorization.authorization_hash,
        "events": (event,),
    }
    return E20RunLedger(
        E20_RUN_LEDGER_ALGORITHM_VERSION,
        authorization.execution_id,
        authorization.authorization_hash,
        (event,),
        sha256_json(payload),
    )


def _append_event(ledger: E20RunLedger, event: E20RunEvent) -> E20RunLedger:
    if not isinstance(ledger, E20RunLedger):
        raise TypeError("ledger must be an E20RunLedger")
    events = ledger.events + (event,)
    payload = {
        "algorithm_version": E20_RUN_LEDGER_ALGORITHM_VERSION,
        "execution_id": ledger.execution_id,
        "authorization_hash": ledger.authorization_hash,
        "events": events,
    }
    return E20RunLedger(
        E20_RUN_LEDGER_ALGORITHM_VERSION,
        ledger.execution_id,
        ledger.authorization_hash,
        events,
        sha256_json(payload),
    )


def start_e20_run(ledger: E20RunLedger, occurred_at_utc: str) -> E20RunLedger:
    if ledger.state is not E20RunState.AUTHORIZED:
        raise E20RunTransitionError("E20 can start only from AUTHORIZED")
    return _append_event(
        ledger,
        E20RunEvent.create(len(ledger.events), E20RunState.STARTED, occurred_at_utc),
    )


def complete_e20_run(
    ledger: E20RunLedger,
    occurred_at_utc: str,
    result_bundle_hash: str,
) -> E20RunLedger:
    if ledger.state is not E20RunState.STARTED:
        raise E20RunTransitionError("E20 can complete only from STARTED")
    require_sha256("result_bundle_hash", result_bundle_hash)
    return _append_event(
        ledger,
        E20RunEvent.create(
            len(ledger.events),
            E20RunState.COMPLETED,
            occurred_at_utc,
            artifact_hash=result_bundle_hash,
        ),
    )


def invalidate_e20_run(
    ledger: E20RunLedger,
    occurred_at_utc: str,
    reason: E20InvalidationReason,
    evidence_hash: str,
    *,
    outcomes_could_influence_fix: bool,
    fresh_seal_required: bool,
) -> E20RunLedger:
    if ledger.state not in (E20RunState.AUTHORIZED, E20RunState.STARTED, E20RunState.COMPLETED):
        raise E20RunTransitionError("E20 can be invalidated only before a prior invalidation")
    if not isinstance(reason, E20InvalidationReason):
        raise TypeError("reason must be an E20InvalidationReason")
    require_sha256("evidence_hash", evidence_hash)
    return _append_event(
        ledger,
        E20RunEvent.create(
            len(ledger.events),
            E20RunState.INVALIDATED,
            occurred_at_utc,
            invalidation_reason=reason,
            evidence_hash=evidence_hash,
            outcomes_could_influence_fix=outcomes_could_influence_fix,
            fresh_seal_required=fresh_seal_required,
        ),
    )


def e20_sample_shard(authorization: E20ExecutionAuthorization, sample_id: str) -> int:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    require_clean_string("sample_id", sample_id)
    return derive_seed(
        authorization.execution_id,
        authorization.seed_derivation_version,
        "shard",
        sample_id,
        bits=64,
    ) % authorization.shard_count


def derive_e20_condition_seed(
    authorization: E20ExecutionAuthorization,
    sample_id: str,
    condition_id: str,
    purpose: str,
) -> int:
    if not isinstance(authorization, E20ExecutionAuthorization):
        raise TypeError("authorization must be an E20ExecutionAuthorization")
    require_clean_string("sample_id", sample_id)
    require_clean_string("condition_id", condition_id)
    require_clean_string("purpose", purpose)
    return derive_seed(
        authorization.execution_id,
        authorization.seed_derivation_version,
        "condition",
        sample_id,
        condition_id,
        purpose,
        bits=64,
    )
