from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from .._validation import require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from ..public_eligibility import build_huggingface_public_eligibility
from ..transforms import TransformRegistry
from .synthid_geometry import GeometryLabel
from .synthid_geometry_headroom import (
    SynthIDGeometryHeadroomReport,
    build_public_eligibility_geometry_headroom,
)
from .synthid_smoke import SynthIDSmokePrompt


SYNTHID_REPETITION_STRATA_ALGORITHM_VERSION = "synthid-repetition-strata-v1"
STRATIFICATION_POLICY_ID = "within-label-public-repetition-rank-quartiles-v1"


class RepetitionStratum(str, Enum):
    Q1_LOW = "Q1_LOW"
    Q2_MID_LOW = "Q2_MID_LOW"
    Q3_MID_HIGH = "Q3_MID_HIGH"
    Q4_HIGH = "Q4_HIGH"


_STRATA = (
    RepetitionStratum.Q1_LOW,
    RepetitionStratum.Q2_MID_LOW,
    RepetitionStratum.Q3_MID_HIGH,
    RepetitionStratum.Q4_HIGH,
)


@runtime_checkable
class RepetitionStrataBackend(Protocol):
    @property
    def backend_id(self) -> str: ...

    @property
    def backend_version(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    @property
    def ngram_len(self) -> int: ...

    @property
    def eos_token_id(self) -> int: ...

    @property
    def context_history_size(self) -> int: ...

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str: ...

    def tokenize(self, text: str) -> tuple[int, ...]: ...


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


@dataclass(frozen=True, slots=True)
class _UnstratifiedSource:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    source_text: str
    source_hash: str
    token_hash: str
    token_count: int
    observation_count: int
    valid_count: int
    repeated_count: int
    repeated_fraction: float
    valid_fraction: float
    headroom: SynthIDGeometryHeadroomReport


@dataclass(frozen=True, slots=True)
class RepetitionSourceRecord:
    prompt_id: str
    generation_seed: int
    label: GeometryLabel
    stratum: RepetitionStratum
    rank_within_label: int
    label_source_count: int
    source_text: str
    source_hash: str
    token_hash: str
    token_count: int
    observation_count: int
    valid_count: int
    repeated_count: int
    repeated_fraction: float
    valid_fraction: float
    headroom: SynthIDGeometryHeadroomReport
    record_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel):
            raise TypeError("label must be a GeometryLabel")
        if not isinstance(self.stratum, RepetitionStratum):
            raise TypeError("stratum must be a RepetitionStratum")
        for name in (
            "generation_seed",
            "rank_within_label",
            "label_source_count",
            "token_count",
            "observation_count",
            "valid_count",
            "repeated_count",
        ):
            require_int(name, getattr(self, name))
        if self.rank_within_label <= 0 or self.rank_within_label > self.label_source_count:
            raise ValueError("rank_within_label is outside label source count")
        if self.token_count < 0 or self.observation_count <= 0:
            raise ValueError("source token and observation counts are invalid")
        if not 0 <= self.valid_count <= self.observation_count:
            raise ValueError("valid_count is outside observation geometry")
        if not 0 <= self.repeated_count <= self.observation_count:
            raise ValueError("repeated_count is outside observation geometry")
        repeated_fraction = _finite("repeated_fraction", self.repeated_fraction)
        valid_fraction = _finite("valid_fraction", self.valid_fraction)
        if not 0.0 <= repeated_fraction <= 1.0 or not 0.0 <= valid_fraction <= 1.0:
            raise ValueError("source fractions must lie in [0, 1]")
        if not math.isclose(repeated_fraction, self.repeated_count / self.observation_count, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("repeated_fraction does not match counts")
        if not math.isclose(valid_fraction, self.valid_count / self.observation_count, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("valid_fraction does not match counts")
        require_sha256("source_hash", self.source_hash)
        require_sha256("token_hash", self.token_hash)
        if self.source_hash != sha256_text(self.source_text):
            raise ValueError("source_hash does not match source_text")
        if not isinstance(self.headroom, SynthIDGeometryHeadroomReport):
            raise TypeError("headroom must be a SynthIDGeometryHeadroomReport")
        require_sha256("record_hash", self.record_hash)
        if self.record_hash != sha256_json(self.payload()):
            raise ValueError("record_hash does not match repetition source record")

    def payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "generation_seed": self.generation_seed,
            "label": self.label.value,
            "stratum": self.stratum.value,
            "rank_within_label": self.rank_within_label,
            "label_source_count": self.label_source_count,
            "source_text": self.source_text,
            "source_hash": self.source_hash,
            "token_hash": self.token_hash,
            "token_count": self.token_count,
            "observation_count": self.observation_count,
            "valid_count": self.valid_count,
            "repeated_count": self.repeated_count,
            "repeated_fraction": self.repeated_fraction,
            "valid_fraction": self.valid_fraction,
            "headroom": self.headroom,
        }


@dataclass(frozen=True, slots=True)
class RepetitionStratumSummary:
    label: GeometryLabel
    stratum: RepetitionStratum
    source_count: int
    mean_repeated_fraction: float | None
    min_repeated_fraction: float | None
    max_repeated_fraction: float | None
    mean_valid_fraction: float | None
    mean_candidate_count: float | None
    mean_rank_correlation: float | None
    disagreement_source_count: int
    scheduled_budget_count: int
    greedy_selection_disagreement_count: int
    exact_budget_count: int
    exact_selection_disagreement_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.label, GeometryLabel) or not isinstance(self.stratum, RepetitionStratum):
            raise TypeError("stratum summary enums are invalid")
        for name in (
            "source_count",
            "disagreement_source_count",
            "scheduled_budget_count",
            "greedy_selection_disagreement_count",
            "exact_budget_count",
            "exact_selection_disagreement_count",
        ):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.disagreement_source_count > self.source_count:
            raise ValueError("disagreement source count exceeds source count")
        if self.greedy_selection_disagreement_count > self.scheduled_budget_count:
            raise ValueError("greedy disagreement count exceeds scheduled budgets")
        if self.exact_selection_disagreement_count > self.exact_budget_count:
            raise ValueError("exact disagreement count exceeds exact budgets")
        optional = (
            "mean_repeated_fraction",
            "min_repeated_fraction",
            "max_repeated_fraction",
            "mean_valid_fraction",
            "mean_candidate_count",
            "mean_rank_correlation",
        )
        if self.source_count == 0:
            if any(getattr(self, name) is not None for name in optional):
                raise ValueError("empty strata must withhold mean and range metrics")
        else:
            if any(getattr(self, name) is None for name in optional[:-1]):
                raise ValueError("non-empty strata require source metrics")
            for name in optional:
                value = getattr(self, name)
                if value is not None:
                    _finite(name, value)


