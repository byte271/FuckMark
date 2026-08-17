from __future__ import annotations

import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_int, require_sha256
from ..coverage import Interval, union_size
from ..hashing import sha256_json
from ..public_eligibility import build_huggingface_public_eligibility
from ..transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    TransformRegistry,
)
from .synthid_eligible_geometry import filter_candidate_coverage_by_public_eligibility
from .synthid_geometry import build_public_candidate_coverage


SYNTHID_GEOMETRY_HEADROOM_ALGORITHM_VERSION = "synthid-geometry-headroom-v1"


class HeadroomBudgetStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    ELIGIBLE_EMPTY = "ELIGIBLE_EMPTY"
    BOTH_EMPTY = "BOTH_EMPTY"


@dataclass(frozen=True, slots=True)
class GeometryRankRow:
    candidate_id: str
    all_coverage: int
    eligible_coverage: int
    all_rank: int
    eligible_rank: int
    rank_displacement: int
    retention_fraction: float | None
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("candidate_id", self.candidate_id)
        for name in (
            "all_coverage",
            "eligible_coverage",
            "all_rank",
            "eligible_rank",
            "rank_displacement",
        ):
            require_int(name, getattr(self, name))
        if self.all_coverage < 0 or self.eligible_coverage < 0:
            raise ValueError("coverage counts must be non-negative")
        if self.eligible_coverage > self.all_coverage:
            raise ValueError("eligible coverage cannot exceed all-observation coverage")
        if self.all_rank <= 0 or self.eligible_rank <= 0:
            raise ValueError("ranks must be positive")
        if self.rank_displacement != abs(self.all_rank - self.eligible_rank):
            raise ValueError("rank_displacement does not match ranks")
        if self.all_coverage == 0:
            if self.retention_fraction is not None:
                raise ValueError("zero all-observation coverage must withhold retention fraction")
        else:
            if self.retention_fraction is None:
                raise ValueError("positive all-observation coverage requires retention fraction")
            if not 0.0 <= self.retention_fraction <= 1.0:
                raise ValueError("retention_fraction must lie in [0, 1]")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match geometry rank row")

    def payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "all_coverage": self.all_coverage,
            "eligible_coverage": self.eligible_coverage,
            "all_rank": self.all_rank,
            "eligible_rank": self.eligible_rank,
            "rank_displacement": self.rank_displacement,
            "retention_fraction": self.retention_fraction,
        }


