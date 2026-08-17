from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .._validation import require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..transforms import TransformRegistry
from .synthid_eligible_geometry import EligibilityPairStatus
from .synthid_geometry import GeometryLabel
from .synthid_geometry_headroom import HeadroomBudgetStatus
from .synthid_repetition_strata import (
    RepetitionStrataBackend,
    RepetitionStratum,
    run_synthid_repetition_strata,
)
from .synthid_smoke import SynthIDSmokePrompt


SYNTHID_HIGH_REPETITION_PLAN_ALGORITHM_VERSION = "synthid-high-repetition-detector-plan-v1"
SYNTHID_HIGH_REPETITION_DETECTOR_ALGORITHM_VERSION = "synthid-high-repetition-detector-v1"
TARGET_STRATUM = RepetitionStratum.Q4_HIGH
HYPOTHESIS_ID = "q4-public-eligible-score-drop-greater-than-all-v1"
SELECTION_POLICY_ID = "frozen-q4-public-geometry-ab-v1"


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


@runtime_checkable
class HighRepetitionDetectorBackend(RepetitionStrataBackend, Protocol):
    @property
    def detector_id(self) -> str: ...

    @property
    def detector_config_hash(self) -> str: ...

    def score(self, text: str) -> float: ...


@dataclass(frozen=True, slots=True)
class HighRepetitionSource:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    source_record_hash: str
    source_hash: str
    source_text: str
    repeated_fraction: float
    headroom_report_hash: str
    source_plan_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        require_int("generation_seed", self.generation_seed)
        for name in ("source_record_hash", "source_hash", "headroom_report_hash", "source_plan_hash"):
            require_sha256(name, getattr(self, name))
        if self.source_hash != sha256_text(self.source_text):
            raise ValueError("source_hash does not match source_text")
        repeated_fraction = _finite("repeated_fraction", self.repeated_fraction)
        if not 0.0 <= repeated_fraction <= 1.0:
            raise ValueError("repeated_fraction must lie in [0, 1]")
        if self.source_plan_hash != sha256_json(self.payload()):
            raise ValueError("source_plan_hash does not match high-repetition source")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "source_record_hash": self.source_record_hash,
            "source_hash": self.source_hash,
            "source_text": self.source_text,
            "repeated_fraction": self.repeated_fraction,
            "headroom_report_hash": self.headroom_report_hash,
        }


