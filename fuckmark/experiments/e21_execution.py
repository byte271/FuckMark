from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from .._validation import require_bool, require_int, require_sha256
from ..hashing import sha256_json
from .e21_rerun import E21ExecutionAuthorization


E21_RUN_LEDGER_ALGORITHM_VERSION = "e21-run-ledger-v1"
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class E21RunState(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    INVALIDATED = "INVALIDATED"


class E21InvalidationReason(str, Enum):
    SOFTWARE_BUG = "SOFTWARE_BUG"
    POST_HOC_CHANGE = "POST_HOC_CHANGE"
    CALIBRATION_LEAKAGE = "CALIBRATION_LEAKAGE"
    SEALED_KEY_CONTAMINATION = "SEALED_KEY_CONTAMINATION"
    SOURCE_PIN_MISMATCH = "SOURCE_PIN_MISMATCH"
    TOKENIZER_DRIFT = "TOKENIZER_DRIFT"
    UPSTREAM_API_CHANGED = "UPSTREAM_API_CHANGED"
    HARD_INVARIANT_FAILURE = "HARD_INVARIANT_FAILURE"
    RERUN_STRUCTURE_DRIFT = "RERUN_STRUCTURE_DRIFT"
    GENERATION_SEED_REUSE = "GENERATION_SEED_REUSE"


class E21RunTransitionError(ValueError):
    pass


class E21RunVerificationError(ValueError):
    pass


def _require_timestamp(value: str) -> None:
    if not isinstance(value, str) or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError("E21 event timestamp must use canonical second-resolution UTC form")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("E21 event timestamp must represent UTC")


@dataclass(frozen=True, slots=True)
class E21RunEvent:
    sequence: int
    state: E21RunState
    occurred_at_utc: str
    artifact_hash: str | None
    invalidation_reason: E21InvalidationReason | None
    evidence_hash: str | None
    outcomes_could_influence_fix: bool
    fresh_rerun_seal_required: bool
    event_hash: str

    def __post_init__(self) -> None:
        require_int("sequence", self.sequence)
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.state, E21RunState):
            raise TypeError("state must be an E21RunState")
        _require_timestamp(self.occurred_at_utc)
        require_bool("outcomes_could_influence_fix", self.outcomes_could_influence_fix)
        require_bool("fresh_rerun_seal_required", self.fresh_rerun_seal_required)
        if self.artifact_hash is not None:
            require_sha256("artifact_hash", self.artifact_hash)
        if self.evidence_hash is not None:
            require_sha256("evidence_hash", self.evidence_hash)
        if self.state is E21RunState.INVALIDATED:
            if not isinstance(self.invalidation_reason, E21InvalidationReason):
                raise TypeError("invalidated E21 events require an E21InvalidationReason")
            if self.evidence_hash is None:
                raise ValueError("invalidated E21 events require an evidence hash")
            if self.artifact_hash is not None:
                raise ValueError("invalidated E21 events cannot name a completed artifact")
            if self.outcomes_could_influence_fix and not self.fresh_rerun_seal_required:
                raise ValueError("outcome-influenced E21 invalidation requires a fresh rerun seal")
            if self.invalidation_reason in (
                E21InvalidationReason.POST_HOC_CHANGE,
                E21InvalidationReason.CALIBRATION_LEAKAGE,
                E21InvalidationReason.SEALED_KEY_CONTAMINATION,
                E21InvalidationReason.RERUN_STRUCTURE_DRIFT,
                E21InvalidationReason.GENERATION_SEED_REUSE,
            ) and not self.fresh_rerun_seal_required:
                raise ValueError("this E21 invalidation reason requires a fresh rerun seal")
        else:
            if self.invalidation_reason is not None or self.evidence_hash is not None:
                raise ValueError("non-invalidated E21 events cannot contain invalidation evidence")
            if self.outcomes_could_influence_fix or self.fresh_rerun_seal_required:
                raise ValueError("non-invalidated E21 events cannot request a fresh rerun seal")
            if self.state is E21RunState.COMPLETED:
                if self.artifact_hash is None:
                    raise ValueError("completed E21 events require a result artifact hash")
            elif self.artifact_hash is not None:
                raise ValueError("only completed E21 events may contain an artifact hash")
        require_sha256("event_hash", self.event_hash)
        if self.event_hash != sha256_json(self._payload()):
            raise ValueError("event_hash does not match E21 run event")

    def _payload(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "state": self.state.value,
            "occurred_at_utc": self.occurred_at_utc,
            "artifact_hash": self.artifact_hash,
            "invalidation_reason": None if self.invalidation_reason is None else self.invalidation_reason.value,
            "evidence_hash": self.evidence_hash,
            "outcomes_could_influence_fix": self.outcomes_could_influence_fix,
            "fresh_rerun_seal_required": self.fresh_rerun_seal_required,
        }

    @classmethod
    def create(
        cls,
        sequence: int,
        state: E21RunState,
        occurred_at_utc: str,
        *,
        artifact_hash: str | None = None,
        invalidation_reason: E21InvalidationReason | None = None,
        evidence_hash: str | None = None,
        outcomes_could_influence_fix: bool = False,
        fresh_rerun_seal_required: bool = False,
    ) -> E21RunEvent:
        payload = {
            "sequence": sequence,
            "state": state.value if isinstance(state, E21RunState) else state,
            "occurred_at_utc": occurred_at_utc,
            "artifact_hash": artifact_hash,
            "invalidation_reason": None if invalidation_reason is None else invalidation_reason.value,
            "evidence_hash": evidence_hash,
            "outcomes_could_influence_fix": outcomes_could_influence_fix,
            "fresh_rerun_seal_required": fresh_rerun_seal_required,
        }
        return cls(
            sequence,
            state,
            occurred_at_utc,
            artifact_hash,
            invalidation_reason,
            evidence_hash,
            outcomes_could_influence_fix,
            fresh_rerun_seal_required,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class E21RunLedger:
    algorithm_version: str
    execution_id: str
    authorization_hash: str
    events: tuple[E21RunEvent, ...]
    ledger_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != E21_RUN_LEDGER_ALGORITHM_VERSION:
            raise ValueError("unsupported E21 run ledger algorithm version")
        require_sha256("execution_id", self.execution_id)
        require_sha256("authorization_hash", self.authorization_hash)
        if not isinstance(self.events, tuple) or not self.events:
            raise TypeError("events must be a non-empty tuple")
        if any(not isinstance(value, E21RunEvent) for value in self.events):
            raise TypeError("events must contain E21RunEvent values")
        if tuple(value.sequence for value in self.events) != tuple(range(len(self.events))):
            raise ValueError("E21 events must use contiguous zero-based sequence numbers")
        states = tuple(value.state for value in self.events)
        valid_paths = {
            (E21RunState.AUTHORIZED,),
            (E21RunState.AUTHORIZED, E21RunState.STARTED),
            (E21RunState.AUTHORIZED, E21RunState.INVALIDATED),
            (E21RunState.AUTHORIZED, E21RunState.STARTED, E21RunState.COMPLETED),
            (E21RunState.AUTHORIZED, E21RunState.STARTED, E21RunState.INVALIDATED),
            (
                E21RunState.AUTHORIZED,
                E21RunState.STARTED,
                E21RunState.COMPLETED,
                E21RunState.INVALIDATED,
            ),
        }
        if states not in valid_paths:
            raise ValueError("invalid E21 run ledger state path")
        require_sha256("ledger_hash", self.ledger_hash)
        if self.ledger_hash != sha256_json(self._payload()):
            raise ValueError("ledger_hash does not match E21 run ledger")

    @property
    def state(self) -> E21RunState:
        return self.events[-1].state

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "execution_id": self.execution_id,
            "authorization_hash": self.authorization_hash,
            "events": self.events,
        }