@dataclass(frozen=True, slots=True)
class RepetitionStrataSummary:
    prompt_count: int
    source_count: int
    control_source_count: int
    watermarked_source_count: int
    total_candidate_count: int
    disagreement_source_count: int
    high_stratum_disagreement_source_count: int
    highest_repetition_record_hash: str

    def __post_init__(self) -> None:
        for name in (
            "prompt_count",
            "source_count",
            "control_source_count",
            "watermarked_source_count",
            "total_candidate_count",
            "disagreement_source_count",
            "high_stratum_disagreement_source_count",
        ):
            require_int(name, getattr(self, name))
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.control_source_count + self.watermarked_source_count != self.source_count:
            raise ValueError("label source counts do not sum to source_count")
        if self.disagreement_source_count > self.source_count:
            raise ValueError("disagreement source count exceeds source_count")
        if self.high_stratum_disagreement_source_count > self.disagreement_source_count:
            raise ValueError("high-stratum disagreement count exceeds all disagreement sources")
        require_sha256("highest_repetition_record_hash", self.highest_repetition_record_hash)


@dataclass(frozen=True, slots=True)
class SynthIDRepetitionStrataReport:
    algorithm_version: str
    stratification_policy_id: str
    detector_scores_used: bool
    backend_id: str
    backend_version: str
    model_id: str
    transform_ruleset_hash: str
    ngram_len: int
    eos_token_id: int
    context_history_size: int
    budgets: tuple[int, ...]
    schedule_seed: int
    records: tuple[RepetitionSourceRecord, ...]
    strata: tuple[RepetitionStratumSummary, ...]
    summary: RepetitionStrataSummary
    report_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != SYNTHID_REPETITION_STRATA_ALGORITHM_VERSION:
            raise ValueError("unsupported repetition strata algorithm version")
        if self.stratification_policy_id != STRATIFICATION_POLICY_ID:
            raise ValueError("unexpected repetition stratification policy")
        if self.detector_scores_used is not False:
            raise ValueError("repetition strata analysis must not use detector scores")
        require_sha256("transform_ruleset_hash", self.transform_ruleset_hash)
        require_int("ngram_len", self.ngram_len)
        require_int("eos_token_id", self.eos_token_id)
        require_int("context_history_size", self.context_history_size)
        require_int("schedule_seed", self.schedule_seed)
        if not isinstance(self.records, tuple) or any(not isinstance(row, RepetitionSourceRecord) for row in self.records):
            raise TypeError("records must contain RepetitionSourceRecord values")
        if len({row.record_hash for row in self.records}) != len(self.records):
            raise ValueError("repetition source records must be unique")
        expected_strata = tuple((label, stratum) for label in (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED) for stratum in _STRATA)
        if tuple((row.label, row.stratum) for row in self.strata) != expected_strata:
            raise ValueError("strata summaries must use canonical label and quartile order")
        if self.summary.source_count != len(self.records):
            raise ValueError("summary source_count does not match records")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match repetition strata report")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "stratification_policy_id": self.stratification_policy_id,
            "detector_scores_used": self.detector_scores_used,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "model_id": self.model_id,
            "transform_ruleset_hash": self.transform_ruleset_hash,
            "ngram_len": self.ngram_len,
            "eos_token_id": self.eos_token_id,
            "context_history_size": self.context_history_size,
            "budgets": self.budgets,
            "schedule_seed": self.schedule_seed,
            "records": self.records,
            "strata": self.strata,
            "summary": self.summary,
        }


