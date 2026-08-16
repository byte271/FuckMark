from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .candidate_artifacts import CandidateEnumeration


CANDIDATE_SCHEDULER_ALGORITHM_VERSION = "candidate-scheduler-v1"


class SchedulePolicy(str, Enum):
    RANDOM_VALID = "RANDOM_VALID"
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"


@dataclass(frozen=True, slots=True)
class SchedulerCandidate:
    candidate_id: str
    start: int
    end: int
    edit_cost: int

    def __post_init__(self) -> None:
        require_sha256("candidate_id", self.candidate_id)
        require_int("start", self.start)
        require_int("end", self.end)
        require_int("edit_cost", self.edit_cost)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("scheduler candidate span must satisfy 0 <= start < end")
        if self.edit_cost <= 0:
            raise ValueError("edit_cost must be positive")


@dataclass(frozen=True, slots=True)
class KeyBlindScheduleInput:
    algorithm_version: str
    input_hash: str
    enumeration_hash: str
    budget_unit: str
    candidates: tuple[SchedulerCandidate, ...]
    conflicts: tuple[tuple[str, str], ...]
    input_artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != CANDIDATE_SCHEDULER_ALGORITHM_VERSION:
            raise ValueError("unsupported candidate scheduler algorithm version")
        require_sha256("input_hash", self.input_hash)
        require_sha256("enumeration_hash", self.enumeration_hash)
        require_clean_string("budget_unit", self.budget_unit)
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be a tuple")
        if any(not isinstance(value, SchedulerCandidate) for value in self.candidates):
            raise TypeError("candidates must contain SchedulerCandidate values")
        canonical_candidates = tuple(sorted(self.candidates, key=lambda value: value.candidate_id))
        if self.candidates != canonical_candidates:
            raise ValueError("scheduler candidates must use canonical candidate_id ordering")
        candidate_ids = tuple(value.candidate_id for value in self.candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("scheduler candidate IDs must be unique")
        if not isinstance(self.conflicts, tuple):
            raise TypeError("conflicts must be a tuple")
        canonical_conflicts = tuple(sorted(set(self.conflicts)))
        if self.conflicts != canonical_conflicts:
            raise ValueError("scheduler conflicts must be unique and canonically ordered")
        valid_ids = set(candidate_ids)
        for conflict in self.conflicts:
            if not isinstance(conflict, tuple) or len(conflict) != 2:
                raise TypeError("scheduler conflicts must contain two-item tuples")
            first, second = conflict
            require_sha256("conflict candidate ID", first)
            require_sha256("conflict candidate ID", second)
            if first >= second:
                raise ValueError("scheduler conflict candidate IDs must be strictly ordered")
            if first not in valid_ids or second not in valid_ids:
                raise ValueError("scheduler conflict references an unknown candidate")
        require_sha256("input_artifact_hash", self.input_artifact_hash)
        if self.input_artifact_hash != sha256_json(self._payload()):
            raise ValueError("input_artifact_hash does not match scheduler input")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "input_hash": self.input_hash,
            "enumeration_hash": self.enumeration_hash,
            "budget_unit": self.budget_unit,
            "candidates": self.candidates,
            "conflicts": self.conflicts,
        }

    @classmethod
    def from_enumeration(
        cls,
        enumeration: CandidateEnumeration,
        edit_costs: Mapping[str, int] | None = None,
        budget_unit: str = "operation",
    ) -> KeyBlindScheduleInput:
        if not isinstance(enumeration, CandidateEnumeration):
            raise TypeError("enumeration must be a CandidateEnumeration")
        require_clean_string("budget_unit", budget_unit)
        ids = tuple(candidate.candidate_id for candidate in enumeration.candidates)
        if edit_costs is None:
            costs = {candidate_id: 1 for candidate_id in ids}
        else:
            if not isinstance(edit_costs, Mapping):
                raise TypeError("edit_costs must be a mapping")
            costs = dict(edit_costs)
            if any(not isinstance(key, str) for key in costs):
                raise TypeError("edit_cost keys must be candidate ID strings")
            if set(costs) != set(ids):
                raise ValueError("edit_costs must contain exactly every enumerated candidate ID")
        candidates = tuple(
            sorted(
                (
                    SchedulerCandidate(
                        candidate.candidate_id,
                        candidate.start,
                        candidate.end,
                        costs[candidate.candidate_id],
                    )
                    for candidate in enumeration.candidates
                ),
                key=lambda value: value.candidate_id,
            )
        )
        conflicts = tuple(
            sorted(
                (conflict.first_candidate_id, conflict.second_candidate_id)
                for conflict in enumeration.conflicts
            )
        )
        payload = {
            "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            "input_hash": enumeration.input_hash,
            "enumeration_hash": enumeration.enumeration_hash,
            "budget_unit": budget_unit,
            "candidates": candidates,
            "conflicts": conflicts,
        }
        return cls(
            CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            enumeration.input_hash,
            enumeration.enumeration_hash,
            budget_unit,
            candidates,
            conflicts,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    algorithm_version: str
    policy: SchedulePolicy
    seed: int
    budget: int
    budget_unit: str
    input_artifact_hash: str
    considered_candidate_ids: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    conflict_skipped_candidate_ids: tuple[str, ...]
    budget_skipped_candidate_ids: tuple[str, ...]
    total_cost: int
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != CANDIDATE_SCHEDULER_ALGORITHM_VERSION:
            raise ValueError("unsupported candidate scheduler algorithm version")
        if not isinstance(self.policy, SchedulePolicy):
            raise TypeError("policy must be a SchedulePolicy")
        require_int("seed", self.seed)
        if self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        require_int("budget", self.budget)
        if self.budget < 0:
            raise ValueError("budget must be non-negative")
        require_clean_string("budget_unit", self.budget_unit)
        require_sha256("input_artifact_hash", self.input_artifact_hash)
        rows = (
            ("considered_candidate_ids", self.considered_candidate_ids),
            ("selected_candidate_ids", self.selected_candidate_ids),
            ("conflict_skipped_candidate_ids", self.conflict_skipped_candidate_ids),
            ("budget_skipped_candidate_ids", self.budget_skipped_candidate_ids),
        )
        for name, values in rows:
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            for value in values:
                require_sha256(name, value)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        if len(set(self.considered_candidate_ids)) != len(self.considered_candidate_ids):
            raise ValueError("considered candidates must be unique")
        classified = (
            set(self.selected_candidate_ids)
            | set(self.conflict_skipped_candidate_ids)
            | set(self.budget_skipped_candidate_ids)
        )
        if classified != set(self.considered_candidate_ids):
            raise ValueError("every considered candidate must have exactly one scheduler outcome")
        counts = (
            len(self.selected_candidate_ids)
            + len(self.conflict_skipped_candidate_ids)
            + len(self.budget_skipped_candidate_ids)
        )
        if counts != len(self.considered_candidate_ids):
            raise ValueError("scheduler outcome classes must be disjoint")
        require_int("total_cost", self.total_cost)
        if self.total_cost < 0 or self.total_cost > self.budget:
            raise ValueError("total_cost must lie inside the requested budget")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self._payload()):
            raise ValueError("result_hash does not match schedule result")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "policy": self.policy.value,
            "seed": self.seed,
            "budget": self.budget,
            "budget_unit": self.budget_unit,
            "input_artifact_hash": self.input_artifact_hash,
            "considered_candidate_ids": self.considered_candidate_ids,
            "selected_candidate_ids": self.selected_candidate_ids,
            "conflict_skipped_candidate_ids": self.conflict_skipped_candidate_ids,
            "budget_skipped_candidate_ids": self.budget_skipped_candidate_ids,
            "total_cost": self.total_cost,
        }


