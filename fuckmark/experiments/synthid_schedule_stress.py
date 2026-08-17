from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_int, require_sha256
from ..coverage import merge_intervals, union_size
from ..hashing import sha256_json, sha256_text
from ..transforms import CandidateScheduler, KeyBlindScheduleInput, ScheduleGeometryMode, SchedulePolicy, TransformRegistry
from .synthid_geometry import GeometryLabel, SynthIDGeometryBackend, build_public_candidate_coverage
from .synthid_smoke import SynthIDSmokePrompt


SYNTHID_SCHEDULE_STRESS_ALGORITHM_VERSION = "synthid-schedule-stress-v1"
SCHEDULE_STRESS_ACCESS_ID = "key-blind-public-tokenizer-geometry-v1"
_EXACT_LIMIT = 16


class StressOpportunityStatus(str, Enum):
    INELIGIBLE = "INELIGIBLE"
    NO_PUBLIC_GEOMETRY = "NO_PUBLIC_GEOMETRY"
    EXACT = "EXACT"
    APPROX_ONLY = "APPROX_ONLY"


@dataclass(frozen=True, slots=True)
class StressScheduleRow:
    prompt_id: str
    prompt_hash: str
    generation_seed: int
    label: GeometryLabel
    source_hash: str
    budget: int
    policy: SchedulePolicy
    schedule_seed: int
    realized_cost: int
    predicted_coverage: int
    selected_candidate_ids: tuple[str, ...]
    schedule_result_hash: str
    row_hash: str

    def __post_init__(self) -> None:
        require_sha256("prompt_hash", self.prompt_hash)
        require_int("generation_seed", self.generation_seed)
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        require_sha256("source_hash", self.source_hash)
        require_int("budget", self.budget)
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if not isinstance(self.policy, SchedulePolicy):
            raise TypeError("policy must be a SchedulePolicy")
        require_int("schedule_seed", self.schedule_seed)
        require_int("realized_cost", self.realized_cost)
        require_int("predicted_coverage", self.predicted_coverage)
        if not 0 <= self.realized_cost <= self.budget:
            raise ValueError("realized cost is outside budget")
        if self.predicted_coverage < 0:
            raise ValueError("predicted coverage must be non-negative")
        if not isinstance(self.selected_candidate_ids, tuple):
            raise TypeError("selected_candidate_ids must be a tuple")
        for value in self.selected_candidate_ids:
            require_sha256("selected_candidate_id", value)
        if len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected candidate IDs must be unique")
        require_sha256("schedule_result_hash", self.schedule_result_hash)
        require_sha256("row_hash", self.row_hash)
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match stress schedule row")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_hash": self.prompt_hash,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "source_hash": self.source_hash,
            "budget": self.budget,
            "policy": self.policy.value,
            "schedule_seed": self.schedule_seed,
            "realized_cost": self.realized_cost,
            "predicted_coverage": self.predicted_coverage,
            "selected_candidate_ids": self.selected_candidate_ids,
            "schedule_result_hash": self.schedule_result_hash,
        }