def _assign_strata(rows: tuple[_UnstratifiedSource, ...]) -> tuple[RepetitionSourceRecord, ...]:
    output = []
    for label in (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED):
        label_rows = tuple(
            sorted(
                (row for row in rows if row.label is label),
                key=lambda row: (row.repeated_fraction, row.prompt_id, row.generation_seed, row.source_hash),
            )
        )
        count = len(label_rows)
        if count == 0:
            raise ValueError("each repetition label must contain at least one source")
        for index, row in enumerate(label_rows):
            stratum = _STRATA[min(3, index * 4 // count)]
            payload = {
                "prompt_id": row.prompt_id,
                "generation_seed": row.generation_seed,
                "label": row.label.value,
                "stratum": stratum.value,
                "rank_within_label": index + 1,
                "label_source_count": count,
                "source_text": row.source_text,
                "source_hash": row.source_hash,
                "token_hash": row.token_hash,
                "token_count": row.token_count,
                "observation_count": row.observation_count,
                "valid_count": row.valid_count,
                "repeated_count": row.repeated_count,
                "repeated_fraction": row.repeated_fraction,
                "valid_fraction": row.valid_fraction,
                "headroom": row.headroom,
            }
            output.append(
                RepetitionSourceRecord(
                    row.prompt_id,
                    row.generation_seed,
                    row.label,
                    stratum,
                    index + 1,
                    count,
                    row.source_text,
                    row.source_hash,
                    row.token_hash,
                    row.token_count,
                    row.observation_count,
                    row.valid_count,
                    row.repeated_count,
                    row.repeated_fraction,
                    row.valid_fraction,
                    row.headroom,
                    sha256_json(payload),
                )
            )
    return tuple(sorted(output, key=lambda row: (row.prompt_id, row.generation_seed, row.label.value)))


def _stratum_summary(
    records: tuple[RepetitionSourceRecord, ...],
    label: GeometryLabel,
    stratum: RepetitionStratum,
) -> RepetitionStratumSummary:
    rows = tuple(row for row in records if row.label is label and row.stratum is stratum)
    if not rows:
        return RepetitionStratumSummary(label, stratum, 0, None, None, None, None, None, None, 0, 0, 0, 0, 0)
    repeated = tuple(row.repeated_fraction for row in rows)
    rank_correlations = tuple(
        row.headroom.summary.spearman_rank_correlation
        for row in rows
        if row.headroom.summary.spearman_rank_correlation is not None
    )
    disagreement_sources = sum(
        row.headroom.summary.greedy_selection_disagreement_count > 0
        or row.headroom.summary.exact_selection_disagreement_count > 0
        for row in rows
    )
    return RepetitionStratumSummary(
        label,
        stratum,
        len(rows),
        statistics.fmean(repeated),
        min(repeated),
        max(repeated),
        statistics.fmean(row.valid_fraction for row in rows),
        statistics.fmean(row.headroom.summary.candidate_count for row in rows),
        None if not rank_correlations else statistics.fmean(rank_correlations),
        disagreement_sources,
        sum(row.headroom.summary.scheduled_budget_count for row in rows),
        sum(row.headroom.summary.greedy_selection_disagreement_count for row in rows),
        sum(row.headroom.summary.exact_budget_count for row in rows),
        sum(row.headroom.summary.exact_selection_disagreement_count for row in rows),
    )


def run_synthid_repetition_strata(
    prompts: Sequence[SynthIDSmokePrompt],
    backend: RepetitionStrataBackend,
    registry: TransformRegistry,
    *,
    budgets: Sequence[int] = (1, 2, 4),
    schedule_seed: int = 9700,
    exact_max_candidates: int = 16,
) -> SynthIDRepetitionStrataReport:
    prompt_values = tuple(prompts)
    if not prompt_values or any(not isinstance(row, SynthIDSmokePrompt) for row in prompt_values):
        raise ValueError("prompts must contain SynthIDSmokePrompt values")
    if len({row.prompt_id for row in prompt_values}) != len(prompt_values):
        raise ValueError("prompt IDs must be unique")
    if not isinstance(backend, RepetitionStrataBackend):
        raise TypeError("backend must satisfy RepetitionStrataBackend")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    budget_values = tuple(sorted(set(budgets)))
    if not budget_values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in budget_values):
        raise ValueError("budgets must contain positive integers")
    require_int("schedule_seed", schedule_seed)
    require_int("exact_max_candidates", exact_max_candidates)
    if not 0 <= schedule_seed < 1 << 64:
        raise ValueError("schedule_seed must fit in 64 bits")
    if not 1 <= exact_max_candidates <= 16:
        raise ValueError("exact_max_candidates must lie in [1, 16]")
    sources = []
    for prompt in prompt_values:
        sources.append((prompt, GeometryLabel.CONTROL, backend.generate(prompt.text, prompt.seed, watermarked=False)))
        sources.append((prompt, GeometryLabel.WATERMARKED, backend.generate(prompt.text, prompt.seed, watermarked=True)))
    unstratified = []
    for prompt, label, source_text in sources:
        if not isinstance(source_text, str):
            raise TypeError("backend.generate must return strings")
        tokens = tuple(backend.tokenize(source_text))
        eligibility = build_huggingface_public_eligibility(
            tokens,
            backend.eos_token_id,
            backend.ngram_len,
            backend.context_history_size,
        )
        if eligibility.observation_count <= 0:
            raise ValueError("generated source is too short for repetition stratification")
        headroom = build_public_eligibility_geometry_headroom(
            source_text,
            backend.tokenize,
            backend.eos_token_id,
            backend.ngram_len,
            backend.context_history_size,
            registry,
            budgets=budget_values,
            seed=schedule_seed,
            exact_max_candidates=exact_max_candidates,
        )
        unstratified.append(
            _UnstratifiedSource(
                prompt.prompt_id,
                prompt.seed,
                label,
                source_text,
                sha256_text(source_text),
                sha256_json(tokens),
                len(tokens),
                eligibility.observation_count,
                eligibility.valid_count,
                eligibility.repeated_count,
                eligibility.repeated_count / eligibility.observation_count,
                eligibility.valid_count / eligibility.observation_count,
                headroom,
            )
        )
    records = _assign_strata(tuple(unstratified))
    strata = tuple(
        _stratum_summary(records, label, stratum)
        for label in (GeometryLabel.CONTROL, GeometryLabel.WATERMARKED)
        for stratum in _STRATA
    )
    disagreement_records = tuple(
        row
        for row in records
        if row.headroom.summary.greedy_selection_disagreement_count > 0
        or row.headroom.summary.exact_selection_disagreement_count > 0
    )
    highest = max(records, key=lambda row: (row.repeated_fraction, row.label.value, row.prompt_id, row.record_hash))
    summary = RepetitionStrataSummary(
        len(prompt_values),
        len(records),
        sum(row.label is GeometryLabel.CONTROL for row in records),
        sum(row.label is GeometryLabel.WATERMARKED for row in records),
        sum(row.headroom.summary.candidate_count for row in records),
        len(disagreement_records),
        sum(row.stratum is RepetitionStratum.Q4_HIGH for row in disagreement_records),
        highest.record_hash,
    )
    payload = {
        "algorithm_version": SYNTHID_REPETITION_STRATA_ALGORITHM_VERSION,
        "stratification_policy_id": STRATIFICATION_POLICY_ID,
        "detector_scores_used": False,
        "backend_id": backend.backend_id,
        "backend_version": backend.backend_version,
        "model_id": backend.model_id,
        "transform_ruleset_hash": registry.ruleset_hash,
        "ngram_len": backend.ngram_len,
        "eos_token_id": backend.eos_token_id,
        "context_history_size": backend.context_history_size,
        "budgets": budget_values,
        "schedule_seed": schedule_seed,
        "records": records,
        "strata": strata,
        "summary": summary,
    }
    return SynthIDRepetitionStrataReport(
        SYNTHID_REPETITION_STRATA_ALGORITHM_VERSION,
        STRATIFICATION_POLICY_ID,
        False,
        backend.backend_id,
        backend.backend_version,
        backend.model_id,
        registry.ruleset_hash,
        backend.ngram_len,
        backend.eos_token_id,
        backend.context_history_size,
        budget_values,
        schedule_seed,
        records,
        strata,
        summary,
        sha256_json(payload),
    )
