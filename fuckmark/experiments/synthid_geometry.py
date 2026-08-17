from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from .._validation import require_int, require_sha256
from ..alignment import align_tokens
from ..coverage import Interval
from ..hashing import sha256_json, sha256_text
from ..observations import StructuralObservationState, structural_observation_diff, summarize_structural_observations
from ..transforms import (
    CandidateEnumeration,
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    TransformRegistry,
)
from .synthid_smoke import SynthIDSmokePrompt


SYNTHID_GEOMETRY_ALGORITHM_VERSION = "synthid-open-geometry-pilot-v1"
SELECTION_ACCESS_ID = "key-blind-public-tokenizer-geometry-v1"


class GeometryLabel(str, Enum):
    CONTROL = "CONTROL"
    WATERMARKED = "WATERMARKED"


class GeometryPairStatus(str, Enum):
    MATCHED = "MATCHED"
    INELIGIBLE = "INELIGIBLE"
    NO_MATCHED_RANDOM = "NO_MATCHED_RANDOM"


@runtime_checkable
class SynthIDGeometryBackend(Protocol):
    @property
    def backend_id(self) -> str: ...
    @property
    def backend_version(self) -> str: ...
    @property
    def model_id(self) -> str: ...
    @property
    def detector_id(self) -> str: ...
    @property
    def detector_config_hash(self) -> str: ...
    @property
    def ngram_len(self) -> int: ...
    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str: ...
    def tokenize(self, text: str) -> tuple[int, ...]: ...
    def score(self, text: str) -> float: ...


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _intervals(indices: Sequence[int]) -> tuple[Interval, ...]:
    values = tuple(sorted(set(indices)))
    if not values:
        return ()
    output: list[Interval] = []
    start = values[0]
    end = start + 1
    for value in values[1:]:
        if value == end:
            end += 1
        else:
            output.append(Interval(start, end))
            start, end = value, value + 1
    output.append(Interval(start, end))
    return tuple(output)


def build_public_candidate_coverage(
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    tokenizer,
    ngram_len: int,
) -> dict[str, tuple[Interval, ...]]:
    """Map candidates to original n-gram observations changed by each candidate alone.

    The mapping uses only source text, deterministic candidate rules, and public tokenizer
    geometry. It never reads watermark keys, g-values, detector scores, or decisions.
    """
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    if not isinstance(enumeration, CandidateEnumeration):
        raise TypeError("enumeration must be a CandidateEnumeration")
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable")
    require_int("ngram_len", ngram_len)
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    original = tuple(tokenizer(enumeration.input_text))
    coverage: dict[str, tuple[Interval, ...]] = {}
    for candidate in enumeration.candidates:
        single = registry.apply(enumeration, (candidate.candidate_id,), seed=0)
        transformed = tuple(tokenizer(single.output_text))
        alignment = align_tokens(original, transformed)
        diffs = structural_observation_diff(original, transformed, ngram_len, alignment)
        coverage[candidate.candidate_id] = _intervals(
            tuple(
                row.original_index
                for row in diffs
                if row.state is not StructuralObservationState.PRESERVED
            )
        )
    return coverage