class CandidateScheduler:
    __slots__ = ()

    def schedule(
        self,
        scheduler_input: KeyBlindScheduleInput,
        policy: SchedulePolicy,
        budget: int,
        seed: int = 0,
    ) -> ScheduleResult:
        if not isinstance(scheduler_input, KeyBlindScheduleInput):
            raise TypeError("scheduler_input must be a KeyBlindScheduleInput")
        if not isinstance(policy, SchedulePolicy):
            raise TypeError("policy must be a SchedulePolicy")
        require_int("budget", budget)
        if budget < 0:
            raise ValueError("budget must be non-negative")
        require_int("seed", seed)
        if seed < 0 or seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        if policy is SchedulePolicy.LEFT_TO_RIGHT:
            ordered = tuple(
                sorted(
                    scheduler_input.candidates,
                    key=lambda value: (value.start, value.end, value.candidate_id),
                )
            )
        else:
            ordered = tuple(
                sorted(
                    scheduler_input.candidates,
                    key=lambda value: (
                        sha256_json(
                            {
                                "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
                                "policy": policy.value,
                                "seed": seed,
                                "candidate_id": value.candidate_id,
                            }
                        ),
                        value.candidate_id,
                    ),
                )
            )
        conflict_map: dict[str, set[str]] = {candidate.candidate_id: set() for candidate in ordered}
        for first, second in scheduler_input.conflicts:
            conflict_map[first].add(second)
            conflict_map[second].add(first)
        selected: list[str] = []
        selected_set: set[str] = set()
        conflict_skipped: list[str] = []
        budget_skipped: list[str] = []
        total_cost = 0
        for candidate in ordered:
            if conflict_map[candidate.candidate_id] & selected_set:
                conflict_skipped.append(candidate.candidate_id)
                continue
            if total_cost + candidate.edit_cost > budget:
                budget_skipped.append(candidate.candidate_id)
                continue
            selected.append(candidate.candidate_id)
            selected_set.add(candidate.candidate_id)
            total_cost += candidate.edit_cost
        considered = tuple(candidate.candidate_id for candidate in ordered)
        selected_tuple = tuple(selected)
        conflict_tuple = tuple(conflict_skipped)
        budget_tuple = tuple(budget_skipped)
        payload = {
            "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            "policy": policy.value,
            "seed": seed,
            "budget": budget,
            "budget_unit": scheduler_input.budget_unit,
            "input_artifact_hash": scheduler_input.input_artifact_hash,
            "considered_candidate_ids": considered,
            "selected_candidate_ids": selected_tuple,
            "conflict_skipped_candidate_ids": conflict_tuple,
            "budget_skipped_candidate_ids": budget_tuple,
            "total_cost": total_cost,
        }
        return ScheduleResult(
            CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            policy,
            seed,
            budget,
            scheduler_input.budget_unit,
            scheduler_input.input_artifact_hash,
            considered,
            selected_tuple,
            conflict_tuple,
            budget_tuple,
            total_cost,
            sha256_json(payload),
        )
