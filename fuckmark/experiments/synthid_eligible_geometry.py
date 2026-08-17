from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from .._validation import require_int, require_sha256
from ..alignment import align_tokens
from ..coverage import Interval
from ..hashing import sha256_json
from ..observations import StructuralObservationState, structural_observation_diff
from ..public_eligibility import (
    PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
    PublicEligibilityMask,
    build_huggingface_public_eligibility,
)
from ..transforms import (
    CandidateEnumeration,
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    TransformRegistry,
)
from .synthid_geometry import GeometryLabel, build_public_candidate_coverage
from .synthid_smoke import SynthIDSmokePrompt


SYNTHID_ELIGIBLE_GEOMETRY_ALGORITHM_VERSION = "synthid-open-eligible-geometry-pilot-v1"
ELIGIBLE_SELECTION_ACCESS_ID = "key-blind-public-tokenizer-validity-geometry-v1"


class EligibilityGeometryBasis(str, Enum):
    ALL_OBSERVATIONS = "ALL_OBSERVATIONS"
    PUBLIC_ELIGIBLE = "PUBLIC_ELIGIBLE"


class EligibilityPairStatus(str, Enum):
    MATCHED = "MATCHED"
    INELIGIBLE = "INELIGIBLE"
    COST_MISMATCH = "COST_MISMATCH"


@runtime_checkable
class SynthIDEligibilityGeometryBackend(Protocol):
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

    @property
    def eos_token_id(self) -> int: ...

    @property
    def context_history_size(self) -> int: ...

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str: ...

    def tokenize(self, text: str) -> tuple[int, ...]: ...

    def score(self, text: str) -> float: ...


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


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
            start = value
            end = value + 1
    output.append(Interval(start, end))
    return tuple(output)


def filter_candidate_coverage_by_public_eligibility(
    coverage: Mapping[str, Sequence[Interval]],
    eligibility: PublicEligibilityMask,
) -> dict[str, tuple[Interval, ...]]:
    if not isinstance(coverage, Mapping):
        raise TypeError("coverage must be a mapping")
    if not isinstance(eligibility, PublicEligibilityMask):
        raise TypeError("eligibility must be a PublicEligibilityMask")
    output: dict[str, tuple[Interval, ...]] = {}
    for candidate_id, intervals in coverage.items():
        if not isinstance(candidate_id, str):
            raise TypeError("coverage keys must be candidate ID strings")
        if not isinstance(intervals, Sequence) or isinstance(intervals, (str, bytes, bytearray)):
            raise TypeError("coverage values must be sequences of Interval values")
        indices: list[int] = []
        for interval in intervals:
            if not isinstance(interval, Interval):
                raise TypeError("coverage values must contain Interval values")
            if interval.end_exclusive > eligibility.observation_count:
                raise ValueError("coverage interval exceeds public eligibility geometry")
            indices.extend(
                index
                for index in range(interval.start, interval.end_exclusive)
                if eligibility.valid_mask[index]
            )
        output[candidate_id] = _intervals(indices)
    return output