@dataclass(frozen=True, slots=True)
class GeometryVariant:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    budget: int
    policy: SchedulePolicy
    schedule_seed: int
    source_text: str
    transformed_text: str
    candidate_count: int
    geometry_positive_candidate_count: int
    source_token_count: int
    transformed_token_count: int
    original_observation_count: int
    predicted_coverage_count: int
    selected_count: int
    realized_edit_cost: int
    preserved_count: int
    replaced_count: int
    unmapped_count: int
    pristine_score: float
    transformed_score: float
    schedule_result_hash: str
    variant_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if self.policy not in (SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND):
            raise ValueError("unsupported geometry policy")
        for name in (
            "generation_seed", "budget", "schedule_seed", "candidate_count",
            "geometry_positive_candidate_count", "source_token_count", "transformed_token_count",
            "original_observation_count", "predicted_coverage_count", "selected_count",
            "realized_edit_cost", "preserved_count", "replaced_count", "unmapped_count",
        ):
            require_int(name, getattr(self, name))
        if self.budget <= 0 or self.realized_edit_cost < 0 or self.realized_edit_cost > self.budget:
            raise ValueError("invalid budget or realized edit cost")
        if self.realized_edit_cost != self.selected_count:
            raise ValueError("pilot uses unit operation costs")
        if self.geometry_positive_candidate_count > self.candidate_count:
            raise ValueError("geometry-positive candidate count exceeds candidate count")
        if self.preserved_count + self.replaced_count + self.unmapped_count != self.original_observation_count:
            raise ValueError("observation counts do not sum to original count")
        if self.predicted_coverage_count > self.original_observation_count:
            raise ValueError("predicted coverage exceeds original observation count")
        object.__setattr__(self, "pristine_score", _finite("pristine_score", self.pristine_score))
        object.__setattr__(self, "transformed_score", _finite("transformed_score", self.transformed_score))
        require_sha256("schedule_result_hash", self.schedule_result_hash)
        require_sha256("variant_hash", self.variant_hash)
        if self.realized_edit_cost == 0:
            if self.source_text != self.transformed_text or self.pristine_score != self.transformed_score:
                raise ValueError("zero-cost variants must preserve text and score")
        elif self.source_text == self.transformed_text:
            raise ValueError("positive-cost variants must change text")
        if self.variant_hash != sha256_json(self.payload()):
            raise ValueError("variant_hash does not match geometry variant")

    @property
    def disrupted_count(self) -> int:
        return self.replaced_count + self.unmapped_count

    @property
    def disruption_per_edit(self) -> float:
        return 0.0 if self.realized_edit_cost == 0 else self.disrupted_count / self.realized_edit_cost

    @property
    def score_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "budget": self.budget,
            "policy": self.policy.value,
            "schedule_seed": self.schedule_seed,
            "source_text": self.source_text,
            "transformed_text": self.transformed_text,
            "candidate_count": self.candidate_count,
            "geometry_positive_candidate_count": self.geometry_positive_candidate_count,
            "source_token_count": self.source_token_count,
            "transformed_token_count": self.transformed_token_count,
            "original_observation_count": self.original_observation_count,
            "predicted_coverage_count": self.predicted_coverage_count,
            "selected_count": self.selected_count,
            "realized_edit_cost": self.realized_edit_cost,
            "preserved_count": self.preserved_count,
            "replaced_count": self.replaced_count,
            "unmapped_count": self.unmapped_count,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "schedule_result_hash": self.schedule_result_hash,
        }


@dataclass(frozen=True, slots=True)
class GeometryPair:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    budget: int
    greedy_variant_hash: str
    matched_random_variant_hashes: tuple[str, ...]
    disruption_advantage: float | None
    score_drop_advantage: float | None
    status: GeometryPairStatus
    pair_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel) or not isinstance(self.status, GeometryPairStatus):
            raise TypeError("invalid pair enum")
        require_int("budget", self.budget)
        require_sha256("greedy_variant_hash", self.greedy_variant_hash)
        require_sha256("pair_hash", self.pair_hash)
        for value in self.matched_random_variant_hashes:
            require_sha256("matched_random_variant_hash", value)
        if self.status is GeometryPairStatus.MATCHED:
            if not self.matched_random_variant_hashes:
                raise ValueError("matched pair requires random variants")
            _finite("disruption_advantage", self.disruption_advantage)
            _finite("score_drop_advantage", self.score_drop_advantage)
        elif self.disruption_advantage is not None or self.score_drop_advantage is not None:
            raise ValueError("unmatched pairs must withhold comparison metrics")
        if self.pair_hash != sha256_json(self.payload()):
            raise ValueError("pair_hash does not match geometry pair")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "budget": self.budget,
            "greedy_variant_hash": self.greedy_variant_hash,
            "matched_random_variant_hashes": self.matched_random_variant_hashes,
            "disruption_advantage": self.disruption_advantage,
            "score_drop_advantage": self.score_drop_advantage,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class GeometrySummary:
    prompt_count: int
    source_count: int
    variant_count: int
    budgets: tuple[int, ...]
    random_seed_count: int
    min_budget_control_eligible_rate: float
    min_budget_watermarked_eligible_rate: float
    matched_pair_count: int
    mean_control_disruption_advantage: float | None
    mean_watermarked_disruption_advantage: float | None
    mean_control_score_drop_advantage: float | None
    mean_watermarked_score_drop_advantage: float | None