@dataclass(frozen=True, slots=True)
class StressOpportunity:
    prompt_id: str
    prompt_hash: str
    generation_seed: int
    label: GeometryLabel
    source_text: str
    source_hash: str
    source_token_count: int
    original_observation_count: int
    budget: int
    candidate_count: int
    geometry_positive_candidate_count: int
    isolated_coverage_sum: int
    candidate_union_coverage: int
    overlap_loss: int
    greedy_cost: int
    greedy_coverage: int
    matched_random_count: int
    mean_matched_random_coverage: float | None
    greedy_advantage_over_random: float | None
    clustered_cost: int
    clustered_coverage: int
    even_cost: int
    even_coverage: int
    exact_optimal_cost: int | None
    exact_optimal_coverage: int | None
    greedy_regret: int | None
    random_headroom_to_optimum: float | None
    status: StressOpportunityStatus
    opportunity_hash: str

    def __post_init__(self) -> None:
        require_sha256("prompt_hash", self.prompt_hash)
        require_sha256("source_hash", self.source_hash)
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if not isinstance(self.status, StressOpportunityStatus):
            raise TypeError("status must be a StressOpportunityStatus")
        for name in (
            "generation_seed",
            "source_token_count",
            "original_observation_count",
            "budget",
            "candidate_count",
            "geometry_positive_candidate_count",
            "isolated_coverage_sum",
            "candidate_union_coverage",
            "overlap_loss",
            "greedy_cost",
            "greedy_coverage",
            "matched_random_count",
            "clustered_cost",
            "clustered_coverage",
            "even_cost",
            "even_coverage",
        ):
            require_int(name, getattr(self, name))
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if not 0 <= self.geometry_positive_candidate_count <= self.candidate_count:
            raise ValueError("invalid geometry-positive candidate count")
        if self.overlap_loss != self.isolated_coverage_sum - self.candidate_union_coverage:
            raise ValueError("overlap loss does not match isolated minus union coverage")
        if self.overlap_loss < 0:
            raise ValueError("overlap loss must be non-negative")
        for name in ("greedy_cost", "clustered_cost", "even_cost"):
            if not 0 <= getattr(self, name) <= self.budget:
                raise ValueError(f"{name} is outside budget")
        if self.matched_random_count == 0:
            if self.mean_matched_random_coverage is not None or self.greedy_advantage_over_random is not None:
                raise ValueError("unmatched random baseline must withhold comparison metrics")
        else:
            mean_random = _finite("mean_matched_random_coverage", self.mean_matched_random_coverage)
            greedy_advantage = _finite("greedy_advantage_over_random", self.greedy_advantage_over_random)
            if not math.isclose(greedy_advantage, self.greedy_coverage - mean_random, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("greedy advantage does not match greedy minus random coverage")
        exact_values = (
            self.exact_optimal_cost,
            self.exact_optimal_coverage,
            self.greedy_regret,
        )
        if self.status is StressOpportunityStatus.EXACT:
            if any(value is None for value in exact_values):
                raise ValueError("exact status requires exact coverage metrics")
            for name, value in zip(
                ("exact_optimal_cost", "exact_optimal_coverage", "greedy_regret"),
                exact_values,
            ):
                require_int(name, value)
            if self.greedy_regret != self.exact_optimal_coverage - self.greedy_coverage:
                raise ValueError("greedy regret does not match exact optimum")
            if self.matched_random_count:
                expected = self.exact_optimal_coverage - float(self.mean_matched_random_coverage)
                if self.random_headroom_to_optimum is None or not math.isclose(
                    self.random_headroom_to_optimum,
                    expected,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    raise ValueError("random headroom does not match exact optimum")
            elif self.random_headroom_to_optimum is not None:
                raise ValueError("random headroom requires matched random rows")
        else:
            if any(value is not None for value in exact_values) or self.random_headroom_to_optimum is not None:
                raise ValueError("non-exact status must withhold exact coverage metrics")
        require_sha256("opportunity_hash", self.opportunity_hash)
        if self.opportunity_hash != sha256_json(self.payload()):
            raise ValueError("opportunity_hash does not match stress opportunity")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_hash": self.prompt_hash,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "source_text": self.source_text,
            "source_hash": self.source_hash,
            "source_token_count": self.source_token_count,
            "original_observation_count": self.original_observation_count,
            "budget": self.budget,
            "candidate_count": self.candidate_count,
            "geometry_positive_candidate_count": self.geometry_positive_candidate_count,
            "isolated_coverage_sum": self.isolated_coverage_sum,
            "candidate_union_coverage": self.candidate_union_coverage,
            "overlap_loss": self.overlap_loss,
            "greedy_cost": self.greedy_cost,
            "greedy_coverage": self.greedy_coverage,
            "matched_random_count": self.matched_random_count,
            "mean_matched_random_coverage": self.mean_matched_random_coverage,
            "greedy_advantage_over_random": self.greedy_advantage_over_random,
            "clustered_cost": self.clustered_cost,
            "clustered_coverage": self.clustered_coverage,
            "even_cost": self.even_cost,
            "even_coverage": self.even_coverage,
            "exact_optimal_cost": self.exact_optimal_cost,
            "exact_optimal_coverage": self.exact_optimal_coverage,
            "greedy_regret": self.greedy_regret,
            "random_headroom_to_optimum": self.random_headroom_to_optimum,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class StressSummary:
    prompt_count: int
    source_count: int
    opportunity_count: int
    exact_opportunity_count: int
    eligible_control_rate: float
    eligible_watermarked_rate: float
    overlap_control_rate: float
    overlap_watermarked_rate: float
    positive_headroom_control_rate: float
    positive_headroom_watermarked_rate: float
    mean_control_greedy_advantage: float | None
    mean_watermarked_greedy_advantage: float | None
    mean_control_random_headroom: float | None
    mean_watermarked_random_headroom: float | None


@dataclass(frozen=True, slots=True)
class SynthIDScheduleStressReport:
    algorithm_version: str
    access_id: str
    backend_id: str
    backend_version: str
    model_id: str
    transform_ruleset_hash: str
    ngram_len: int
    budgets: tuple[int, ...]
    random_seeds: tuple[int, ...]
    spacing_seed: int
    opportunities: tuple[StressOpportunity, ...]
    schedule_rows: tuple[StressScheduleRow, ...]
    summary: StressSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_SCHEDULE_STRESS_ALGORITHM_VERSION:
            raise ValueError("unsupported schedule stress algorithm version")
        if self.access_id != SCHEDULE_STRESS_ACCESS_ID:
            raise ValueError("unexpected schedule stress access identity")
        require_sha256("transform_ruleset_hash", self.transform_ruleset_hash)
        require_int("ngram_len", self.ngram_len)
        require_int("spacing_seed", self.spacing_seed)
        require_sha256("report_hash", self.report_hash)
        if self.summary.opportunity_count != len(self.opportunities):
            raise ValueError("summary opportunity count does not match report")
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match schedule stress report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "access_id": self.access_id,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "ngram_len": self.ngram_len,
            "budgets": self.budgets,
            "random_seeds": self.random_seeds,
            "spacing_seed": self.spacing_seed,
            "opportunities": self.opportunities,
            "schedule_rows": self.schedule_rows,
            "summary": self.summary,
        }


def _finite(name: str, value: float | None) -> float:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


def _row(
    prompt: SynthIDSmokePrompt,
    label: GeometryLabel,
    source_hash: str,
    policy: SchedulePolicy,
    seed: int,
    result,
) -> StressScheduleRow:
    payload = {
        "prompt_id": prompt.prompt_id,
        "prompt_hash": sha256_text(prompt.text),
        "generation_seed": prompt.seed,
        "label": label.value,
        "source_hash": source_hash,
        "budget": result.budget,
        "policy": policy.value,
        "schedule_seed": seed,
        "realized_cost": result.total_cost,
        "predicted_coverage": result.covered_interval_size,
        "selected_candidate_ids": result.selected_candidate_ids,
        "schedule_result_hash": result.result_hash,
    }
    return StressScheduleRow(
        prompt.prompt_id,
        payload["prompt_hash"],
        prompt.seed,
        label,
        source_hash,
        result.budget,
        policy,
        seed,
        result.total_cost,
        result.covered_interval_size,
        result.selected_candidate_ids,
        result.result_hash,
        sha256_json(payload),
    )


def _rate(values: tuple[bool, ...]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _mean(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return statistics.fmean(values)


def _label_values(
    opportunities: tuple[StressOpportunity, ...],
    label: GeometryLabel,
    field: str,
) -> tuple[float, ...]:
    return tuple(
        float(value)
        for row in opportunities
        if row.label is label and (value := getattr(row, field)) is not None
    )


def run_synthid_schedule_stress(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: SynthIDGeometryBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    random_seeds: Sequence[int] = tuple(range(8)),
    spacing_seed: int = 0,
) -> SynthIDScheduleStressReport:
    prompt_values = tuple(prompts)
    if not prompt_values or any(not isinstance(value, SynthIDSmokePrompt) for value in prompt_values):
        raise ValueError("prompts must contain SynthIDSmokePrompt values")
    if len({value.prompt_id for value in prompt_values}) != len(prompt_values):
        raise ValueError("prompt IDs must be unique")
    if not isinstance(backend, SynthIDGeometryBackend):
        raise TypeError("backend must satisfy SynthIDGeometryBackend")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    budget_values = tuple(sorted(set(budgets)))
    random_seed_values = tuple(sorted(set(random_seeds)))
    if not budget_values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in budget_values):
        raise ValueError("budgets must contain positive integers")
    if not random_seed_values or any(
        isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64
        for value in random_seed_values
    ):
        raise ValueError("random seeds must contain 64-bit unsigned integers")
    require_int("spacing_seed", spacing_seed)
    if not 0 <= spacing_seed < 1 << 64:
        raise ValueError("spacing_seed must be a 64-bit unsigned integer")

    sources: list[tuple[SynthIDSmokePrompt, GeometryLabel, str]] = []
    for prompt in prompt_values:
        sources.append((prompt, GeometryLabel.CONTROL, backend.generate(prompt.text, prompt.seed, watermarked=False)))
        sources.append((prompt, GeometryLabel.WATERMARKED, backend.generate(prompt.text, prompt.seed, watermarked=True)))

    opportunities: list[StressOpportunity] = []
    schedule_rows: list[StressScheduleRow] = []
    scheduler = CandidateScheduler()
    for prompt, label, source_text in sources:
        if not isinstance(source_text, str):
            raise TypeError("backend.generate must return strings")
        source_hash = sha256_text(source_text)
        source_tokens = tuple(backend.tokenize(source_text))
        observation_count = max(0, len(source_tokens) - backend.ngram_len + 1)
        enumeration = registry.enumerate(source_text)
        coverage = build_public_candidate_coverage(registry, enumeration, backend.tokenize, backend.ngram_len)
        isolated = sum(union_size(values) for values in coverage.values())
        union = union_size(tuple(interval for values in coverage.values() for interval in values))
        overlap_loss = isolated - union
        positive_count = sum(bool(values) for values in coverage.values())
        scheduler_input = KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=coverage,
            budget_unit="operation",
            geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        )
        for budget in budget_values:
            random_results = tuple(
                scheduler.schedule(scheduler_input, SchedulePolicy.RANDOM_VALID, budget, seed)
                for seed in random_seed_values
            )
            clustered = scheduler.schedule(scheduler_input, SchedulePolicy.CLUSTERED, budget, spacing_seed)
            even = scheduler.schedule(scheduler_input, SchedulePolicy.EVEN_SPACING, budget, spacing_seed)
            for seed, result in zip(random_seed_values, random_results):
                schedule_rows.append(_row(prompt, label, source_hash, SchedulePolicy.RANDOM_VALID, seed, result))
            schedule_rows.append(_row(prompt, label, source_hash, SchedulePolicy.CLUSTERED, spacing_seed, clustered))
            schedule_rows.append(_row(prompt, label, source_hash, SchedulePolicy.EVEN_SPACING, spacing_seed, even))
            if not enumeration.candidates:
                status = StressOpportunityStatus.INELIGIBLE
                greedy_cost = greedy_coverage = 0
                mean_random = greedy_advantage = None
                exact_cost = exact_coverage = greedy_regret = random_headroom = None
            elif positive_count == 0:
                status = StressOpportunityStatus.NO_PUBLIC_GEOMETRY
                greedy_cost = greedy_coverage = 0
                mean_random = greedy_advantage = None
                exact_cost = exact_coverage = greedy_regret = random_headroom = None
            else:
                greedy = scheduler.schedule(
                    scheduler_input,
                    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
                    budget,
                    spacing_seed,
                )
                schedule_rows.append(
                    _row(
                        prompt,
                        label,
                        source_hash,
                        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
                        spacing_seed,
                        greedy,
                    )
                )
                greedy_cost = greedy.total_cost
                greedy_coverage = greedy.covered_interval_size
                matched_random = tuple(result for result in random_results if result.total_cost == greedy_cost)
                if matched_random:
                    mean_random = statistics.fmean(result.covered_interval_size for result in matched_random)
                    greedy_advantage = greedy_coverage - mean_random
                else:
                    mean_random = greedy_advantage = None
                if len(enumeration.candidates) <= _EXACT_LIMIT:
                    diagnostic = scheduler.exact_coverage_diagnostic(
                        scheduler_input,
                        budget,
                        spacing_seed,
                        _EXACT_LIMIT,
                    )
                    status = StressOpportunityStatus.EXACT
                    exact_cost = diagnostic.optimal_cost
                    exact_coverage = diagnostic.optimal_coverage
                    greedy_regret = diagnostic.coverage_regret
                    random_headroom = (
                        exact_coverage - mean_random
                        if mean_random is not None
                        else None
                    )
                else:
                    status = StressOpportunityStatus.APPROX_ONLY
                    exact_cost = exact_coverage = greedy_regret = random_headroom = None
            matched_random_count = (
                sum(result.total_cost == greedy_cost for result in random_results)
                if status in (StressOpportunityStatus.EXACT, StressOpportunityStatus.APPROX_ONLY)
                else 0
            )
            payload = {
                "prompt_id": prompt.prompt_id,
                "prompt_hash": sha256_text(prompt.text),
                "generation_seed": prompt.seed,
                "label": label.value,
                "source_text": source_text,
                "source_hash": source_hash,
                "source_token_count": len(source_tokens),
                "original_observation_count": observation_count,
                "budget": budget,
                "candidate_count": len(enumeration.candidates),
                "geometry_positive_candidate_count": positive_count,
                "isolated_coverage_sum": isolated,
                "candidate_union_coverage": union,
                "overlap_loss": overlap_loss,
                "greedy_cost": greedy_cost,
                "greedy_coverage": greedy_coverage,
                "matched_random_count": matched_random_count,
                "mean_matched_random_coverage": mean_random,
                "greedy_advantage_over_random": greedy_advantage,
                "clustered_cost": clustered.total_cost,
                "clustered_coverage": clustered.covered_interval_size,
                "even_cost": even.total_cost,
                "even_coverage": even.covered_interval_size,
                "exact_optimal_cost": exact_cost,
                "exact_optimal_coverage": exact_coverage,
                "greedy_regret": greedy_regret,
                "random_headroom_to_optimum": random_headroom,
                "status": status.value,
            }
            opportunities.append(
                StressOpportunity(
                    prompt.prompt_id,
                    payload["prompt_hash"],
                    prompt.seed,
                    label,
                    source_text,
                    source_hash,
                    len(source_tokens),
                    observation_count,
                    budget,
                    len(enumeration.candidates),
                    positive_count,
                    isolated,
                    union,
                    overlap_loss,
                    greedy_cost,
                    greedy_coverage,
                    matched_random_count,
                    mean_random,
                    greedy_advantage,
                    clustered.total_cost,
                    clustered.covered_interval_size,
                    even.total_cost,
                    even.covered_interval_size,
                    exact_cost,
                    exact_coverage,
                    greedy_regret,
                    random_headroom,
                    status,
                    sha256_json(payload),
                )
            )
    opportunity_values = tuple(opportunities)
    row_values = tuple(schedule_rows)
    min_budget = budget_values[0]
    min_cells = tuple(row for row in opportunity_values if row.budget == min_budget)
    control_min = tuple(row for row in min_cells if row.label is GeometryLabel.CONTROL)
    watermark_min = tuple(row for row in min_cells if row.label is GeometryLabel.WATERMARKED)
    exact_cells = tuple(row for row in opportunity_values if row.status is StressOpportunityStatus.EXACT)
    summary = StressSummary(
        len(prompt_values),
        len(sources),
        len(opportunity_values),
        len(exact_cells),
        _rate(tuple(row.candidate_count > 0 for row in control_min)),
        _rate(tuple(row.candidate_count > 0 for row in watermark_min)),
        _rate(tuple(row.overlap_loss > 0 for row in control_min)),
        _rate(tuple(row.overlap_loss > 0 for row in watermark_min)),
        _rate(tuple((row.random_headroom_to_optimum or 0.0) > 0.0 for row in control_min)),
        _rate(tuple((row.random_headroom_to_optimum or 0.0) > 0.0 for row in watermark_min)),
        _mean(_label_values(opportunity_values, GeometryLabel.CONTROL, "greedy_advantage_over_random")),
        _mean(_label_values(opportunity_values, GeometryLabel.WATERMARKED, "greedy_advantage_over_random")),
        _mean(_label_values(opportunity_values, GeometryLabel.CONTROL, "random_headroom_to_optimum")),
        _mean(_label_values(opportunity_values, GeometryLabel.WATERMARKED, "random_headroom_to_optimum")),
    )
    payload = {
        "algorithm_version": SYNTHID_SCHEDULE_STRESS_ALGORITHM_VERSION,
        "access_id": SCHEDULE_STRESS_ACCESS_ID,
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "transform_ruleset_hash": registry.ruleset_hash,
        "ngram_len": backend.ngram_len,
        "budgets": budget_values,
        "random_seeds": random_seed_values,
        "spacing_seed": spacing_seed,
        "opportunities": opportunity_values,
        "schedule_rows": row_values,
        "summary": summary,
    }
    return SynthIDScheduleStressReport(
        SYNTHID_SCHEDULE_STRESS_ALGORITHM_VERSION,
        SCHEDULE_STRESS_ACCESS_ID,
        backend.backend_id,
        backend.backend_version,
        backend.model_id,
        registry.ruleset_hash,
        backend.ngram_len,
        budget_values,
        random_seed_values,
        spacing_seed,
        opportunity_values,
        row_values,
        summary,
        sha256_json(payload),
    )