@dataclass(frozen=True, slots=True)
class EligibilityGeometryVariant:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    basis: EligibilityGeometryBasis
    budget: int
    schedule_seed: int
    source_text: str
    transformed_text: str
    source_token_count: int
    source_observation_count: int
    public_valid_observation_count: int
    public_repeated_observation_count: int
    candidate_count: int
    geometry_positive_candidate_count: int
    predicted_coverage_count: int
    selected_candidate_ids: tuple[str, ...]
    realized_edit_cost: int
    realized_total_disrupted_count: int
    realized_valid_disrupted_count: int
    pristine_score: float
    transformed_score: float
    schedule_result_hash: str
    variant_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if not isinstance(self.basis, EligibilityGeometryBasis):
            raise TypeError("basis must be an EligibilityGeometryBasis")
        for name in (
            "generation_seed",
            "budget",
            "schedule_seed",
            "source_token_count",
            "source_observation_count",
            "public_valid_observation_count",
            "public_repeated_observation_count",
            "candidate_count",
            "geometry_positive_candidate_count",
            "predicted_coverage_count",
            "realized_edit_cost",
            "realized_total_disrupted_count",
            "realized_valid_disrupted_count",
        ):
            require_int(name, getattr(self, name))
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if not 0 <= self.realized_edit_cost <= self.budget:
            raise ValueError("realized edit cost is outside budget")
        if self.realized_edit_cost != len(self.selected_candidate_ids):
            raise ValueError("eligible geometry pilot uses unit operation costs")
        for value in self.selected_candidate_ids:
            require_sha256("selected_candidate_id", value)
        if len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids):
            raise ValueError("selected_candidate_ids must be unique")
        if not 0 <= self.public_valid_observation_count <= self.source_observation_count:
            raise ValueError("public valid observation count is outside source geometry")
        if not 0 <= self.public_repeated_observation_count <= self.source_observation_count:
            raise ValueError("public repeated observation count is outside source geometry")
        if not 0 <= self.realized_valid_disrupted_count <= self.realized_total_disrupted_count:
            raise ValueError("valid disrupted count exceeds total disrupted count")
        if self.realized_total_disrupted_count > self.source_observation_count:
            raise ValueError("total disrupted count exceeds source observations")
        if self.realized_valid_disrupted_count > self.public_valid_observation_count:
            raise ValueError("valid disrupted count exceeds public valid observations")
        if not 0 <= self.geometry_positive_candidate_count <= self.candidate_count:
            raise ValueError("geometry-positive candidate count exceeds candidate count")
        if self.predicted_coverage_count > self.source_observation_count:
            raise ValueError("predicted coverage exceeds source observations")
        if self.basis is EligibilityGeometryBasis.PUBLIC_ELIGIBLE:
            if self.predicted_coverage_count > self.public_valid_observation_count:
                raise ValueError("eligible predicted coverage exceeds public valid observations")
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
            raise ValueError("variant_hash does not match eligible geometry variant")

    @property
    def valid_disruption_per_edit(self) -> float:
        if self.realized_edit_cost == 0:
            return 0.0
        return self.realized_valid_disrupted_count / self.realized_edit_cost

    @property
    def score_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "basis": self.basis.value,
            "budget": self.budget,
            "schedule_seed": self.schedule_seed,
            "source_text": self.source_text,
            "transformed_text": self.transformed_text,
            "source_token_count": self.source_token_count,
            "source_observation_count": self.source_observation_count,
            "public_valid_observation_count": self.public_valid_observation_count,
            "public_repeated_observation_count": self.public_repeated_observation_count,
            "candidate_count": self.candidate_count,
            "geometry_positive_candidate_count": self.geometry_positive_candidate_count,
            "predicted_coverage_count": self.predicted_coverage_count,
            "selected_candidate_ids": self.selected_candidate_ids,
            "realized_edit_cost": self.realized_edit_cost,
            "realized_total_disrupted_count": self.realized_total_disrupted_count,
            "realized_valid_disrupted_count": self.realized_valid_disrupted_count,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "schedule_result_hash": self.schedule_result_hash,
        }


@dataclass(frozen=True, slots=True)
class EligibilityGeometryPair:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    budget: int
    all_variant_hash: str
    eligible_variant_hash: str
    same_selection: bool
    valid_disruption_advantage: float | None
    score_drop_advantage: float | None
    status: EligibilityPairStatus
    pair_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if not isinstance(self.status, EligibilityPairStatus):
            raise TypeError("status must be an EligibilityPairStatus")
        require_int("budget", self.budget)
        require_sha256("all_variant_hash", self.all_variant_hash)
        require_sha256("eligible_variant_hash", self.eligible_variant_hash)
        if not isinstance(self.same_selection, bool):
            raise TypeError("same_selection must be a bool")
        if self.status is EligibilityPairStatus.MATCHED:
            _finite("valid_disruption_advantage", self.valid_disruption_advantage)
            _finite("score_drop_advantage", self.score_drop_advantage)
        elif self.valid_disruption_advantage is not None or self.score_drop_advantage is not None:
            raise ValueError("unmatched eligible geometry pairs must withhold comparison metrics")
        require_sha256("pair_hash", self.pair_hash)
        if self.pair_hash != sha256_json(self.payload()):
            raise ValueError("pair_hash does not match eligible geometry pair")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "budget": self.budget,
            "all_variant_hash": self.all_variant_hash,
            "eligible_variant_hash": self.eligible_variant_hash,
            "same_selection": self.same_selection,
            "valid_disruption_advantage": self.valid_disruption_advantage,
            "score_drop_advantage": self.score_drop_advantage,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class EligibilityGeometrySummary:
    prompt_count: int
    source_count: int
    variant_count: int
    pair_count: int
    matched_pair_count: int
    budgets: tuple[int, ...]
    mean_control_public_valid_fraction: float
    mean_watermarked_public_valid_fraction: float
    matched_same_selection_rate: float | None
    mean_control_valid_disruption_advantage: float | None
    mean_watermarked_valid_disruption_advantage: float | None
    mean_control_score_drop_advantage: float | None
    mean_watermarked_score_drop_advantage: float | None