@dataclass(frozen=True, slots=True)
class HighRepetitionPlanPair:
    source_record_hash: str
    budget: int
    headroom_row_hash: str
    all_selected_candidate_ids: tuple[str, ...]
    eligible_selected_candidate_ids: tuple[str, ...]
    all_transformed_text: str
    eligible_transformed_text: str
    pair_plan_hash: str

    def __post_init__(self) -> None:
        require_sha256("source_record_hash", self.source_record_hash)
        require_sha256("headroom_row_hash", self.headroom_row_hash)
        require_sha256("pair_plan_hash", self.pair_plan_hash)
        require_int("budget", self.budget)
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        for name, values in (
            ("all_selected_candidate_ids", self.all_selected_candidate_ids),
            ("eligible_selected_candidate_ids", self.eligible_selected_candidate_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(values) > self.budget or len(set(values)) != len(values):
                raise ValueError(f"{name} violates budget or uniqueness")
            for value in values:
                require_sha256(name, value)
        if self.pair_plan_hash != sha256_json(self.payload()):
            raise ValueError("pair_plan_hash does not match high-repetition plan pair")

    @property
    def same_selection(self) -> bool:
        return self.all_selected_candidate_ids == self.eligible_selected_candidate_ids

    def payload(self) -> dict[str, object]:
        return {
            "source_record_hash": self.source_record_hash,
            "budget": self.budget,
            "headroom_row_hash": self.headroom_row_hash,
            "all_selected_candidate_ids": self.all_selected_candidate_ids,
            "eligible_selected_candidate_ids": self.eligible_selected_candidate_ids,
            "all_transformed_text": self.all_transformed_text,
            "eligible_transformed_text": self.eligible_transformed_text,
        }


@dataclass(frozen=True, slots=True)
class HighRepetitionDetectorPlan:
    algorithm_version: str
    hypothesis_id: str
    selection_policy_id: str
    target_stratum: RepetitionStratum
    detector_scores_used: bool
    selection_feedback_used: bool
    repetition_report_hash: str
    backend_id: str
    backend_version: str
    model_id: str
    ngram_len: int
    eos_token_id: int
    context_history_size: int
    transform_ruleset_hash: str
    budgets: tuple[int, ...]
    schedule_seed: int
    sources: tuple[HighRepetitionSource, ...]
    pairs: tuple[HighRepetitionPlanPair, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_HIGH_REPETITION_PLAN_ALGORITHM_VERSION:
            raise ValueError("unsupported high-repetition plan algorithm version")
        if self.hypothesis_id != HYPOTHESIS_ID or self.selection_policy_id != SELECTION_POLICY_ID:
            raise ValueError("high-repetition plan identity mismatch")
        if self.target_stratum is not TARGET_STRATUM:
            raise ValueError("high-repetition plan must target Q4")
        if self.detector_scores_used is not False or self.selection_feedback_used is not False:
            raise ValueError("plan must be frozen before detector scoring")
        for name in ("repetition_report_hash", "transform_ruleset_hash", "plan_hash"):
            require_sha256(name, getattr(self, name))
        for name in ("ngram_len", "eos_token_id", "context_history_size", "schedule_seed"):
            require_int(name, getattr(self, name))
        if not isinstance(self.sources, tuple) or any(not isinstance(row, HighRepetitionSource) for row in self.sources):
            raise TypeError("sources must contain HighRepetitionSource values")
        if not isinstance(self.pairs, tuple) or any(not isinstance(row, HighRepetitionPlanPair) for row in self.pairs):
            raise TypeError("pairs must contain HighRepetitionPlanPair values")
        source_hashes = {row.source_record_hash for row in self.sources}
        if len(source_hashes) != len(self.sources):
            raise ValueError("high-repetition sources must be unique")
        if any(row.source_record_hash not in source_hashes for row in self.pairs):
            raise ValueError("plan pair references an unknown high-repetition source")
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match high-repetition detector plan")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "hypothesis_id": self.hypothesis_id,
            "selection_policy_id": self.selection_policy_id,
            "target_stratum": self.target_stratum.value,
            "detector_scores_used": self.detector_scores_used,
            "selection_feedback_used": self.selection_feedback_used,
            "repetition_report_hash": self.repetition_report_hash,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "ngram_len": self.ngram_len,
            "eos_token_id": self.eos_token_id,
            "context_history_size": self.context_history_size,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "budgets": self.budgets,
            "schedule_seed": self.schedule_seed,
            "sources": self.sources,
            "pairs": self.pairs,
        }


@dataclass(frozen=True, slots=True)
class HighRepetitionScorePair:
    pair_plan_hash: str
    source_record_hash: str
    label: GeometryLabel
    budget: int
    same_selection: bool
    status: EligibilityPairStatus
    source_score: float
    all_transformed_score: float
    eligible_transformed_score: float
    score_drop_advantage: float | None
    score_pair_hash: str

    def __post_init__(self) -> None:
        require_sha256("pair_plan_hash", self.pair_plan_hash)
        require_sha256("source_record_hash", self.source_record_hash)
        require_sha256("score_pair_hash", self.score_pair_hash)
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if not isinstance(self.status, EligibilityPairStatus):
            raise TypeError("status must be an EligibilityPairStatus")
        require_int("budget", self.budget)
        source = _finite("source_score", self.source_score)
        all_score = _finite("all_transformed_score", self.all_transformed_score)
        eligible_score = _finite("eligible_transformed_score", self.eligible_transformed_score)
        if self.status is EligibilityPairStatus.MATCHED:
            advantage = _finite("score_drop_advantage", self.score_drop_advantage)
            expected = (source - eligible_score) - (source - all_score)
            if not math.isclose(advantage, expected, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("score_drop_advantage does not match score changes")
        elif self.score_drop_advantage is not None:
            raise ValueError("unmatched pairs must withhold score_drop_advantage")
        if self.score_pair_hash != sha256_json(self.payload()):
            raise ValueError("score_pair_hash does not match high-repetition score pair")

    def payload(self) -> dict[str, object]:
        return {
            "pair_plan_hash": self.pair_plan_hash,
            "source_record_hash": self.source_record_hash,
            "label": self.label.value,
            "budget": self.budget,
            "same_selection": self.same_selection,
            "status": self.status.value,
            "source_score": self.source_score,
            "all_transformed_score": self.all_transformed_score,
            "eligible_transformed_score": self.eligible_transformed_score,
            "score_drop_advantage": self.score_drop_advantage,
        }


@dataclass(frozen=True, slots=True)
class HighRepetitionDetectorSummary:
    high_source_count: int
    plan_pair_count: int
    matched_pair_count: int
    differing_selection_pair_count: int
    control_differing_selection_pair_count: int
    watermarked_differing_selection_pair_count: int
    mean_control_score_drop_advantage: float | None
    mean_watermarked_score_drop_advantage: float | None
    mean_control_score_drop_advantage_when_selection_differs: float | None
    mean_watermarked_score_drop_advantage_when_selection_differs: float | None
    watermarked_better_count_when_selection_differs: int
    watermarked_worse_count_when_selection_differs: int
    watermarked_tie_count_when_selection_differs: int


@dataclass(frozen=True, slots=True)
class SynthIDHighRepetitionDetectorReport:
    algorithm_version: str
    hypothesis_id: str
    selection_policy_id: str
    target_stratum: RepetitionStratum
    selection_feedback_used: bool
    plan_hash: str
    detector_id: str
    detector_config_hash: str
    pairs: tuple[HighRepetitionScorePair, ...]
    summary: HighRepetitionDetectorSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_HIGH_REPETITION_DETECTOR_ALGORITHM_VERSION:
            raise ValueError("unsupported high-repetition detector report algorithm version")
        if self.hypothesis_id != HYPOTHESIS_ID or self.selection_policy_id != SELECTION_POLICY_ID:
            raise ValueError("high-repetition detector report identity mismatch")
        if self.target_stratum is not TARGET_STRATUM or self.selection_feedback_used is not False:
            raise ValueError("high-repetition detector report policy mismatch")
        require_sha256("plan_hash", self.plan_hash)
        require_sha256("detector_config_hash", self.detector_config_hash)
        require_sha256("report_hash", self.report_hash)
        if self.summary.plan_pair_count != len(self.pairs):
            raise ValueError("summary plan_pair_count does not match pairs")
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match high-repetition detector report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "hypothesis_id": self.hypothesis_id,
            "selection_policy_id": self.selection_policy_id,
            "target_stratum": self.target_stratum.value,
            "selection_feedback_used": self.selection_feedback_used,
            "plan_hash": self.plan_hash,
            "detector_id": self.detector_id,
            "detector_config_hash": self.detector_config_hash,
            "pairs": self.pairs,
            "summary": self.summary,
        }


def _source(record) -> HighRepetitionSource:
    payload = {
        "prompt_id": record.prompt_id,
        "generation_seed": record.generation_seed,
        "label": record.label.value,
        "source_record_hash": record.record_hash,
        "source_hash": record.source_hash,
        "source_text": record.source_text,
        "repeated_fraction": record.repeated_fraction,
        "headroom_report_hash": record.headroom.report_hash,
    }
    return HighRepetitionSource(
        record.prompt_id,
        record.generation_seed,
        record.label,
        record.record_hash,
        record.source_hash,
        record.source_text,
        record.repeated_fraction,
        record.headroom.report_hash,
        sha256_json(payload),
    )


def _plan_pair(record, budget_row, registry: TransformRegistry, schedule_seed: int) -> HighRepetitionPlanPair:
    enumeration = registry.enumerate(record.source_text)
    if enumeration.enumeration_hash != record.headroom.enumeration_hash:
        raise RuntimeError("reconstructed enumeration does not match frozen headroom report")
    all_ids = budget_row.all_greedy_selected_candidate_ids
    eligible_ids = budget_row.eligible_greedy_selected_candidate_ids
    all_text = registry.apply(enumeration, all_ids, seed=schedule_seed).output_text
    eligible_text = registry.apply(enumeration, eligible_ids, seed=schedule_seed).output_text
    payload = {
        "source_record_hash": record.record_hash,
        "budget": budget_row.budget,
        "headroom_row_hash": budget_row.row_hash,
        "all_selected_candidate_ids": all_ids,
        "eligible_selected_candidate_ids": eligible_ids,
        "all_transformed_text": all_text,
        "eligible_transformed_text": eligible_text,
    }
    return HighRepetitionPlanPair(
        record.record_hash,
        budget_row.budget,
        budget_row.row_hash,
        all_ids,
        eligible_ids,
        all_text,
        eligible_text,
        sha256_json(payload),
    )


def build_high_repetition_detector_plan(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: RepetitionStrataBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    schedule_seed: int = 9800,
    exact_max_candidates: int = 16,
) -> HighRepetitionDetectorPlan:
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    repetition = run_synthid_repetition_strata(
        prompts,
        backend,
        registry,
        budgets=budgets,
        schedule_seed=schedule_seed,
        exact_max_candidates=exact_max_candidates,
    )
    high_records = tuple(row for row in repetition.records if row.stratum is TARGET_STRATUM)
    sources = tuple(_source(row) for row in high_records)
    pairs = []
    for record in high_records:
        for budget_row in record.headroom.budget_rows:
            if budget_row.status is HeadroomBudgetStatus.SCHEDULED:
                pairs.append(_plan_pair(record, budget_row, registry, schedule_seed))
    pair_values = tuple(sorted(pairs, key=lambda row: (row.source_record_hash, row.budget)))
    payload = {
        "algorithm_version": SYNTHID_HIGH_REPETITION_PLAN_ALGORITHM_VERSION,
        "hypothesis_id": HYPOTHESIS_ID,
        "selection_policy_id": SELECTION_POLICY_ID,
        "target_stratum": TARGET_STRATUM.value,
        "detector_scores_used": False,
        "selection_feedback_used": False,
        "repetition_report_hash": repetition.report_hash,
        "backend_id": repetition.backend_id,
        "backend_version": repetition.backend_version,
        "model_id": repetition.model_id,
        "ngram_len": repetition.ngram_len,
        "eos_token_id": repetition.eos_token_id,
        "context_history_size": repetition.context_history_size,
        "transform_ruleset_hash": repetition.transform_ruleset_hash,
        "budgets": repetition.budgets,
        "schedule_seed": repetition.schedule_seed,
        "sources": sources,
        "pairs": pair_values,
    }
    return HighRepetitionDetectorPlan(
        SYNTHID_HIGH_REPETITION_PLAN_ALGORITHM_VERSION,
        HYPOTHESIS_ID,
        SELECTION_POLICY_ID,
        TARGET_STRATUM,
        False,
        False,
        repetition.report_hash,
        repetition.backend_id,
        repetition.backend_version,
        repetition.model_id,
        repetition.ngram_len,
        repetition.eos_token_id,
        repetition.context_history_size,
        repetition.transform_ruleset_hash,
        repetition.budgets,
        repetition.schedule_seed,
        sources,
        pair_values,
        sha256_json(payload),
    )


def _mean(rows: tuple[HighRepetitionScorePair, ...], label: GeometryLabel, differing_only: bool) -> float | None:
    values = tuple(
        float(row.score_drop_advantage)
        for row in rows
        if row.status is EligibilityPairStatus.MATCHED
        and row.label is label
        and (not differing_only or not row.same_selection)
        and row.score_drop_advantage is not None
    )
    return None if not values else statistics.fmean(values)


def score_high_repetition_detector_plan(
    plan: HighRepetitionDetectorPlan,
    backend: HighRepetitionDetectorBackend,
) -> SynthIDHighRepetitionDetectorReport:
    if not isinstance(plan, HighRepetitionDetectorPlan):
        raise TypeError("plan must be a HighRepetitionDetectorPlan")
    if not isinstance(backend, HighRepetitionDetectorBackend):
        raise TypeError("backend must satisfy HighRepetitionDetectorBackend")
    for name in ("backend_id", "backend_version", "model_id", "ngram_len", "eos_token_id", "context_history_size"):
        if getattr(backend, name) != getattr(plan, name):
            raise ValueError(f"scoring backend {name} does not match frozen plan")
    require_sha256("backend.detector_config_hash", backend.detector_config_hash)
    sources = {row.source_record_hash: row for row in plan.sources}
    score_cache: dict[str, float] = {}
    for pair in plan.pairs:
        source = sources[pair.source_record_hash]
        for text in (source.source_text, pair.all_transformed_text, pair.eligible_transformed_text):
            if text not in score_cache:
                score_cache[text] = _finite("backend.score", backend.score(text))
    rows = []
    for pair in plan.pairs:
        source = sources[pair.source_record_hash]
        source_score = score_cache[source.source_text]
        all_score = score_cache[pair.all_transformed_text]
        eligible_score = score_cache[pair.eligible_transformed_text]
        all_cost = len(pair.all_selected_candidate_ids)
        eligible_cost = len(pair.eligible_selected_candidate_ids)
        if all_cost == eligible_cost == 0:
            status = EligibilityPairStatus.INELIGIBLE
            advantage = None
        elif all_cost != eligible_cost:
            status = EligibilityPairStatus.COST_MISMATCH
            advantage = None
        else:
            status = EligibilityPairStatus.MATCHED
            advantage = (source_score - eligible_score) - (source_score - all_score)
        payload = {
            "pair_plan_hash": pair.pair_plan_hash,
            "source_record_hash": pair.source_record_hash,
            "label": source.label.value,
            "budget": pair.budget,
            "same_selection": pair.same_selection,
            "status": status.value,
            "source_score": source_score,
            "all_transformed_score": all_score,
            "eligible_transformed_score": eligible_score,
            "score_drop_advantage": advantage,
        }
        rows.append(
            HighRepetitionScorePair(
                pair.pair_plan_hash,
                pair.source_record_hash,
                source.label,
                pair.budget,
                pair.same_selection,
                status,
                source_score,
                all_score,
                eligible_score,
                advantage,
                sha256_json(payload),
            )
        )
    pair_values = tuple(rows)
    matched = tuple(row for row in pair_values if row.status is EligibilityPairStatus.MATCHED)
    differing = tuple(row for row in matched if not row.same_selection)
    wm_diff = tuple(row for row in differing if row.label is GeometryLabel.WATERMARKED)
    tolerance = 1e-15
    summary = HighRepetitionDetectorSummary(
        len(plan.sources),
        len(plan.pairs),
        len(matched),
        len(differing),
        sum(row.label is GeometryLabel.CONTROL for row in differing),
        sum(row.label is GeometryLabel.WATERMARKED for row in differing),
        _mean(pair_values, GeometryLabel.CONTROL, False),
        _mean(pair_values, GeometryLabel.WATERMARKED, False),
        _mean(pair_values, GeometryLabel.CONTROL, True),
        _mean(pair_values, GeometryLabel.WATERMARKED, True),
        sum(float(row.score_drop_advantage) > tolerance for row in wm_diff),
        sum(float(row.score_drop_advantage) < -tolerance for row in wm_diff),
        sum(abs(float(row.score_drop_advantage)) <= tolerance for row in wm_diff),
    )
    payload = {
        "algorithm_version": SYNTHID_HIGH_REPETITION_DETECTOR_ALGORITHM_VERSION,
        "hypothesis_id": HYPOTHESIS_ID,
        "selection_policy_id": SELECTION_POLICY_ID,
        "target_stratum": TARGET_STRATUM.value,
        "selection_feedback_used": False,
        "plan_hash": plan.plan_hash,
        "detector_id": backend.detector_id,
        "detector_config_hash": backend.detector_config_hash,
        "pairs": pair_values,
        "summary": summary,
    }
    return SynthIDHighRepetitionDetectorReport(
        SYNTHID_HIGH_REPETITION_DETECTOR_ALGORITHM_VERSION,
        HYPOTHESIS_ID,
        SELECTION_POLICY_ID,
        TARGET_STRATUM,
        False,
        plan.plan_hash,
        backend.detector_id,
        backend.detector_config_hash,
        pair_values,
        summary,
        sha256_json(payload),
    )


def run_synthid_high_repetition_detector_pilot(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: HighRepetitionDetectorBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    schedule_seed: int = 9800,
    exact_max_candidates: int = 16,
) -> tuple[HighRepetitionDetectorPlan, SynthIDHighRepetitionDetectorReport]:
    plan = build_high_repetition_detector_plan(
        prompts,
        backend,
        registry,
        budgets=budgets,
        schedule_seed=schedule_seed,
        exact_max_candidates=exact_max_candidates,
    )
    return plan, score_high_repetition_detector_plan(plan, backend)