@dataclass(frozen=True, slots=True)
class SynthIDGeometryReport:
    algorithm_version: str
    selection_access_id: str
    backend_id: str
    backend_version: str
    model_id: str
    detector_id: str
    detector_config_hash: str
    transform_ruleset_hash: str
    ngram_len: int
    greedy_seed: int
    random_seeds: tuple[int, ...]
    variants: tuple[GeometryVariant, ...]
    pairs: tuple[GeometryPair, ...]
    summary: GeometrySummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported geometry algorithm version")
        if self.selection_access_id != SELECTION_ACCESS_ID:
            raise ValueError("unexpected selection access identity")
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_sha256("transform_ruleset_hash", self.transform_ruleset_hash)
        require_sha256("report_hash", self.report_hash)
        if self.summary.variant_count != len(self.variants):
            raise ValueError("summary variant count does not match report")
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match geometry report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "selection_access_id": self.selection_access_id,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "detector_id": self.detector_id,
            "detector_config_hash": self.detector_config_hash,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "ngram_len": self.ngram_len,
            "greedy_seed": self.greedy_seed,
            "random_seeds": self.random_seeds,
            "variants": self.variants,
            "pairs": self.pairs,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class _Prepared:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    budget: int
    policy: SchedulePolicy
    schedule_seed: int
    source_text: str
    transformed_text: str
    candidate_count: int
    geometry_positive_candidate_count: int
    source_token_count: int
    transformed_token_count: int
    original_observation_count: int
    predicted_coverage_count: int
    selected_count: int
    realized_edit_cost: int
    preserved_count: int
    replaced_count: int
    unmapped_count: int
    schedule_result_hash: str


def _prepare(
    prompt: SynthIDSmokePrompt,
    label: GeometryLabel,
    source_text: str,
    source_tokens: tuple[int, ...],
    backend: SynthIDGeometryBackend,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    scheduler_input: KeyBlindScheduleInput,
    policy: SchedulePolicy,
    budget: int,
    schedule_seed: int,
) -> _Prepared:
    schedule = CandidateScheduler().schedule(scheduler_input, policy, budget, schedule_seed)
    transformed = registry.apply(enumeration, schedule.selected_candidate_ids, seed=schedule_seed)
    transformed_tokens = tuple(backend.tokenize(transformed.output_text))
    alignment = align_tokens(source_tokens, transformed_tokens)
    diffs = structural_observation_diff(source_tokens, transformed_tokens, backend.ngram_len, alignment)
    summary = summarize_structural_observations(source_tokens, transformed_tokens, backend.ngram_len, diffs)
    return _Prepared(
        prompt.prompt_id,
        prompt.seed,
        label,
        budget,
        policy,
        schedule_seed,
        source_text,
        transformed.output_text,
        len(enumeration.candidates),
        sum(bool(row.coverage_intervals) for row in scheduler_input.candidates),
        len(source_tokens),
        len(transformed_tokens),
        summary.original_count,
        schedule.covered_interval_size,
        len(schedule.selected_candidate_ids),
        schedule.total_cost,
        summary.preserved_count,
        summary.replaced_count,
        summary.unmapped_count,
        schedule.result_hash,
    )


def _variant(value: _Prepared, pristine_score: float, transformed_score: float) -> GeometryVariant:
    payload = {
        "prompt_id": value.prompt_id,
        "generation_seed": value.generation_seed,
        "label": value.label.value,
        "budget": value.budget,
        "policy": value.policy.value,
        "schedule_seed": value.schedule_seed,
        "source_text": value.source_text,
        "transformed_text": value.transformed_text,
        "candidate_count": value.candidate_count,
        "geometry_positive_candidate_count": value.geometry_positive_candidate_count,
        "source_token_count": value.source_token_count,
        "transformed_token_count": value.transformed_token_count,
        "original_observation_count": value.original_observation_count,
        "predicted_coverage_count": value.predicted_coverage_count,
        "selected_count": value.selected_count,
        "realized_edit_cost": value.realized_edit_cost,
        "preserved_count": value.preserved_count,
        "replaced_count": value.replaced_count,
        "unmapped_count": value.unmapped_count,
        "pristine_score": pristine_score,
        "transformed_score": transformed_score,
        "schedule_result_hash": value.schedule_result_hash,
    }
    return GeometryVariant(
        value.prompt_id,
        value.generation_seed,
        value.label,
        value.budget,
        value.policy,
        value.schedule_seed,
        value.source_text,
        value.transformed_text,
        value.candidate_count,
        value.geometry_positive_candidate_count,
        value.source_token_count,
        value.transformed_token_count,
        value.original_observation_count,
        value.predicted_coverage_count,
        value.selected_count,
        value.realized_edit_cost,
        value.preserved_count,
        value.replaced_count,
        value.unmapped_count,
        pristine_score,
        transformed_score,
        value.schedule_result_hash,
        sha256_json(payload),
    )