@dataclass(frozen=True, slots=True)
class SynthIDEligibilityGeometryReport:
    algorithm_version: str
    selection_access_id: str
    public_eligibility_algorithm_version: str
    backend_id: str
    backend_version: str
    model_id: str
    detector_id: str
    detector_config_hash: str
    transform_ruleset_hash: str
    ngram_len: int
    eos_token_id: int
    context_history_size: int
    schedule_seed: int
    variants: tuple[EligibilityGeometryVariant, ...]
    pairs: tuple[EligibilityGeometryPair, ...]
    summary: EligibilityGeometrySummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_ELIGIBLE_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("unsupported eligible geometry algorithm version")
        if self.selection_access_id != ELIGIBLE_SELECTION_ACCESS_ID:
            raise ValueError("unexpected eligible geometry selection access identity")
        if self.public_eligibility_algorithm_version != PUBLIC_ELIGIBILITY_ALGORITHM_VERSION:
            raise ValueError("unexpected public eligibility algorithm version")
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_sha256("transform_ruleset_hash", self.transform_ruleset_hash)
        require_int("ngram_len", self.ngram_len)
        require_int("eos_token_id", self.eos_token_id)
        require_int("context_history_size", self.context_history_size)
        require_int("schedule_seed", self.schedule_seed)
        if self.summary.variant_count != len(self.variants) or self.summary.pair_count != len(self.pairs):
            raise ValueError("eligible geometry summary counts do not match report")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match eligible geometry report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "selection_access_id": self.selection_access_id,
            "public_eligibility_algorithm_version": self.public_eligibility_algorithm_version,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "detector_id": self.detector_id,
            "detector_config_hash": self.detector_config_hash,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "ngram_len": self.ngram_len,
            "eos_token_id": self.eos_token_id,
            "context_history_size": self.context_history_size,
            "schedule_seed": self.schedule_seed,
            "variants": self.variants,
            "pairs": self.pairs,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class _Prepared:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    basis: EligibilityGeometryBasis
    budget: int
    source_text: str
    transformed_text: str
    source_token_count: int
    source_observation_count: int
    public_valid_observation_count: int
    public_repeated_observation_count: int
    candidate_count: int
    geometry_positive_candidate_count: int
    predicted_coverage_count: int
    selected_candidate_ids: tuple[str, ...]
    realized_edit_cost: int
    realized_total_disrupted_count: int
    realized_valid_disrupted_count: int
    schedule_result_hash: str


def _prepare(
    prompt: SynthIDSmokePrompt,
    label: GeometryLabel,
    source_text: str,
    source_tokens: tuple[int, ...],
    eligibility: PublicEligibilityMask,
    backend: SynthIDEligibilityGeometryBackend,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    scheduler_input: KeyBlindScheduleInput,
    basis: EligibilityGeometryBasis,
    budget: int,
    schedule_seed: int,
) -> _Prepared:
    schedule = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        budget,
        schedule_seed,
    )
    transformed = registry.apply(enumeration, schedule.selected_candidate_ids, seed=schedule_seed)
    transformed_tokens = tuple(backend.tokenize(transformed.output_text))
    alignment = align_tokens(source_tokens, transformed_tokens)
    diffs = structural_observation_diff(source_tokens, transformed_tokens, backend.ngram_len, alignment)
    disrupted = tuple(row for row in diffs if row.state is not StructuralObservationState.PRESERVED)
    valid_disrupted = tuple(row for row in disrupted if eligibility.valid_mask[row.original_index])
    return _Prepared(
        prompt.prompt_id,
        prompt.seed,
        label,
        basis,
        budget,
        source_text,
        transformed.output_text,
        len(source_tokens),
        eligibility.observation_count,
        eligibility.valid_count,
        eligibility.repeated_count,
        len(enumeration.candidates),
        sum(bool(candidate.coverage_intervals) for candidate in scheduler_input.candidates),
        schedule.covered_interval_size,
        schedule.selected_candidate_ids,
        schedule.total_cost,
        len(disrupted),
        len(valid_disrupted),
        schedule.result_hash,
    )


