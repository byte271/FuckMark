from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..coverage import Interval, merge_intervals, union_size
from ..hashing import sha256_json
from .candidate_artifacts import CandidateEnumeration


CANDIDATE_SCHEDULER_ALGORITHM_VERSION = "candidate-scheduler-v2"
_EXACT_DIAGNOSTIC_MAX_CANDIDATES = 16


class SchedulePolicy(str, Enum):
    RANDOM_VALID = "RANDOM_VALID"
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    CLUSTERED = "CLUSTERED"
    EVEN_SPACING = "EVEN_SPACING"
    COVERAGE_GREEDY_KEY_BLIND = "COVERAGE_GREEDY_KEY_BLIND"


class ScheduleGeometryMode(str, Enum):
    TEXT_ONLY = "TEXT_ONLY"
    TOKENIZER_AWARE_PUBLIC = "TOKENIZER_AWARE_PUBLIC"


@dataclass(frozen=True, slots=True)
class SchedulerCandidate:
    candidate_id: str
    start: int
    end: int
    edit_cost: int
    coverage_intervals: tuple[Interval, ...]

    def __post_init__(self) -> None:
        require_sha256("candidate_id", self.candidate_id)
        require_int("start", self.start)
        require_int("end", self.end)
        require_int("edit_cost", self.edit_cost)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("scheduler candidate span must satisfy 0 <= start < end")
        if self.edit_cost <= 0:
            raise ValueError("edit_cost must be positive")
        if not isinstance(self.coverage_intervals, tuple):
            raise TypeError("coverage_intervals must be a tuple")
        if any(not isinstance(value, Interval) for value in self.coverage_intervals):
            raise TypeError("coverage_intervals must contain Interval values")
        canonical_intervals = merge_intervals(self.coverage_intervals)
        if self.coverage_intervals != canonical_intervals:
            raise ValueError("coverage_intervals must be merged and canonically ordered")

    @property
    def center_twice(self) -> int:
        return self.start + self.end