def _ledger(authorization: E21ExecutionAuthorization, events: tuple[E21RunEvent, ...]) -> E21RunLedger:
    payload = {
        "algorithm_version": E21_RUN_LEDGER_ALGORITHM_VERSION,
        "execution_id": authorization.execution_id,
        "authorization_hash": authorization.authorization_hash,
        "events": events,
    }
    return E21RunLedger(
        E21_RUN_LEDGER_ALGORITHM_VERSION,
        authorization.execution_id,
        authorization.authorization_hash,
        events,
        sha256_json(payload),
    )


def create_e21_run_ledger(
    authorization: E21ExecutionAuthorization,
    occurred_at_utc: str,
) -> E21RunLedger:
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    return _ledger(
        authorization,
        (E21RunEvent.create(0, E21RunState.AUTHORIZED, occurred_at_utc),),
    )


def verify_e21_run_ledger(
    ledger: E21RunLedger,
    authorization: E21ExecutionAuthorization,
) -> None:
    if not isinstance(ledger, E21RunLedger):
        raise TypeError("ledger must be an E21RunLedger")
    if not isinstance(authorization, E21ExecutionAuthorization):
        raise TypeError("authorization must be an E21ExecutionAuthorization")
    if ledger.execution_id != authorization.execution_id or ledger.authorization_hash != authorization.authorization_hash:
        raise E21RunVerificationError("E21 run ledger is not bound to the supplied authorization")