def _variant(value: _Prepared, schedule_seed: int, pristine_score: float, transformed_score: float) -> EligibilityGeometryVariant:
    payload = {
        "prompt_id": value.prompt_id,
        "generation_seed": value.generation_seed,
        "label": value.label.value,
        "basis": value.basis.value,
        "budget": value.budget,
        "schedule_seed": schedule_seed,
        "source_text": value.source_text,
        "transformed_text": value.transformed_text,
        "source_token_count": value.source_token_count,
        "source_observation_count": value.source_observation_count,
        "public_valid_observation_count": value.public_valid_observation_count,
        "public_repeated_observation_count": value.public_repeated_observation_count,
        "candidate_count": value.candidate_count,
        "geometry_positive_candidate_count": value.geometry_positive_candidate_count,
        "predicted_coverage_count": value.predicted_coverage_count,
        "selected_candidate_ids": value.selected_candidate_ids,
        "realized_edit_cost": value.realized_edit_cost,
        "realized_total_disrupted_count": value.realized_total_disrupted_count,
        "realized_valid_disrupted_count": value.realized_valid_disrupted_count,
        "pristine_score": pristine_score,
        "transformed_score": transformed_score,
        "schedule_result_hash": value.schedule_result_hash,
    }
    return EligibilityGeometryVariant(
        value.prompt_id,
        value.generation_seed,
        value.label,
        value.basis,
        value.budget,
        schedule_seed,
        value.source_text,
        value.transformed_text,
        value.source_token_count,
        value.source_observation_count,
        value.public_valid_observation_count,
        value.public_repeated_observation_count,
        value.candidate_count,
        value.geometry_positive_candidate_count,
        value.predicted_coverage_count,
        value.selected_candidate_ids,
        value.realized_edit_cost,
        value.realized_total_disrupted_count,
        value.realized_valid_disrupted_count,
        pristine_score,
        transformed_score,
        value.schedule_result_hash,
        sha256_json(payload),
    )


def _pair(all_variant: EligibilityGeometryVariant, eligible_variant: EligibilityGeometryVariant) -> EligibilityGeometryPair:
    same_selection = all_variant.selected_candidate_ids == eligible_variant.selected_candidate_ids
    if all_variant.realized_edit_cost == eligible_variant.realized_edit_cost == 0:
        status = EligibilityPairStatus.INELIGIBLE
        valid_advantage = None
        score_advantage = None
    elif all_variant.realized_edit_cost != eligible_variant.realized_edit_cost:
        status = EligibilityPairStatus.COST_MISMATCH
        valid_advantage = None
        score_advantage = None
    else:
        status = EligibilityPairStatus.MATCHED
        valid_advantage = eligible_variant.valid_disruption_per_edit - all_variant.valid_disruption_per_edit
        score_advantage = eligible_variant.score_drop - all_variant.score_drop
    payload = {
        "prompt_id": all_variant.prompt_id,
        "generation_seed": all_variant.generation_seed,
        "label": all_variant.label.value,
        "budget": all_variant.budget,
        "all_variant_hash": all_variant.variant_hash,
        "eligible_variant_hash": eligible_variant.variant_hash,
        "same_selection": same_selection,
        "valid_disruption_advantage": valid_advantage,
        "score_drop_advantage": score_advantage,
        "status": status.value,
    }
    return EligibilityGeometryPair(
        all_variant.prompt_id,
        all_variant.generation_seed,
        all_variant.label,
        all_variant.budget,
        all_variant.variant_hash,
        eligible_variant.variant_hash,
        same_selection,
        valid_advantage,
        score_advantage,
        status,
        sha256_json(payload),
    )


