from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import derive_seed, sha256_json
from .mid_dev_context_survival import MidDevCondition


MID_DEV_SELECTION_TRACE_VERSION = "mid-dev-selection-trace-v1"
MID_DEV_TRACE_ARTIFACT_VERSION = "mid-dev-selection-trace-artifact-v1"
MID_DEV_SEED_DERIVATION_BASE = 0x4D49444445565031
MID_DEV_SEED_DERIVATION_VERSION = "mid-dev-plan-builder-v1"


def mid_dev_schedule_seed(
    sample_id: str,
    condition: MidDevCondition,
    budget: int,
    replicate: int,
) -> int:
    return derive_seed(
        MID_DEV_SEED_DERIVATION_BASE,
        MID_DEV_SEED_DERIVATION_VERSION,
        sample_id,
        condition.value,
        str(budget),
        str(replicate),
        bits=64,
    )


@dataclass(frozen=True, slots=True)
class MidDevSelectionTrace:
    source_group_id: str
    sample_id: str
    condition: MidDevCondition
    budget: int
    replicate: int
    schedule_seed: int
    candidate_pool_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    final_search_state_hash: str | None
    operation_hashes: tuple[str, ...]
    transition_hashes: tuple[str, ...]
    status: str
    trace_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_group_id, str) or not self.source_group_id:
            raise ValueError("source_group_id must be non-empty")
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        require_int("budget", self.budget)
        require_int("replicate", self.replicate)
        require_int("schedule_seed", self.schedule_seed)
        for name in (
            "candidate_pool_hash",
            "scheduler_input_hash",
            "schedule_result_hash",
            "trace_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.final_search_state_hash is not None:
            require_sha256("final_search_state_hash", self.final_search_state_hash)
        for index, value in enumerate(self.operation_hashes):
            require_sha256(f"operation_hashes[{index}]", value)
        for index, value in enumerate(self.transition_hashes):
            require_sha256(f"transition_hashes[{index}]", value)
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status must be non-empty")
        if self.trace_hash != sha256_json(self.payload()):
            raise ValueError("trace_hash does not match MidDev selection trace")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SELECTION_TRACE_VERSION,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "schedule_seed": self.schedule_seed,
            "candidate_pool_hash": self.candidate_pool_hash,
            "scheduler_input_hash": self.scheduler_input_hash,
            "schedule_result_hash": self.schedule_result_hash,
            "final_search_state_hash": self.final_search_state_hash,
            "operation_hashes": self.operation_hashes,
            "transition_hashes": self.transition_hashes,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class MidDevSelectionTraceArtifact:
    plan_hash: str
    traces: tuple[MidDevSelectionTrace, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_hash", self.plan_hash)
        if not isinstance(self.traces, tuple) or not self.traces:
            raise ValueError("traces must be a non-empty tuple")
        if any(not isinstance(value, MidDevSelectionTrace) for value in self.traces):
            raise TypeError("traces must contain MidDevSelectionTrace values")
        if len({value.trace_hash for value in self.traces}) != len(self.traces):
            raise ValueError("selection trace hashes must be unique")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match selection trace artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_TRACE_ARTIFACT_VERSION,
            "plan_hash": self.plan_hash,
            "trace_hashes": tuple(value.trace_hash for value in self.traces),
        }