@dataclass(frozen=True, slots=True)
class GeometryBudgetHeadroom:
    budget: int
    status: HeadroomBudgetStatus
    all_greedy_selected_candidate_ids: tuple[str, ...]
    eligible_greedy_selected_candidate_ids: tuple[str, ...]
    greedy_same_selection: bool | None
    all_greedy_coverage: int | None
    eligible_greedy_coverage: int | None
    all_selection_under_eligible_coverage: int | None
    eligible_selection_under_all_coverage: int | None
    exact_diagnostic_available: bool
    exact_all_selected_candidate_ids: tuple[str, ...]
    exact_eligible_selected_candidate_ids: tuple[str, ...]
    exact_same_selection: bool | None
    all_greedy_regret: int | None
    eligible_greedy_regret: int | None
    row_hash: str

    def __post_init__(self) -> None:
        require_int("budget", self.budget)
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if not isinstance(self.status, HeadroomBudgetStatus):
            raise TypeError("status must be a HeadroomBudgetStatus")
        for name, values in (
            ("all_greedy_selected_candidate_ids", self.all_greedy_selected_candidate_ids),
            ("eligible_greedy_selected_candidate_ids", self.eligible_greedy_selected_candidate_ids),
            ("exact_all_selected_candidate_ids", self.exact_all_selected_candidate_ids),
            ("exact_eligible_selected_candidate_ids", self.exact_eligible_selected_candidate_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
            for value in values:
                require_sha256(name, value)
        for name in ("greedy_same_selection", "exact_same_selection"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be bool or None")
        if not isinstance(self.exact_diagnostic_available, bool):
            raise TypeError("exact_diagnostic_available must be a bool")
        for name in (
            "all_greedy_coverage",
            "eligible_greedy_coverage",
            "all_selection_under_eligible_coverage",
            "eligible_selection_under_all_coverage",
            "all_greedy_regret",
            "eligible_greedy_regret",
        ):
            value = getattr(self, name)
            if value is not None:
                require_int(name, value)
                if value < 0:
                    raise ValueError(f"{name} must be non-negative")
        if self.status is HeadroomBudgetStatus.SCHEDULED:
            required = (
                self.greedy_same_selection,
                self.all_greedy_coverage,
                self.eligible_greedy_coverage,
                self.all_selection_under_eligible_coverage,
                self.eligible_selection_under_all_coverage,
            )
            if any(value is None for value in required):
                raise ValueError("scheduled budget rows require greedy comparison metrics")
        else:
            if self.greedy_same_selection is not None:
                raise ValueError("empty-geometry rows must withhold greedy selection comparison")
        if self.exact_diagnostic_available:
            if self.exact_same_selection is None or self.all_greedy_regret is None or self.eligible_greedy_regret is None:
                raise ValueError("exact diagnostic rows require exact comparison metrics")
        else:
            if self.exact_same_selection is not None or self.all_greedy_regret is not None or self.eligible_greedy_regret is not None:
                raise ValueError("unavailable exact diagnostics must withhold exact comparison metrics")
            if self.exact_all_selected_candidate_ids or self.exact_eligible_selected_candidate_ids:
                raise ValueError("unavailable exact diagnostics must not expose exact selections")
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match geometry budget headroom")

    def payload(self) -> dict[str, object]:
        return {
            "budget": self.budget,
            "status": self.status.value,
            "all_greedy_selected_candidate_ids": self.all_greedy_selected_candidate_ids,
            "eligible_greedy_selected_candidate_ids": self.eligible_greedy_selected_candidate_ids,
            "greedy_same_selection": self.greedy_same_selection,
            "all_greedy_coverage": self.all_greedy_coverage,
            "eligible_greedy_coverage": self.eligible_greedy_coverage,
            "all_selection_under_eligible_coverage": self.all_selection_under_eligible_coverage,
            "eligible_selection_under_all_coverage": self.eligible_selection_under_all_coverage,
            "exact_diagnostic_available": self.exact_diagnostic_available,
            "exact_all_selected_candidate_ids": self.exact_all_selected_candidate_ids,
            "exact_eligible_selected_candidate_ids": self.exact_eligible_selected_candidate_ids,
            "exact_same_selection": self.exact_same_selection,
            "all_greedy_regret": self.all_greedy_regret,
            "eligible_greedy_regret": self.eligible_greedy_regret,
        }


@dataclass(frozen=True, slots=True)
class GeometryHeadroomSummary:
    candidate_count: int
    all_positive_candidate_count: int
    eligible_positive_candidate_count: int
    top_positive_candidate_same: bool | None
    spearman_rank_correlation: float | None
    mean_absolute_rank_displacement: float
    budget_count: int
    scheduled_budget_count: int
    greedy_selection_disagreement_count: int
    exact_budget_count: int
    exact_selection_disagreement_count: int
    positive_all_zero_eligible_candidate_count: int


@dataclass(frozen=True, slots=True)
class SynthIDGeometryHeadroomReport:
    algorithm_version: str
    all_input_hash: str
    eligible_input_hash: str
    enumeration_hash: str
    rank_rows: tuple[GeometryRankRow, ...]
    budget_rows: tuple[GeometryBudgetHeadroom, ...]
    summary: GeometryHeadroomSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_GEOMETRY_HEADROOM_ALGORITHM_VERSION:
            raise ValueError("unsupported geometry headroom algorithm version")
        require_sha256("all_input_hash", self.all_input_hash)
        require_sha256("eligible_input_hash", self.eligible_input_hash)
        require_sha256("enumeration_hash", self.enumeration_hash)
        if not isinstance(self.rank_rows, tuple) or any(not isinstance(row, GeometryRankRow) for row in self.rank_rows):
            raise TypeError("rank_rows must contain GeometryRankRow values")
        if not isinstance(self.budget_rows, tuple) or any(not isinstance(row, GeometryBudgetHeadroom) for row in self.budget_rows):
            raise TypeError("budget_rows must contain GeometryBudgetHeadroom values")
        if self.summary.candidate_count != len(self.rank_rows) or self.summary.budget_count != len(self.budget_rows):
            raise ValueError("headroom summary counts do not match report rows")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match geometry headroom report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "all_input_hash": self.all_input_hash,
            "eligible_input_hash": self.eligible_input_hash,
            "enumeration_hash": self.enumeration_hash,
            "rank_rows": self.rank_rows,
            "budget_rows": self.budget_rows,
            "summary": self.summary,
        }


def _coverage_sizes(scheduler_input: KeyBlindScheduleInput) -> dict[str, int]:
    return {
        candidate.candidate_id: union_size(candidate.coverage_intervals)
        for candidate in scheduler_input.candidates
    }


def _selected_coverage(scheduler_input: KeyBlindScheduleInput, selected: Sequence[str]) -> int:
    by_id = {candidate.candidate_id: candidate for candidate in scheduler_input.candidates}
    intervals: list[Interval] = []
    for candidate_id in selected:
        intervals.extend(by_id[candidate_id].coverage_intervals)
    return union_size(intervals)


def _rank_rows(all_input: KeyBlindScheduleInput, eligible_input: KeyBlindScheduleInput) -> tuple[GeometryRankRow, ...]:
    all_sizes = _coverage_sizes(all_input)
    eligible_sizes = _coverage_sizes(eligible_input)
    all_order = tuple(sorted(all_sizes, key=lambda candidate_id: (-all_sizes[candidate_id], candidate_id)))
    eligible_order = tuple(sorted(eligible_sizes, key=lambda candidate_id: (-eligible_sizes[candidate_id], candidate_id)))
    all_rank = {candidate_id: index + 1 for index, candidate_id in enumerate(all_order)}
    eligible_rank = {candidate_id: index + 1 for index, candidate_id in enumerate(eligible_order)}
    rows = []
    for candidate_id in sorted(all_sizes):
        all_coverage = all_sizes[candidate_id]
        eligible_coverage = eligible_sizes[candidate_id]
        retention = None if all_coverage == 0 else eligible_coverage / all_coverage
        payload = {
            "candidate_id": candidate_id,
            "all_coverage": all_coverage,
            "eligible_coverage": eligible_coverage,
            "all_rank": all_rank[candidate_id],
            "eligible_rank": eligible_rank[candidate_id],
            "rank_displacement": abs(all_rank[candidate_id] - eligible_rank[candidate_id]),
            "retention_fraction": retention,
        }
        rows.append(
            GeometryRankRow(
                candidate_id,
                all_coverage,
                eligible_coverage,
                all_rank[candidate_id],
                eligible_rank[candidate_id],
                payload["rank_displacement"],
                retention,
                sha256_json(payload),
            )
        )
    return tuple(rows)


def _spearman(rows: tuple[GeometryRankRow, ...]) -> float | None:
    count = len(rows)
    if count < 2:
        return None
    displacement_squared = sum((row.all_rank - row.eligible_rank) ** 2 for row in rows)
    return 1.0 - (6.0 * displacement_squared) / (count * (count * count - 1))


def _top_positive_candidate(rows: tuple[GeometryRankRow, ...], field: str, rank_field: str) -> str | None:
    positive = tuple(row for row in rows if getattr(row, field) > 0)
    if not positive:
        return None
    return min(positive, key=lambda row: getattr(row, rank_field)).candidate_id


def _budget_row(
    all_input: KeyBlindScheduleInput,
    eligible_input: KeyBlindScheduleInput,
    budget: int,
    seed: int,
    exact_max_candidates: int,
) -> GeometryBudgetHeadroom:
    scheduler = CandidateScheduler()
    all_positive = any(candidate.coverage_intervals for candidate in all_input.candidates)
    eligible_positive = any(candidate.coverage_intervals for candidate in eligible_input.candidates)
    if not all_positive:
        status = HeadroomBudgetStatus.BOTH_EMPTY
    elif not eligible_positive:
        status = HeadroomBudgetStatus.ELIGIBLE_EMPTY
    else:
        status = HeadroomBudgetStatus.SCHEDULED
    all_selected: tuple[str, ...] = ()
    eligible_selected: tuple[str, ...] = ()
    greedy_same = None
    all_coverage = None
    eligible_coverage = None
    all_under_eligible = None
    eligible_under_all = None
    if status is HeadroomBudgetStatus.SCHEDULED:
        all_result = scheduler.schedule(all_input, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND, budget, seed)
        eligible_result = scheduler.schedule(eligible_input, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND, budget, seed)
        all_selected = all_result.selected_candidate_ids
        eligible_selected = eligible_result.selected_candidate_ids
        greedy_same = all_selected == eligible_selected
        all_coverage = all_result.covered_interval_size
        eligible_coverage = eligible_result.covered_interval_size
        all_under_eligible = _selected_coverage(eligible_input, all_selected)
        eligible_under_all = _selected_coverage(all_input, eligible_selected)
    exact_available = (
        status is HeadroomBudgetStatus.SCHEDULED
        and len(all_input.candidates) <= exact_max_candidates
    )
    exact_all_selected: tuple[str, ...] = ()
    exact_eligible_selected: tuple[str, ...] = ()
    exact_same = None
    all_regret = None
    eligible_regret = None
    if exact_available:
        all_exact = scheduler.exact_coverage_diagnostic(
            all_input,
            budget,
            seed,
            max_candidates=exact_max_candidates,
        )
        eligible_exact = scheduler.exact_coverage_diagnostic(
            eligible_input,
            budget,
            seed,
            max_candidates=exact_max_candidates,
        )
        exact_all_selected = all_exact.optimal_selected_candidate_ids
        exact_eligible_selected = eligible_exact.optimal_selected_candidate_ids
        exact_same = exact_all_selected == exact_eligible_selected
        all_regret = all_exact.coverage_regret
        eligible_regret = eligible_exact.coverage_regret
    payload = {
        "budget": budget,
        "status": status.value,
        "all_greedy_selected_candidate_ids": all_selected,
        "eligible_greedy_selected_candidate_ids": eligible_selected,
        "greedy_same_selection": greedy_same,
        "all_greedy_coverage": all_coverage,
        "eligible_greedy_coverage": eligible_coverage,
        "all_selection_under_eligible_coverage": all_under_eligible,
        "eligible_selection_under_all_coverage": eligible_under_all,
        "exact_diagnostic_available": exact_available,
        "exact_all_selected_candidate_ids": exact_all_selected,
        "exact_eligible_selected_candidate_ids": exact_eligible_selected,
        "exact_same_selection": exact_same,
        "all_greedy_regret": all_regret,
        "eligible_greedy_regret": eligible_regret,
    }
    return GeometryBudgetHeadroom(
        budget,
        status,
        all_selected,
        eligible_selected,
        greedy_same,
        all_coverage,
        eligible_coverage,
        all_under_eligible,
        eligible_under_all,
        exact_available,
        exact_all_selected,
        exact_eligible_selected,
        exact_same,
        all_regret,
        eligible_regret,
        sha256_json(payload),
    )


def analyze_geometry_headroom(
    all_input: KeyBlindScheduleInput,
    eligible_input: KeyBlindScheduleInput,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    seed: int = 0,
    exact_max_candidates: int = 16,
) -> SynthIDGeometryHeadroomReport:
    if not isinstance(all_input, KeyBlindScheduleInput) or not isinstance(eligible_input, KeyBlindScheduleInput):
        raise TypeError("all_input and eligible_input must be KeyBlindScheduleInput values")
    if all_input.enumeration_hash != eligible_input.enumeration_hash:
        raise ValueError("geometry inputs must share one candidate enumeration")
    if all_input.conflicts != eligible_input.conflicts:
        raise ValueError("geometry inputs must share identical conflict geometry")
    if tuple((row.candidate_id, row.start, row.end, row.edit_cost) for row in all_input.candidates) != tuple(
        (row.candidate_id, row.start, row.end, row.edit_cost) for row in eligible_input.candidates
    ):
        raise ValueError("geometry inputs must share identical candidate identity and cost geometry")
    if all_input.geometry_mode is not ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC:
        raise ValueError("all_input must use public tokenizer-aware geometry")
    if eligible_input.geometry_mode is not ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC:
        raise ValueError("eligible_input must use public tokenizer-aware geometry")
    budget_values = tuple(sorted(set(budgets)))
    if not budget_values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in budget_values):
        raise ValueError("budgets must contain positive integers")
    require_int("seed", seed)
    if not 0 <= seed < 1 << 64:
        raise ValueError("seed must be a 64-bit unsigned integer")
    require_int("exact_max_candidates", exact_max_candidates)
    if not 1 <= exact_max_candidates <= 16:
        raise ValueError("exact_max_candidates must lie in [1, 16]")
    rank_rows = _rank_rows(all_input, eligible_input)
    for row in rank_rows:
        if row.eligible_coverage > row.all_coverage:
            raise ValueError("eligible geometry must be a subset of all-observation geometry")
    budget_rows = tuple(
        _budget_row(all_input, eligible_input, budget, seed, exact_max_candidates)
        for budget in budget_values
    )
    all_top = _top_positive_candidate(rank_rows, "all_coverage", "all_rank")
    eligible_top = _top_positive_candidate(rank_rows, "eligible_coverage", "eligible_rank")
    top_same = None if all_top is None or eligible_top is None else all_top == eligible_top
    scheduled = tuple(row for row in budget_rows if row.status is HeadroomBudgetStatus.SCHEDULED)
    exact = tuple(row for row in budget_rows if row.exact_diagnostic_available)
    summary = GeometryHeadroomSummary(
        len(rank_rows),
        sum(row.all_coverage > 0 for row in rank_rows),
        sum(row.eligible_coverage > 0 for row in rank_rows),
        top_same,
        _spearman(rank_rows),
        0.0 if not rank_rows else statistics.fmean(row.rank_displacement for row in rank_rows),
        len(budget_rows),
        len(scheduled),
        sum(row.greedy_same_selection is False for row in scheduled),
        len(exact),
        sum(row.exact_same_selection is False for row in exact),
        sum(row.all_coverage > 0 and row.eligible_coverage == 0 for row in rank_rows),
    )
    payload = {
        "algorithm_version": SYNTHID_GEOMETRY_HEADROOM_ALGORITHM_VERSION,
        "all_input_hash": all_input.input_artifact_hash,
        "eligible_input_hash": eligible_input.input_artifact_hash,
        "enumeration_hash": all_input.enumeration_hash,
        "rank_rows": rank_rows,
        "budget_rows": budget_rows,
        "summary": summary,
    }
    return SynthIDGeometryHeadroomReport(
        SYNTHID_GEOMETRY_HEADROOM_ALGORITHM_VERSION,
        all_input.input_artifact_hash,
        eligible_input.input_artifact_hash,
        all_input.enumeration_hash,
        rank_rows,
        budget_rows,
        summary,
        sha256_json(payload),
    )


def build_public_eligibility_geometry_headroom(
    source_text: str,
    tokenizer: Callable[[str], Sequence[int]],
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    seed: int = 0,
    exact_max_candidates: int = 16,
) -> SynthIDGeometryHeadroomReport:
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    token_ids = tuple(tokenizer(source_text))
    eligibility = build_huggingface_public_eligibility(
        token_ids,
        eos_token_id,
        ngram_len,
        context_history_size,
    )
    enumeration = registry.enumerate(source_text)
    all_coverage = build_public_candidate_coverage(
        registry,
        enumeration,
        tokenizer,
        ngram_len,
    )
    eligible_coverage = filter_candidate_coverage_by_public_eligibility(all_coverage, eligibility)
    all_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=all_coverage,
        budget_unit="operation",
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    eligible_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=eligible_coverage,
        budget_unit="operation",
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    return analyze_geometry_headroom(
        all_input,
        eligible_input,
        budgets=budgets,
        seed=seed,
        exact_max_candidates=exact_max_candidates,
    )