def _mean_pair(pairs: tuple[EligibilityGeometryPair, ...], label: GeometryLabel, field: str) -> float | None:
    values = tuple(
        float(getattr(pair, field))
        for pair in pairs
        if pair.status is EligibilityPairStatus.MATCHED and pair.label is label
    )
    if not values:
        return None
    return statistics.fmean(values)


def run_synthid_eligible_geometry_pilot(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: SynthIDEligibilityGeometryBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    schedule_seed: int = 0,
) -> SynthIDEligibilityGeometryReport:
    prompt_values = tuple(prompts)
    if not prompt_values or any(not isinstance(prompt, SynthIDSmokePrompt) for prompt in prompt_values):
        raise ValueError("prompts must contain SynthIDSmokePrompt values")
    if len({prompt.prompt_id for prompt in prompt_values}) != len(prompt_values):
        raise ValueError("prompt IDs must be unique")
    if not isinstance(backend, SynthIDEligibilityGeometryBackend):
        raise TypeError("backend must satisfy SynthIDEligibilityGeometryBackend")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    budget_values = tuple(sorted(set(budgets)))
    if not budget_values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in budget_values):
        raise ValueError("budgets must contain positive integers")
    require_int("schedule_seed", schedule_seed)
    if not 0 <= schedule_seed < 1 << 64:
        raise ValueError("schedule_seed must be a 64-bit unsigned integer")
    require_int("backend.ngram_len", backend.ngram_len)
    require_int("backend.eos_token_id", backend.eos_token_id)
    require_int("backend.context_history_size", backend.context_history_size)
    if backend.ngram_len < 2:
        raise ValueError("backend.ngram_len must be at least 2")
    if backend.eos_token_id < 0:
        raise ValueError("backend.eos_token_id must be non-negative")
    if backend.context_history_size <= 0:
        raise ValueError("backend.context_history_size must be positive")
    require_sha256("backend.detector_config_hash", backend.detector_config_hash)

    sources: list[tuple[SynthIDSmokePrompt, GeometryLabel, str]] = []
    for prompt in prompt_values:
        sources.append((prompt, GeometryLabel.CONTROL, backend.generate(prompt.text, prompt.seed, watermarked=False)))
        sources.append((prompt, GeometryLabel.WATERMARKED, backend.generate(prompt.text, prompt.seed, watermarked=True)))

    prepared: list[_Prepared] = []
    source_fractions: dict[tuple[str, GeometryLabel], float] = {}
    for prompt, label, source_text in sources:
        if not isinstance(source_text, str):
            raise TypeError("backend.generate must return strings")
        source_tokens = tuple(backend.tokenize(source_text))
        if len(source_tokens) < backend.ngram_len:
            raise ValueError("generated source is too short for eligible geometry analysis")
        eligibility = build_huggingface_public_eligibility(
            source_tokens,
            backend.eos_token_id,
            backend.ngram_len,
            backend.context_history_size,
        )
        source_fractions[(prompt.prompt_id, label)] = eligibility.valid_count / eligibility.observation_count
        enumeration = registry.enumerate(source_text)
        all_coverage = build_public_candidate_coverage(
            registry,
            enumeration,
            backend.tokenize,
            backend.ngram_len,
        )
        eligible_coverage = filter_candidate_coverage_by_public_eligibility(all_coverage, eligibility)
        scheduler_inputs = {
            EligibilityGeometryBasis.ALL_OBSERVATIONS: KeyBlindScheduleInput.from_enumeration(
                enumeration,
                coverage_intervals=all_coverage,
                budget_unit="operation",
                geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
            ),
            EligibilityGeometryBasis.PUBLIC_ELIGIBLE: KeyBlindScheduleInput.from_enumeration(
                enumeration,
                coverage_intervals=eligible_coverage,
                budget_unit="operation",
                geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
            ),
        }
        for budget in budget_values:
            for basis in (EligibilityGeometryBasis.ALL_OBSERVATIONS, EligibilityGeometryBasis.PUBLIC_ELIGIBLE):
                prepared.append(
                    _prepare(
                        prompt,
                        label,
                        source_text,
                        source_tokens,
                        eligibility,
                        backend,
                        registry,
                        enumeration,
                        scheduler_inputs[basis],
                        basis,
                        budget,
                        schedule_seed,
                    )
                )

    score_cache: dict[str, float] = {}
    for row in prepared:
        for text in (row.source_text, row.transformed_text):
            if text not in score_cache:
                score_cache[text] = _finite("backend.score", backend.score(text))
    variants = tuple(
        _variant(row, schedule_seed, score_cache[row.source_text], score_cache[row.transformed_text])
        for row in prepared
    )

    groups: dict[tuple[str, int, GeometryLabel, int], list[EligibilityGeometryVariant]] = {}
    for variant in variants:
        groups.setdefault(
            (variant.prompt_id, variant.generation_seed, variant.label, variant.budget),
            [],
        ).append(variant)
    pairs: list[EligibilityGeometryPair] = []
    for key in sorted(groups, key=lambda value: (value[0], value[1], value[2].value, value[3])):
        group = groups[key]
        all_rows = tuple(row for row in group if row.basis is EligibilityGeometryBasis.ALL_OBSERVATIONS)
        eligible_rows = tuple(row for row in group if row.basis is EligibilityGeometryBasis.PUBLIC_ELIGIBLE)
        if len(all_rows) != 1 or len(eligible_rows) != 1:
            raise RuntimeError("incomplete eligible geometry basis group")
        pairs.append(_pair(all_rows[0], eligible_rows[0]))
    pair_values = tuple(pairs)
    matched = tuple(pair for pair in pair_values if pair.status is EligibilityPairStatus.MATCHED)
    control_fractions = tuple(
        fraction
        for (prompt_id, label), fraction in source_fractions.items()
        if prompt_id and label is GeometryLabel.CONTROL
    )
    watermarked_fractions = tuple(
        fraction
        for (prompt_id, label), fraction in source_fractions.items()
        if prompt_id and label is GeometryLabel.WATERMARKED
    )
    same_selection_rate = None
    if matched:
        same_selection_rate = sum(pair.same_selection for pair in matched) / len(matched)
    summary = EligibilityGeometrySummary(
        len(prompt_values),
        len(sources),
        len(variants),
        len(pair_values),
        len(matched),
        budget_values,
        statistics.fmean(control_fractions),
        statistics.fmean(watermarked_fractions),
        same_selection_rate,
        _mean_pair(pair_values, GeometryLabel.CONTROL, "valid_disruption_advantage"),
        _mean_pair(pair_values, GeometryLabel.WATERMARKED, "valid_disruption_advantage"),
        _mean_pair(pair_values, GeometryLabel.CONTROL, "score_drop_advantage"),
        _mean_pair(pair_values, GeometryLabel.WATERMARKED, "score_drop_advantage"),
    )
    payload = {
        "algorithm_version": SYNTHID_ELIGIBLE_GEOMETRY_ALGORITHM_VERSION,
        "selection_access_id": ELIGIBLE_SELECTION_ACCESS_ID,
        "public_eligibility_algorithm_version": PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "detector_id": backend.detector_id,
        "detector_config_hash": backend.detector_config_hash,
        "transform_ruleset_hash": registry.ruleset_hash,
        "ngram_len": backend.ngram_len,
        "eos_token_id": backend.eos_token_id,
        "context_history_size": backend.context_history_size,
        "schedule_seed": schedule_seed,
        "variants": variants,
        "pairs": pair_values,
        "summary": summary,
    }
    return SynthIDEligibilityGeometryReport(
        SYNTHID_ELIGIBLE_GEOMETRY_ALGORITHM_VERSION,
        ELIGIBLE_SELECTION_ACCESS_ID,
        PUBLIC_ELIGIBILITY_ALGORITHM_VERSION,
        backend.backend_id,
        backend.backend_version,
        backend.model_id,
        backend.detector_id,
        backend.detector_config_hash,
        registry.ruleset_hash,
        backend.ngram_len,
        backend.eos_token_id,
        backend.context_history_size,
        schedule_seed,
        variants,
        pair_values,
        summary,
        sha256_json(payload),
    )