def _pair(greedy: GeometryVariant, randoms: tuple[GeometryVariant, ...]) -> GeometryPair:
    matched = tuple(row for row in randoms if row.realized_edit_cost == greedy.realized_edit_cost > 0)
    if greedy.realized_edit_cost == 0:
        status = GeometryPairStatus.INELIGIBLE
        disruption_advantage = score_drop_advantage = None
    elif not matched:
        status = GeometryPairStatus.NO_MATCHED_RANDOM
        disruption_advantage = score_drop_advantage = None
    else:
        status = GeometryPairStatus.MATCHED
        disruption_advantage = greedy.disruption_per_edit - statistics.fmean(row.disruption_per_edit for row in matched)
        score_drop_advantage = greedy.score_drop - statistics.fmean(row.score_drop for row in matched)
    matched_hashes = tuple(sorted(row.variant_hash for row in matched))
    payload = {
        "prompt_id": greedy.prompt_id,
        "generation_seed": greedy.generation_seed,
        "label": greedy.label.value,
        "budget": greedy.budget,
        "greedy_variant_hash": greedy.variant_hash,
        "matched_random_variant_hashes": matched_hashes,
        "disruption_advantage": disruption_advantage,
        "score_drop_advantage": score_drop_advantage,
        "status": status.value,
    }
    return GeometryPair(
        greedy.prompt_id,
        greedy.generation_seed,
        greedy.label,
        greedy.budget,
        greedy.variant_hash,
        matched_hashes,
        disruption_advantage,
        score_drop_advantage,
        status,
        sha256_json(payload),
    )


def _mean_pair(pairs: tuple[GeometryPair, ...], label: GeometryLabel, field: str) -> float | None:
    values = tuple(
        float(getattr(row, field))
        for row in pairs
        if row.status is GeometryPairStatus.MATCHED and row.label is label
    )
    return statistics.fmean(values) if values else None