def _append(ledger: E21RunLedger, event: E21RunEvent) -> E21RunLedger:
    events = ledger.events + (event,)
    payload = {
        "algorithm_version": E21_RUN_LEDGER_ALGORITHM_VERSION,
        "execution_id": ledger.execution_id,
        "authorization_hash": ledger.authorization_hash,
        "events": events,
    }
    return E21RunLedger(
        E21_RUN_LEDGER_ALGORITHM_VERSION,
        ledger.execution_id,
        ledger.authorization_hash,
        events,
        sha256_json(payload),
    )


def start_e21_run(ledger: E21RunLedger, occurred_at_utc: str) -> E21RunLedger:
    if ledger.state is not E21RunState.AUTHORIZED:
        raise E21RunTransitionError("E21 can start only from AUTHORIZED")
    return _append(
        ledger,
        E21RunEvent.create(len(ledger.events), E21RunState.STARTED, occurred_at_utc),
    )


def complete_e21_run(
    ledger: E21RunLedger,
    occurred_at_utc: str,
    result_bundle_hash: str,
) -> E21RunLedger:
    if ledger.state is not E21RunState.STARTED:
        raise E21RunTransitionError("E21 can complete only from STARTED")
    require_sha256("result_bundle_hash", result_bundle_hash)
    return _append(
        ledger,
        E21RunEvent.create(
            len(ledger.events),
            E21RunState.COMPLETED,
            occurred_at_utc,
            artifact_hash=result_bundle_hash,
        ),
    )


def invalidate_e21_run(
    ledger: E21RunLedger,
    occurred_at_utc: str,
    reason: E21InvalidationReason,
    evidence_hash: str,
    *,
    outcomes_could_influence_fix: bool,
    fresh_rerun_seal_required: bool,
) -> E21RunLedger:
    if ledger.state not in (E21RunState.AUTHORIZED, E21RunState.STARTED, E21RunState.COMPLETED):
        raise E21RunTransitionError("E21 can be invalidated only from an active or completed state")
    if not isinstance(reason, E21InvalidationReason):
        raise TypeError("reason must be an E21InvalidationReason")
    require_sha256("evidence_hash", evidence_hash)
    return _append(
        ledger,
        E21RunEvent.create(
            len(ledger.events),
            E21RunState.INVALIDATED,
            occurred_at_utc,
            invalidation_reason=reason,
            evidence_hash=evidence_hash,
            outcomes_could_influence_fix=outcomes_could_influence_fix,
            fresh_rerun_seal_required=fresh_rerun_seal_required,
        ),
    )