@dataclass(frozen=True, slots=True)
class KeyBlindScheduleInput:
    algorithm_version: str
    input_hash: str
    enumeration_hash: str
    budget_unit: str
    geometry_mode: ScheduleGeometryMode
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
        if not isinstance(self.geometry_mode, ScheduleGeometryMode):
            raise TypeError("geometry_mode must be a ScheduleGeometryMode")
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
        if any(not isinstance(value, tuple) or len(value) != 2 for value in self.conflicts):
            raise TypeError("scheduler conflicts must contain two-item tuples")
        canonical_conflicts = tuple(sorted(set(self.conflicts)))
        if self.conflicts != canonical_conflicts:
            raise ValueError("scheduler conflicts must be unique and canonically ordered")
        valid_ids = set(candidate_ids)
        for first, second in self.conflicts:
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
            "geometry_mode": self.geometry_mode.value,
            "candidates": self.candidates,
            "conflicts": self.conflicts,
        }

    @classmethod
    def from_enumeration(
        cls,
        enumeration: CandidateEnumeration,
        edit_costs: Mapping[str, int] | None = None,
        budget_unit: str = "operation",
        coverage_intervals: Mapping[str, Sequence[Interval]] | None = None,
        geometry_mode: ScheduleGeometryMode = ScheduleGeometryMode.TEXT_ONLY,
    ) -> KeyBlindScheduleInput:
        if not isinstance(enumeration, CandidateEnumeration):
            raise TypeError("enumeration must be a CandidateEnumeration")
        require_clean_string("budget_unit", budget_unit)
        if not isinstance(geometry_mode, ScheduleGeometryMode):
            raise TypeError("geometry_mode must be a ScheduleGeometryMode")
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
        if coverage_intervals is None:
            geometry = {candidate_id: () for candidate_id in ids}
        else:
            if not isinstance(coverage_intervals, Mapping):
                raise TypeError("coverage_intervals must be a mapping")
            snapshot = dict(coverage_intervals)
            if any(not isinstance(key, str) for key in snapshot):
                raise TypeError("coverage interval keys must be candidate ID strings")
            if set(snapshot) != set(ids):
                raise ValueError("coverage_intervals must contain exactly every enumerated candidate ID")
            geometry = {}
            for candidate_id in ids:
                values = snapshot[candidate_id]
                if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
                    raise TypeError("coverage interval values must be sequences of Interval values")
                geometry[candidate_id] = tuple(values)
        candidates = tuple(
            sorted(
                (
                    SchedulerCandidate(
                        candidate.candidate_id,
                        candidate.start,
                        candidate.end,
                        costs[candidate.candidate_id],
                        geometry[candidate.candidate_id],
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
            "geometry_mode": geometry_mode.value,
            "candidates": candidates,
            "conflicts": conflicts,
        }
        return cls(
            CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            enumeration.input_hash,
            enumeration.enumeration_hash,
            budget_unit,
            geometry_mode,
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
    policy_skipped_candidate_ids: tuple[str, ...]
    total_cost: int
    covered_interval_size: int
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
            ("policy_skipped_candidate_ids", self.policy_skipped_candidate_ids),
        )
        for name, values in rows:
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            for value in values:
                require_sha256(name, value)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        classified = (
            set(self.selected_candidate_ids)
            | set(self.conflict_skipped_candidate_ids)
            | set(self.budget_skipped_candidate_ids)
            | set(self.policy_skipped_candidate_ids)
        )
        if classified != set(self.considered_candidate_ids):
            raise ValueError("every considered candidate must have exactly one scheduler outcome")
        counts = (
            len(self.selected_candidate_ids)
            + len(self.conflict_skipped_candidate_ids)
            + len(self.budget_skipped_candidate_ids)
            + len(self.policy_skipped_candidate_ids)
        )
        if counts != len(self.considered_candidate_ids):
            raise ValueError("scheduler outcome classes must be disjoint")
        require_int("total_cost", self.total_cost)
        if self.total_cost < 0 or self.total_cost > self.budget:
            raise ValueError("total_cost must lie inside the requested budget")
        require_int("covered_interval_size", self.covered_interval_size)
        if self.covered_interval_size < 0:
            raise ValueError("covered_interval_size must be non-negative")
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
            "policy_skipped_candidate_ids": self.policy_skipped_candidate_ids,
            "total_cost": self.total_cost,
            "covered_interval_size": self.covered_interval_size,
        }


@dataclass(frozen=True, slots=True)
class CoverageOptimalityDiagnostic:
    algorithm_version: str
    input_artifact_hash: str
    budget: int
    candidate_count: int
    greedy_selected_candidate_ids: tuple[str, ...]
    greedy_coverage: int
    optimal_selected_candidate_ids: tuple[str, ...]
    optimal_cost: int
    optimal_coverage: int
    coverage_regret: int
    diagnostic_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != CANDIDATE_SCHEDULER_ALGORITHM_VERSION:
            raise ValueError("unsupported candidate scheduler algorithm version")
        require_sha256("input_artifact_hash", self.input_artifact_hash)
        require_int("budget", self.budget)
        require_int("candidate_count", self.candidate_count)
        require_int("greedy_coverage", self.greedy_coverage)
        require_int("optimal_cost", self.optimal_cost)
        require_int("optimal_coverage", self.optimal_coverage)
        require_int("coverage_regret", self.coverage_regret)
        if self.budget < 0 or self.candidate_count < 0:
            raise ValueError("budget and candidate_count must be non-negative")
        if self.greedy_coverage < 0 or self.optimal_cost < 0 or self.optimal_coverage < 0:
            raise ValueError("diagnostic metrics must be non-negative")
        if self.optimal_cost > self.budget:
            raise ValueError("optimal_cost must lie inside the requested budget")
        if self.coverage_regret != self.optimal_coverage - self.greedy_coverage:
            raise ValueError("coverage_regret does not match optimal minus greedy coverage")
        if self.coverage_regret < 0:
            raise ValueError("exact diagnostic cannot be worse than greedy coverage")
        for name, values in (
            ("greedy_selected_candidate_ids", self.greedy_selected_candidate_ids),
            ("optimal_selected_candidate_ids", self.optimal_selected_candidate_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
            for value in values:
                require_sha256(name, value)
        require_sha256("diagnostic_hash", self.diagnostic_hash)
        if self.diagnostic_hash != sha256_json(self._payload()):
            raise ValueError("diagnostic_hash does not match coverage optimality diagnostic")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "input_artifact_hash": self.input_artifact_hash,
            "budget": self.budget,
            "candidate_count": self.candidate_count,
            "greedy_selected_candidate_ids": self.greedy_selected_candidate_ids,
            "greedy_coverage": self.greedy_coverage,
            "optimal_selected_candidate_ids": self.optimal_selected_candidate_ids,
            "optimal_cost": self.optimal_cost,
            "optimal_coverage": self.optimal_coverage,
            "coverage_regret": self.coverage_regret,
        }


def _conflict_map(scheduler_input: KeyBlindScheduleInput) -> dict[str, set[str]]:
    output = {candidate.candidate_id: set() for candidate in scheduler_input.candidates}
    for first, second in scheduler_input.conflicts:
        output[first].add(second)
        output[second].add(first)
    return output


def _spacing_anchor_key(seed: int, candidate: SchedulerCandidate) -> tuple[str, str]:
    return (
        sha256_json(
            {
                "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
                "purpose": "spacing-anchor",
                "seed": seed,
                "candidate_id": candidate.candidate_id,
            }
        ),
        candidate.candidate_id,
    )


def _marginal_coverage(candidate: SchedulerCandidate, covered: tuple[Interval, ...]) -> int:
    return union_size((*covered, *candidate.coverage_intervals)) - union_size(covered)


def _selected_coverage(
    candidates_by_id: Mapping[str, SchedulerCandidate],
    selected_candidate_ids: Sequence[str],
) -> int:
    intervals: list[Interval] = []
    for candidate_id in selected_candidate_ids:
        intervals.extend(candidates_by_id[candidate_id].coverage_intervals)
    return union_size(intervals)


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
        if policy is SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND:
            if not any(candidate.coverage_intervals for candidate in scheduler_input.candidates):
                raise ValueError("coverage greedy scheduling requires explicit key-blind coverage geometry")
            return self._schedule_coverage_greedy(scheduler_input, budget, seed)
        if policy in (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING):
            return self._schedule_spacing(scheduler_input, policy, budget, seed)
        return self._schedule_linear(scheduler_input, policy, budget, seed)

    def exact_coverage_diagnostic(
        self,
        scheduler_input: KeyBlindScheduleInput,
        budget: int,
        seed: int = 0,
        max_candidates: int = _EXACT_DIAGNOSTIC_MAX_CANDIDATES,
    ) -> CoverageOptimalityDiagnostic:
        if not isinstance(scheduler_input, KeyBlindScheduleInput):
            raise TypeError("scheduler_input must be a KeyBlindScheduleInput")
        require_int("budget", budget)
        if budget < 0:
            raise ValueError("budget must be non-negative")
        require_int("seed", seed)
        if seed < 0 or seed >= 1 << 64:
            raise ValueError("seed must be between 0 and 2^64-1")
        require_int("max_candidates", max_candidates)
        if max_candidates <= 0 or max_candidates > _EXACT_DIAGNOSTIC_MAX_CANDIDATES:
            raise ValueError("max_candidates must be between 1 and the exact diagnostic resource limit")
        candidates = scheduler_input.candidates
        if len(candidates) > max_candidates:
            raise ValueError("candidate set exceeds exact diagnostic resource limit")
        if not any(candidate.coverage_intervals for candidate in candidates):
            raise ValueError("exact coverage diagnostic requires explicit key-blind coverage geometry")
        greedy = self.schedule(
            scheduler_input,
            SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
            budget,
            seed,
        )
        index_by_id = {
            candidate.candidate_id: index
            for index, candidate in enumerate(candidates)
        }
        conflict_masks = [0] * len(candidates)
        for first, second in scheduler_input.conflicts:
            first_index = index_by_id[first]
            second_index = index_by_id[second]
            conflict_masks[first_index] |= 1 << second_index
            conflict_masks[second_index] |= 1 << first_index
        states: dict[
            tuple[int, int, tuple[Interval, ...]],
            tuple[str, ...],
        ] = {(0, 0, ()): ()}
        for index, candidate in enumerate(candidates):
            next_states = dict(states)
            candidate_bit = 1 << index
            for (cost, blocked_mask, covered), selected in states.items():
                if blocked_mask & candidate_bit:
                    continue
                new_cost = cost + candidate.edit_cost
                if new_cost > budget:
                    continue
                new_selected = (*selected, candidate.candidate_id)
                new_covered = merge_intervals((*covered, *candidate.coverage_intervals))
                new_blocked = blocked_mask | candidate_bit | conflict_masks[index]
                state_key = (new_cost, new_blocked, new_covered)
                existing = next_states.get(state_key)
                if existing is None or new_selected < existing:
                    next_states[state_key] = new_selected
            states = next_states
        best_selected: tuple[str, ...] = ()
        best_cost = 0
        best_coverage = 0
        for (cost, covered, _), selected in states.items():
            coverage = union_size(covered)
            if coverage > best_coverage:
                best_selected = selected
                best_cost = cost
                best_coverage = coverage
            elif coverage == best_coverage:
                if cost < best_cost or (cost == best_cost and selected < best_selected):
                    best_selected = selected
                    best_cost = cost
        regret = best_coverage - greedy.covered_interval_size
        payload = {
            "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            "input_artifact_hash": scheduler_input.input_artifact_hash,
            "budget": budget,
            "candidate_count": len(candidates),
            "greedy_selected_candidate_ids": greedy.selected_candidate_ids,
            "greedy_coverage": greedy.covered_interval_size,
            "optimal_selected_candidate_ids": best_selected,
            "optimal_cost": best_cost,
            "optimal_coverage": best_coverage,
            "coverage_regret": regret,
        }
        return CoverageOptimalityDiagnostic(
            CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            scheduler_input.input_artifact_hash,
            budget,
            len(candidates),
            greedy.selected_candidate_ids,
            greedy.covered_interval_size,
            best_selected,
            best_cost,
            best_coverage,
            regret,
            sha256_json(payload),
        )

    def _schedule_linear(
        self,
        scheduler_input: KeyBlindScheduleInput,
        policy: SchedulePolicy,
        budget: int,
        seed: int,
    ) -> ScheduleResult:
        if policy is SchedulePolicy.LEFT_TO_RIGHT:
            ordered = tuple(
                sorted(
                    scheduler_input.candidates,
                    key=lambda value: (value.start, value.end, value.candidate_id),
                )
            )
        elif policy is SchedulePolicy.RANDOM_VALID:
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
        else:
            raise ValueError("linear scheduler received an unsupported policy")
        conflicts = _conflict_map(scheduler_input)
        selected: list[str] = []
        selected_set: set[str] = set()
        conflict_skipped: list[str] = []
        budget_skipped: list[str] = []
        total_cost = 0
        for candidate in ordered:
            if conflicts[candidate.candidate_id] & selected_set:
                conflict_skipped.append(candidate.candidate_id)
                continue
            if total_cost + candidate.edit_cost > budget:
                budget_skipped.append(candidate.candidate_id)
                continue
            selected.append(candidate.candidate_id)
            selected_set.add(candidate.candidate_id)
            total_cost += candidate.edit_cost
        return self._result(
            scheduler_input,
            policy,
            seed,
            budget,
            tuple(candidate.candidate_id for candidate in ordered),
            tuple(selected),
            tuple(conflict_skipped),
            tuple(budget_skipped),
            (),
            total_cost,
        )

    def _schedule_spacing(
        self,
        scheduler_input: KeyBlindScheduleInput,
        policy: SchedulePolicy,
        budget: int,
        seed: int,
    ) -> ScheduleResult:
        conflicts = _conflict_map(scheduler_input)
        remaining = {candidate.candidate_id: candidate for candidate in scheduler_input.candidates}
        selected: list[str] = []
        selected_set: set[str] = set()
        considered: list[str] = []
        conflict_skipped: list[str] = []
        budget_skipped: list[str] = []
        total_cost = 0
        anchor: SchedulerCandidate | None = None
        while remaining:
            conflicting = tuple(
                sorted(
                    candidate_id
                    for candidate_id in remaining
                    if conflicts[candidate_id] & selected_set
                )
            )
            for candidate_id in conflicting:
                considered.append(candidate_id)
                conflict_skipped.append(candidate_id)
                remaining.pop(candidate_id)
            if not remaining:
                break
            feasible = tuple(
                candidate
                for candidate in remaining.values()
                if total_cost + candidate.edit_cost <= budget
            )
            if not feasible:
                for candidate_id in sorted(remaining):
                    considered.append(candidate_id)
                    budget_skipped.append(candidate_id)
                break
            if anchor is None:
                chosen = min(feasible, key=lambda candidate: _spacing_anchor_key(seed, candidate))
                anchor = chosen
            elif policy is SchedulePolicy.CLUSTERED:
                chosen = min(
                    feasible,
                    key=lambda candidate: (
                        abs(candidate.center_twice - anchor.center_twice),
                        candidate.candidate_id,
                    ),
                )
            else:
                selected_candidates = tuple(
                    candidate
                    for candidate in scheduler_input.candidates
                    if candidate.candidate_id in selected_set
                )
                chosen = min(
                    feasible,
                    key=lambda candidate: (
                        -min(
                            abs(candidate.center_twice - selected_candidate.center_twice)
                            for selected_candidate in selected_candidates
                        ),
                        candidate.candidate_id,
                    ),
                )
            considered.append(chosen.candidate_id)
            selected.append(chosen.candidate_id)
            selected_set.add(chosen.candidate_id)
            total_cost += chosen.edit_cost
            remaining.pop(chosen.candidate_id)
        return self._result(
            scheduler_input,
            policy,
            seed,
            budget,
            tuple(considered),
            tuple(selected),
            tuple(conflict_skipped),
            tuple(budget_skipped),
            (),
            total_cost,
        )

    def _schedule_coverage_greedy(
        self,
        scheduler_input: KeyBlindScheduleInput,
        budget: int,
        seed: int,
    ) -> ScheduleResult:
        conflicts = _conflict_map(scheduler_input)
        remaining = {candidate.candidate_id: candidate for candidate in scheduler_input.candidates}
        selected: list[str] = []
        selected_set: set[str] = set()
        considered: list[str] = []
        conflict_skipped: list[str] = []
        budget_skipped: list[str] = []
        policy_skipped: list[str] = []
        total_cost = 0
        covered: tuple[Interval, ...] = ()
        while remaining:
            conflicting = tuple(
                sorted(
                    candidate_id
                    for candidate_id in remaining
                    if conflicts[candidate_id] & selected_set
                )
            )
            for candidate_id in conflicting:
                considered.append(candidate_id)
                conflict_skipped.append(candidate_id)
                remaining.pop(candidate_id)
            if not remaining:
                break
            feasible = tuple(
                candidate
                for candidate in remaining.values()
                if total_cost + candidate.edit_cost <= budget
            )
            if not feasible:
                for candidate_id in sorted(remaining):
                    considered.append(candidate_id)
                    budget_skipped.append(candidate_id)
                break
            best: SchedulerCandidate | None = None
            best_gain = -1
            for candidate in feasible:
                gain = _marginal_coverage(candidate, covered)
                if best is None:
                    best = candidate
                    best_gain = gain
                    continue
                left = gain * best.edit_cost
                right = best_gain * candidate.edit_cost
                if left > right or (left == right and candidate.candidate_id < best.candidate_id):
                    best = candidate
                    best_gain = gain
            if best is None:
                raise RuntimeError("coverage scheduler failed to choose from a non-empty feasible set")
            if best_gain <= 0:
                for candidate_id in sorted(remaining):
                    candidate = remaining[candidate_id]
                    considered.append(candidate_id)
                    if total_cost + candidate.edit_cost > budget:
                        budget_skipped.append(candidate_id)
                    else:
                        policy_skipped.append(candidate_id)
                break
            considered.append(best.candidate_id)
            selected.append(best.candidate_id)
            selected_set.add(best.candidate_id)
            total_cost += best.edit_cost
            covered = merge_intervals((*covered, *best.coverage_intervals))
            remaining.pop(best.candidate_id)
        return self._result(
            scheduler_input,
            SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
            seed,
            budget,
            tuple(considered),
            tuple(selected),
            tuple(conflict_skipped),
            tuple(budget_skipped),
            tuple(policy_skipped),
            total_cost,
        )

    def _result(
        self,
        scheduler_input: KeyBlindScheduleInput,
        policy: SchedulePolicy,
        seed: int,
        budget: int,
        considered: tuple[str, ...],
        selected: tuple[str, ...],
        conflict_skipped: tuple[str, ...],
        budget_skipped: tuple[str, ...],
        policy_skipped: tuple[str, ...],
        total_cost: int,
    ) -> ScheduleResult:
        candidates_by_id = {
            candidate.candidate_id: candidate
            for candidate in scheduler_input.candidates
        }
        covered_interval_size = _selected_coverage(candidates_by_id, selected)
        payload = {
            "algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            "policy": policy.value,
            "seed": seed,
            "budget": budget,
            "budget_unit": scheduler_input.budget_unit,
            "input_artifact_hash": scheduler_input.input_artifact_hash,
            "considered_candidate_ids": considered,
            "selected_candidate_ids": selected,
            "conflict_skipped_candidate_ids": conflict_skipped,
            "budget_skipped_candidate_ids": budget_skipped,
            "policy_skipped_candidate_ids": policy_skipped,
            "total_cost": total_cost,
            "covered_interval_size": covered_interval_size,
        }
        return ScheduleResult(
            CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            policy,
            seed,
            budget,
            scheduler_input.budget_unit,
            scheduler_input.input_artifact_hash,
            considered,
            selected,
            conflict_skipped,
            budget_skipped,
            policy_skipped,
            total_cost,
            covered_interval_size,
            sha256_json(payload),
        )