def run_synthid_geometry_pilot(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: SynthIDGeometryBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2),
    random_seeds: Sequence[int] = tuple(range(8)),
    greedy_seed: int = 0,
) -> SynthIDGeometryReport:
    prompt_values = tuple(prompts)
    if not prompt_values or any(not isinstance(row, SynthIDSmokePrompt) for row in prompt_values):
        raise ValueError("prompts must contain SynthIDSmokePrompt values")
    if len({row.prompt_id for row in prompt_values}) != len(prompt_values):
        raise ValueError("prompt IDs must be unique")
    if not isinstance(backend, SynthIDGeometryBackend):
        raise TypeError("backend must satisfy SynthIDGeometryBackend")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    budget_values = tuple(sorted(set(budgets)))
    random_seed_values = tuple(sorted(set(random_seeds)))
    if not budget_values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in budget_values):
        raise ValueError("budgets must contain positive integers")
    if not random_seed_values or any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64 for value in random_seed_values):
        raise ValueError("random_seeds must contain 64-bit unsigned integers")
    require_int("greedy_seed", greedy_seed)
    if not 0 <= greedy_seed < 1 << 64:
        raise ValueError("greedy_seed must be a 64-bit unsigned integer")
    require_int("backend.ngram_len", backend.ngram_len)
    if backend.ngram_len <= 0:
        raise ValueError("backend.ngram_len must be positive")
    require_sha256("backend.detector_config_hash", backend.detector_config_hash)

    # Generate every matched source before any detector score is requested.
    sources: list[tuple[SynthIDSmokePrompt, GeometryLabel, str]] = []
    for prompt in prompt_values:
        sources.append((prompt, GeometryLabel.CONTROL, backend.generate(prompt.text, prompt.seed, watermarked=False)))
        sources.append((prompt, GeometryLabel.WATERMARKED, backend.generate(prompt.text, prompt.seed, watermarked=True)))

    # Build public-tokenizer geometry and every transform selection before detector scoring.
    prepared: list[_Prepared] = []
    for prompt, label, source_text in sources:
        if not isinstance(source_text, str):
            raise TypeError("backend.generate must return strings")
        source_tokens = tuple(backend.tokenize(source_text))
        if len(source_tokens) < backend.ngram_len:
            raise ValueError("generated source is too short for geometry analysis")
        enumeration = registry.enumerate(source_text)
        coverage = build_public_candidate_coverage(registry, enumeration, backend.tokenize, backend.ngram_len)
        scheduler_input = KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=coverage,
            budget_unit="operation",
            geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        )
        for budget in budget_values:
            prepared.append(
                _prepare(
                    prompt,
                    label,
                    source_text,
                    source_tokens,
                    backend,
                    registry,
                    enumeration,
                    scheduler_input,
                    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
                    budget,
                    greedy_seed,
                )
            )
            for seed in random_seed_values:
                prepared.append(
                    _prepare(
                        prompt,
                        label,
                        source_text,
                        source_tokens,
                        backend,
                        registry,
                        enumeration,
                        scheduler_input,
                        SchedulePolicy.RANDOM_VALID,
                        budget,
                        seed,
                    )
                )

    score_cache: dict[str, float] = {}
    for row in prepared:
        for text in (row.source_text, row.transformed_text):
            if text not in score_cache:
                score_cache[text] = _finite("backend.score", backend.score(text))
    variants = tuple(_variant(row, score_cache[row.source_text], score_cache[row.transformed_text]) for row in prepared)

    groups: dict[tuple[str, int, GeometryLabel, int], list[GeometryVariant]] = {}
    for row in variants:
        groups.setdefault((row.prompt_id, row.generation_seed, row.label, row.budget), []).append(row)
    pairs: list[GeometryPair] = []
    for key in sorted(groups, key=lambda row: (row[0], row[1], row[2].value, row[3])):
        group = groups[key]
        greedy = tuple(row for row in group if row.policy is SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND)
        randoms = tuple(row for row in group if row.policy is SchedulePolicy.RANDOM_VALID)
        if len(greedy) != 1 or len(randoms) != len(random_seed_values):
            raise RuntimeError("incomplete geometry policy group")
        pairs.append(_pair(greedy[0], randoms))
    pair_values = tuple(pairs)

    min_budget = budget_values[0]
    min_greedy = tuple(
        row
        for row in variants
        if row.budget == min_budget and row.policy is SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND
    )
    control_min = tuple(row for row in min_greedy if row.label is GeometryLabel.CONTROL)
    watermark_min = tuple(row for row in min_greedy if row.label is GeometryLabel.WATERMARKED)
    summary = GeometrySummary(
        prompt_count=len(prompt_values),
        source_count=len(sources),
        variant_count=len(variants),
        budgets=budget_values,
        random_seed_count=len(random_seed_values),
        min_budget_control_eligible_rate=sum(row.realized_edit_cost > 0 for row in control_min) / len(control_min),
        min_budget_watermarked_eligible_rate=sum(row.realized_edit_cost > 0 for row in watermark_min) / len(watermark_min),
        matched_pair_count=sum(row.status is GeometryPairStatus.MATCHED for row in pair_values),
        mean_control_disruption_advantage=_mean_pair(pair_values, GeometryLabel.CONTROL, "disruption_advantage"),
        mean_watermarked_disruption_advantage=_mean_pair(pair_values, GeometryLabel.WATERMARKED, "disruption_advantage"),
        mean_control_score_drop_advantage=_mean_pair(pair_values, GeometryLabel.CONTROL, "score_drop_advantage"),
        mean_watermarked_score_drop_advantage=_mean_pair(pair_values, GeometryLabel.WATERMARKED, "score_drop_advantage"),
    )
    payload = {
        "algorithm_version": SYNTHID_GEOMETRY_ALGORITHM_VERSION,
        "selection_access_id": SELECTION_ACCESS_ID,
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "detector_id": backend.detector_id,
        "detector_config_hash": backend.detector_config_hash,
        "transform_ruleset_hash": registry.ruleset_hash,
        "ngram_len": backend.ngram_len,
        "greedy_seed": greedy_seed,
        "random_seeds": random_seed_values,
        "variants": variants,
        "pairs": pair_values,
        "summary": summary,
    }
    return SynthIDGeometryReport(
        SYNTHID_GEOMETRY_ALGORITHM_VERSION,
        SELECTION_ACCESS_ID,
        backend.backend_id,
        backend.backend_version,
        backend.model_id,
        backend.detector_id,
        backend.detector_config_hash,
        registry.ruleset_hash,
        backend.ngram_len,
        greedy_seed,
        random_seed_values,
        variants,
        pair_values,
        summary,
        sha256_json(payload),
    )
