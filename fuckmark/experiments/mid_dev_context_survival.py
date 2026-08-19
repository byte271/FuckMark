from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.mid_dev import MidDevAnalysisSplit
from ..corpus.schema import CorpusDomain, WatermarkLabel
from ..hashing import sha256_json, sha256_text
from ..scheduling.beam_v2 import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


MID_DEV_PLAN_ALGORITHM_VERSION = "mid-dev-context-survival-plan-v2"
MID_DEV_SELECTION_CONFIG_VERSION = "mid-dev-selection-config-v1"
MID_DEV_SELECTION_ATTESTATION_VERSION = "mid-dev-selection-attestation-v1"
MID_DEV_QUALITY_VERSION = "mid-dev-quality-sidecar-v1"
MID_DEV_COMPUTE_VERSION = "mid-dev-compute-sidecar-v1"
MID_DEV_SCORED_ROW_VERSION = "mid-dev-scored-row-v2"
MID_DEV_SOURCE_COMPARISON_VERSION = "mid-dev-source-control-adjusted-v1"
MID_DEV_ECS1_PREDICTOR_VERSION = "E-CS1-predictor-comparison-v1"

MID_DEV_BUDGETS = (1, 2, 4, 6)
MID_DEV_BEAM_BUDGETS = (4, 6)
MID_DEV_RANDOM_REPLICATES = 16
MID_DEV_BEAM_WIDTH = 32
MID_DEV_MAX_RISK_TIER = 1
MID_DEV_MINIMUM_SOURCE_GROUPS = 32
MID_DEV_BOOTSTRAP_REPLICATES = 10_000

SUCCESS = "SUCCESS"
NO_CANDIDATES = "NO_CANDIDATES"
INSUFFICIENT_CANDIDATES = "INSUFFICIENT_NONCONFLICTING_CANDIDATES"
VALID_PLAN_STATUSES = frozenset({SUCCESS, NO_CANDIDATES, INSUFFICIENT_CANDIDATES})


class MidDevCondition(str, Enum):
    CURRENT_STRONGEST_BASELINE = "current-strongest-key-blind-baseline"
    CONTEXT_SURVIVAL_GREEDY = "context-survival-greedy"
    CONTEXT_SURVIVAL_BEAM = "context-survival-beam-v2"
    EVEN_SPACING = "even-spacing"
    RANDOM_SAFE = "budget-matched-random-safe"
    NO_OP = "no-op-control"


DETERMINISTIC_BUDGET_CONDITIONS = (
    MidDevCondition.CURRENT_STRONGEST_BASELINE,
    MidDevCondition.CONTEXT_SURVIVAL_GREEDY,
    MidDevCondition.EVEN_SPACING,
)


@dataclass(frozen=True, slots=True)
class MidDevSelectionConfig:
    algorithm_version: str
    budgets: tuple[int, ...]
    beam_budgets: tuple[int, ...]
    random_replicates: int
    beam_width: int
    max_risk_tier: int
    beam_algorithm_version: str
    config_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_SELECTION_CONFIG_VERSION:
            raise ValueError("unsupported MidDev selection config version")
        if self.budgets != MID_DEV_BUDGETS:
            raise ValueError("MidDev budgets must match the frozen development profile")
        if self.beam_budgets != MID_DEV_BEAM_BUDGETS:
            raise ValueError("MidDev beam budgets must match the frozen development profile")
        require_int("random_replicates", self.random_replicates)
        if self.random_replicates != MID_DEV_RANDOM_REPLICATES:
            raise ValueError("frozen MidDev requires exactly sixteen random replicates per source/budget")
        require_int("beam_width", self.beam_width)
        require_int("max_risk_tier", self.max_risk_tier)
        if self.beam_width != MID_DEV_BEAM_WIDTH:
            raise ValueError("MidDev beam width must match the frozen development profile")
        if self.max_risk_tier != MID_DEV_MAX_RISK_TIER:
            raise ValueError("MidDev risk tier must match the frozen development profile")
        if self.beam_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
            raise ValueError("MidDev must use the corrected context-survival beam v2")
        require_sha256("config_hash", self.config_hash)
        if self.config_hash != sha256_json(self.payload()):
            raise ValueError("config_hash does not match MidDev selection config")

    @classmethod
    def frozen(cls) -> "MidDevSelectionConfig":
        payload = {
            "algorithm_version": MID_DEV_SELECTION_CONFIG_VERSION,
            "budgets": MID_DEV_BUDGETS,
            "beam_budgets": MID_DEV_BEAM_BUDGETS,
            "random_replicates": MID_DEV_RANDOM_REPLICATES,
            "beam_width": MID_DEV_BEAM_WIDTH,
            "max_risk_tier": MID_DEV_MAX_RISK_TIER,
            "beam_algorithm_version": CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        }
        return cls(
            MID_DEV_SELECTION_CONFIG_VERSION,
            MID_DEV_BUDGETS,
            MID_DEV_BEAM_BUDGETS,
            MID_DEV_RANDOM_REPLICATES,
            MID_DEV_BEAM_WIDTH,
            MID_DEV_MAX_RISK_TIER,
            CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "budgets": self.budgets,
            "beam_budgets": self.beam_budgets,
            "random_replicates": self.random_replicates,
            "beam_width": self.beam_width,
            "max_risk_tier": self.max_risk_tier,
            "beam_algorithm_version": self.beam_algorithm_version,
        }


@dataclass(frozen=True, slots=True)
class MidDevSelectionAttestation:
    algorithm_version: str
    attested_expander_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    detector_query_count: int
    secret_query_count: int
    attestation_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_SELECTION_ATTESTATION_VERSION:
            raise ValueError("unsupported MidDev selection attestation version")
        require_int("attested_expander_count", self.attested_expander_count)
        if self.attested_expander_count <= 0:
            raise ValueError("MidDev selection must attest at least one real expander")
        if not isinstance(self.detector_access_observed, bool):
            raise TypeError("detector_access_observed must be a boolean")
        if not isinstance(self.secret_access_observed, bool):
            raise TypeError("secret_access_observed must be a boolean")
        for name in ("detector_query_count", "secret_query_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.detector_access_observed
            or self.secret_access_observed
            or self.detector_query_count
            or self.secret_query_count
        ):
            raise ValueError("MidDev selection attestation is contaminated")
        require_sha256("attestation_hash", self.attestation_hash)
        if self.attestation_hash != sha256_json(self.payload()):
            raise ValueError("attestation_hash does not match MidDev selection attestation")

    @classmethod
    def from_observed(
        cls,
        *,
        attested_expander_count: int,
        detector_access_observed: bool,
        secret_access_observed: bool,
        detector_query_count: int,
        secret_query_count: int,
    ) -> "MidDevSelectionAttestation":
        payload = {
            "algorithm_version": MID_DEV_SELECTION_ATTESTATION_VERSION,
            "attested_expander_count": attested_expander_count,
            "detector_access_observed": detector_access_observed,
            "secret_access_observed": secret_access_observed,
            "detector_query_count": detector_query_count,
            "secret_query_count": secret_query_count,
        }
        return cls(
            MID_DEV_SELECTION_ATTESTATION_VERSION,
            attested_expander_count,
            detector_access_observed,
            secret_access_observed,
            detector_query_count,
            secret_query_count,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "attested_expander_count": self.attested_expander_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
            "detector_query_count": self.detector_query_count,
            "secret_query_count": self.secret_query_count,
        }


@dataclass(frozen=True, slots=True)
class MidDevPlanRow:
    source_group_id: str
    prompt_id: str
    sample_id: str
    source_label: WatermarkLabel
    prompt_family_id: str
    domain: CorpusDomain
    target_length: int
    source_text_hash: str
    condition: MidDevCondition
    budget: int
    replicate: int
    transformed_text: str
    transformed_text_hash: str
    operation_count: int
    status: str
    selection_trace_hash: str
    plan_row_hash: str

    def __post_init__(self) -> None:
        for name in ("source_group_id", "prompt_id", "sample_id", "prompt_family_id", "status"):
            require_clean_string(name, getattr(self, name))
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be a WatermarkLabel")
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_int("target_length", self.target_length)
        if self.target_length not in (128, 256):
            raise ValueError("MidDev target_length must be 128 or 256")
        require_sha256("source_text_hash", self.source_text_hash)
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be a MidDevCondition")
        require_int("budget", self.budget)
        require_int("replicate", self.replicate)
        require_int("operation_count", self.operation_count)
        if self.condition is MidDevCondition.NO_OP:
            if self.budget != 0 or self.replicate != 0 or self.operation_count != 0:
                raise ValueError("MidDev no-op rows must use budget=replicate=operation_count=0")
        else:
            if self.budget not in MID_DEV_BUDGETS:
                raise ValueError("MidDev planned budget is not frozen")
            if self.operation_count < 0 or self.operation_count > self.budget:
                raise ValueError("operation_count must be between zero and requested budget")
            if self.condition is MidDevCondition.RANDOM_SAFE:
                if not 0 <= self.replicate < MID_DEV_RANDOM_REPLICATES:
                    raise ValueError("random-safe replicate is outside the frozen range")
            elif self.replicate != 0:
                raise ValueError("deterministic MidDev conditions must use replicate zero")
            if self.condition is MidDevCondition.CONTEXT_SURVIVAL_BEAM and self.budget not in MID_DEV_BEAM_BUDGETS:
                raise ValueError("MidDev beam rows are only defined for B4/B6")
        if self.status not in VALID_PLAN_STATUSES:
            raise ValueError("unsupported MidDev plan status")
        if self.condition is MidDevCondition.NO_OP and self.status != SUCCESS:
            raise ValueError("no-op row must be successful")
        if self.status == SUCCESS and self.condition is not MidDevCondition.NO_OP:
            if self.operation_count != self.budget:
                raise ValueError("successful MidDev edit row must realize its requested budget")
        if self.status == NO_CANDIDATES and self.operation_count != 0:
            raise ValueError("NO_CANDIDATES row must realize zero operations")
        if not isinstance(self.transformed_text, str) or not self.transformed_text:
            raise ValueError("transformed_text must be a non-empty string")
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        require_sha256("selection_trace_hash", self.selection_trace_hash)
        require_sha256("plan_row_hash", self.plan_row_hash)
        if self.plan_row_hash != sha256_json(self.payload()):
            raise ValueError("plan_row_hash does not match MidDevPlanRow payload")

    @classmethod
    def create(
        cls,
        *,
        source_group_id: str,
        prompt_id: str,
        sample_id: str,
        source_label: WatermarkLabel,
        prompt_family_id: str,
        domain: CorpusDomain,
        target_length: int,
        source_text_hash: str,
        condition: MidDevCondition,
        budget: int,
        replicate: int,
        transformed_text: str,
        operation_count: int,
        status: str,
        selection_trace_hash: str,
    ) -> "MidDevPlanRow":
        transformed_text_hash = sha256_text(transformed_text)
        payload = {
            "source_group_id": source_group_id,
            "prompt_id": prompt_id,
            "sample_id": sample_id,
            "source_label": source_label.value,
            "prompt_family_id": prompt_family_id,
            "domain": domain.value,
            "target_length": target_length,
            "source_text_hash": source_text_hash,
            "condition": condition.value,
            "budget": budget,
            "replicate": replicate,
            "transformed_text_hash": transformed_text_hash,
            "operation_count": operation_count,
            "status": status,
            "selection_trace_hash": selection_trace_hash,
        }
        return cls(
            source_group_id,
            prompt_id,
            sample_id,
            source_label,
            prompt_family_id,
            domain,
            target_length,
            source_text_hash,
            condition,
            budget,
            replicate,
            transformed_text,
            transformed_text_hash,
            operation_count,
            status,
            selection_trace_hash,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "source_group_id": self.source_group_id,
            "prompt_id": self.prompt_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain.value,
            "target_length": self.target_length,
            "source_text_hash": self.source_text_hash,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "transformed_text_hash": self.transformed_text_hash,
            "operation_count": self.operation_count,
            "status": self.status,
            "selection_trace_hash": self.selection_trace_hash,
        }


@dataclass(frozen=True, slots=True)
class MidDevQualityRow:
    plan_row_hash: str
    word_edit_rate: float
    old_observation_replacement_ratio: float
    exact_destruction_ratio: float
    exact_survival_ratio: float
    token_edit_distance: int
    length_ratio: float
    numbers_preserved_fraction: float
    urls_preserved_fraction: float
    protected_span_violation_count: int
    hard_invariant_status: str
    quality_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_row_hash", self.plan_row_hash)
        for name in (
            "word_edit_rate",
            "old_observation_replacement_ratio",
            "exact_destruction_ratio",
            "exact_survival_ratio",
            "numbers_preserved_fraction",
            "urls_preserved_fraction",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if not math.isclose(
            self.exact_destruction_ratio + self.exact_survival_ratio,
            1.0,
            abs_tol=1e-12,
        ):
            raise ValueError("exact destruction and survival ratios must sum to one")
        if isinstance(self.length_ratio, bool) or not isinstance(self.length_ratio, (int, float)):
            raise ValueError("length_ratio must be numeric")
        if not math.isfinite(float(self.length_ratio)) or self.length_ratio <= 0:
            raise ValueError("length_ratio must be finite and positive")
        require_int("token_edit_distance", self.token_edit_distance)
        require_int("protected_span_violation_count", self.protected_span_violation_count)
        if self.token_edit_distance < 0:
            raise ValueError("token_edit_distance must be non-negative")
        if self.protected_span_violation_count != 0:
            raise ValueError("MidDev plan cannot contain protected-span fidelity violations")
        if self.hard_invariant_status != "pass":
            raise ValueError("MidDev plan requires passing hard invariants")
        require_sha256("quality_hash", self.quality_hash)
        if self.quality_hash != sha256_json(self.payload()):
            raise ValueError("quality_hash does not match MidDevQualityRow payload")

    @classmethod
    def create(
        cls,
        *,
        plan_row_hash: str,
        word_edit_rate: float,
        old_observation_replacement_ratio: float,
        exact_destruction_ratio: float,
        exact_survival_ratio: float,
        token_edit_distance: int,
        length_ratio: float,
        numbers_preserved_fraction: float,
        urls_preserved_fraction: float,
        protected_span_violation_count: int,
        hard_invariant_status: str,
    ) -> "MidDevQualityRow":
        payload = {
            "algorithm_version": MID_DEV_QUALITY_VERSION,
            "plan_row_hash": plan_row_hash,
            "word_edit_rate": float(word_edit_rate),
            "old_observation_replacement_ratio": float(old_observation_replacement_ratio),
            "exact_destruction_ratio": float(exact_destruction_ratio),
            "exact_survival_ratio": float(exact_survival_ratio),
            "token_edit_distance": token_edit_distance,
            "length_ratio": float(length_ratio),
            "numbers_preserved_fraction": float(numbers_preserved_fraction),
            "urls_preserved_fraction": float(urls_preserved_fraction),
            "protected_span_violation_count": protected_span_violation_count,
            "hard_invariant_status": hard_invariant_status,
        }
        return cls(
            plan_row_hash,
            float(word_edit_rate),
            float(old_observation_replacement_ratio),
            float(exact_destruction_ratio),
            float(exact_survival_ratio),
            token_edit_distance,
            float(length_ratio),
            float(numbers_preserved_fraction),
            float(urls_preserved_fraction),
            protected_span_violation_count,
            hard_invariant_status,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_QUALITY_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "word_edit_rate": self.word_edit_rate,
            "old_observation_replacement_ratio": self.old_observation_replacement_ratio,
            "exact_destruction_ratio": self.exact_destruction_ratio,
            "exact_survival_ratio": self.exact_survival_ratio,
            "token_edit_distance": self.token_edit_distance,
            "length_ratio": self.length_ratio,
            "numbers_preserved_fraction": self.numbers_preserved_fraction,
            "urls_preserved_fraction": self.urls_preserved_fraction,
            "protected_span_violation_count": self.protected_span_violation_count,
            "hard_invariant_status": self.hard_invariant_status,
        }


@dataclass(frozen=True, slots=True)
class MidDevComputeRow:
    plan_row_hash: str
    expanded_state_count: int
    pruned_state_count: int
    candidate_evaluation_count: int
    expansion_cache_hit_count: int
    expansion_cache_miss_count: int
    geometry_cache_hit_count: int
    planning_wall_time_ms: float
    selection_detector_query_count: int
    selection_secret_query_count: int
    compute_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_row_hash", self.plan_row_hash)
        for name in (
            "expanded_state_count",
            "pruned_state_count",
            "candidate_evaluation_count",
            "expansion_cache_hit_count",
            "expansion_cache_miss_count",
            "geometry_cache_hit_count",
            "selection_detector_query_count",
            "selection_secret_query_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.selection_detector_query_count or self.selection_secret_query_count:
            raise ValueError("MidDev selection sidecar recorded forbidden detector/secret queries")
        if isinstance(self.planning_wall_time_ms, bool) or not isinstance(
            self.planning_wall_time_ms, (int, float)
        ):
            raise ValueError("planning_wall_time_ms must be numeric")
        if not math.isfinite(float(self.planning_wall_time_ms)) or self.planning_wall_time_ms < 0:
            raise ValueError("planning_wall_time_ms must be finite and non-negative")
        require_sha256("compute_hash", self.compute_hash)
        if self.compute_hash != sha256_json(self.payload()):
            raise ValueError("compute_hash does not match MidDevComputeRow payload")

    @classmethod
    def create(cls, **kwargs) -> "MidDevComputeRow":
        payload = {"algorithm_version": MID_DEV_COMPUTE_VERSION, **kwargs}
        return cls(
            kwargs["plan_row_hash"],
            kwargs["expanded_state_count"],
            kwargs["pruned_state_count"],
            kwargs["candidate_evaluation_count"],
            kwargs["expansion_cache_hit_count"],
            kwargs["expansion_cache_miss_count"],
            kwargs["geometry_cache_hit_count"],
            float(kwargs["planning_wall_time_ms"]),
            kwargs["selection_detector_query_count"],
            kwargs["selection_secret_query_count"],
            sha256_json(
                {
                    **payload,
                    "planning_wall_time_ms": float(kwargs["planning_wall_time_ms"]),
                }
            ),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_COMPUTE_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "candidate_evaluation_count": self.candidate_evaluation_count,
            "expansion_cache_hit_count": self.expansion_cache_hit_count,
            "expansion_cache_miss_count": self.expansion_cache_miss_count,
            "geometry_cache_hit_count": self.geometry_cache_hit_count,
            "planning_wall_time_ms": self.planning_wall_time_ms,
            "selection_detector_query_count": self.selection_detector_query_count,
            "selection_secret_query_count": self.selection_secret_query_count,
        }


def _expected_keys_for_sample() -> set[tuple[MidDevCondition, int, int]]:
    expected: set[tuple[MidDevCondition, int, int]] = {(MidDevCondition.NO_OP, 0, 0)}
    for budget in MID_DEV_BUDGETS:
        for condition in DETERMINISTIC_BUDGET_CONDITIONS:
            expected.add((condition, budget, 0))
        for replicate in range(MID_DEV_RANDOM_REPLICATES):
            expected.add((MidDevCondition.RANDOM_SAFE, budget, replicate))
    for budget in MID_DEV_BEAM_BUDGETS:
        expected.add((MidDevCondition.CONTEXT_SURVIVAL_BEAM, budget, 0))
    return expected


def _validate_plan_matrix(rows: Sequence[MidDevPlanRow]) -> None:
    source_groups = sorted({value.source_group_id for value in rows})
    if len(source_groups) < MID_DEV_MINIMUM_SOURCE_GROUPS:
        raise ValueError("MidDev frozen plan must contain at least 32 independent source groups")
    by_sample: dict[tuple[str, str], list[MidDevPlanRow]] = {}
    group_labels: dict[str, set[WatermarkLabel]] = {}
    group_metadata: dict[str, set[tuple[str, str, CorpusDomain, int]]] = {}
    for row in rows:
        by_sample.setdefault((row.source_group_id, row.sample_id), []).append(row)
        group_labels.setdefault(row.source_group_id, set()).add(row.source_label)
        group_metadata.setdefault(row.source_group_id, set()).add(
            (row.prompt_id, row.prompt_family_id, row.domain, row.target_length)
        )
    for group_id in source_groups:
        if group_labels[group_id] != {
            WatermarkLabel.WATERMARKED,
            WatermarkLabel.UNWATERMARKED,
        }:
            raise ValueError("each MidDev source group must contain watermarked and control plans")
        if len(group_metadata[group_id]) != 1:
            raise ValueError("matched MidDev source labels must share prompt metadata")
    expected = _expected_keys_for_sample()
    for values in by_sample.values():
        keys = {(value.condition, value.budget, value.replicate) for value in values}
        if keys != expected or len(values) != len(expected):
            raise ValueError(
                "each MidDev sample must contain the complete frozen condition/budget/replicate matrix"
            )


@dataclass(frozen=True, slots=True)
class MidDevFrozenPlan:
    algorithm_version: str
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    selection_config: MidDevSelectionConfig
    selection_attestation: MidDevSelectionAttestation
    rows: tuple[MidDevPlanRow, ...]
    quality_rows: tuple[MidDevQualityRow, ...]
    compute_rows: tuple[MidDevComputeRow, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_PLAN_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev plan algorithm version")
        for name in ("corpus_artifact_hash", "source_profile_hash", "analysis_split_hash", "plan_hash"):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.selection_config, MidDevSelectionConfig):
            raise TypeError("selection_config must be a MidDevSelectionConfig")
        if not isinstance(self.selection_attestation, MidDevSelectionAttestation):
            raise TypeError("selection_attestation must be a MidDevSelectionAttestation")
        if not isinstance(self.rows, tuple) or any(not isinstance(value, MidDevPlanRow) for value in self.rows):
            raise TypeError("rows must be a tuple of MidDevPlanRow values")
        if not self.rows:
            raise ValueError("MidDev plan must contain rows")
        if len({value.plan_row_hash for value in self.rows}) != len(self.rows):
            raise ValueError("MidDev plan rows must be unique")
        _validate_plan_matrix(self.rows)
        row_hashes = {value.plan_row_hash for value in self.rows}
        quality_hashes = {value.plan_row_hash for value in self.quality_rows}
        compute_hashes = {value.plan_row_hash for value in self.compute_rows}
        if len(self.quality_rows) != len(self.rows) or quality_hashes != row_hashes:
            raise ValueError("MidDev quality sidecar must bind every plan row exactly once")
        if len(self.compute_rows) != len(self.rows) or compute_hashes != row_hashes:
            raise ValueError("MidDev compute sidecar must bind every plan row exactly once")
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match MidDevFrozenPlan payload")

    @classmethod
    def create(
        cls,
        *,
        corpus_artifact_hash: str,
        source_profile_hash: str,
        analysis_split_hash: str,
        selection_config: MidDevSelectionConfig,
        selection_attestation: MidDevSelectionAttestation,
        rows: Sequence[MidDevPlanRow],
        quality_rows: Sequence[MidDevQualityRow],
        compute_rows: Sequence[MidDevComputeRow],
    ) -> "MidDevFrozenPlan":
        materialized = tuple(
            sorted(
                rows,
                key=lambda value: (
                    value.source_group_id,
                    value.sample_id,
                    value.condition.value,
                    value.budget,
                    value.replicate,
                ),
            )
        )
        quality = tuple(sorted(quality_rows, key=lambda value: value.plan_row_hash))
        compute = tuple(sorted(compute_rows, key=lambda value: value.plan_row_hash))
        payload = {
            "algorithm_version": MID_DEV_PLAN_ALGORITHM_VERSION,
            "corpus_artifact_hash": corpus_artifact_hash,
            "source_profile_hash": source_profile_hash,
            "analysis_split_hash": analysis_split_hash,
            "selection_config_hash": selection_config.config_hash,
            "selection_attestation_hash": selection_attestation.attestation_hash,
            "row_hashes": tuple(value.plan_row_hash for value in materialized),
            "quality_hashes": tuple(value.quality_hash for value in quality),
            "compute_hashes": tuple(value.compute_hash for value in compute),
        }
        return cls(
            MID_DEV_PLAN_ALGORITHM_VERSION,
            corpus_artifact_hash,
            source_profile_hash,
            analysis_split_hash,
            selection_config,
            selection_attestation,
            materialized,
            quality,
            compute,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "selection_config_hash": self.selection_config.config_hash,
            "selection_attestation_hash": self.selection_attestation.attestation_hash,
            "row_hashes": tuple(value.plan_row_hash for value in self.rows),
            "quality_hashes": tuple(value.quality_hash for value in self.quality_rows),
            "compute_hashes": tuple(value.compute_hash for value in self.compute_rows),
        }


@dataclass(frozen=True, slots=True)
class MidDevScoredRow:
    plan_row_hash: str
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    condition: MidDevCondition
    budget: int
    replicate: int
    detector_identity_hash: str
    threshold_hash: str
    threshold_value: float
    pristine_score: float
    transformed_score: float
    pristine_detected: bool
    transformed_detected: bool
    scored_row_hash: str

    def __post_init__(self) -> None:
        for name in ("plan_row_hash", "detector_identity_hash", "threshold_hash", "scored_row_hash"):
            require_sha256(name, getattr(self, name))
        require_clean_string("source_group_id", self.source_group_id)
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be a WatermarkLabel")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be a MidDevCondition")
        require_int("budget", self.budget)
        require_int("replicate", self.replicate)
        for name in ("threshold_value", "pristine_score", "transformed_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not isinstance(self.pristine_detected, bool) or not isinstance(self.transformed_detected, bool):
            raise TypeError("detected fields must be booleans")
        if self.scored_row_hash != sha256_json(self.payload()):
            raise ValueError("scored_row_hash does not match MidDevScoredRow payload")

    @classmethod
    def create(
        cls,
        *,
        plan_row: MidDevPlanRow,
        detector_identity_hash: str,
        threshold_hash: str,
        threshold_value: float,
        pristine_score: float,
        transformed_score: float,
    ) -> "MidDevScoredRow":
        pristine_detected = pristine_score >= threshold_value
        transformed_detected = transformed_score >= threshold_value
        payload = {
            "algorithm_version": MID_DEV_SCORED_ROW_VERSION,
            "plan_row_hash": plan_row.plan_row_hash,
            "source_group_id": plan_row.source_group_id,
            "sample_id": plan_row.sample_id,
            "source_label": plan_row.source_label.value,
            "condition": plan_row.condition.value,
            "budget": plan_row.budget,
            "replicate": plan_row.replicate,
            "detector_identity_hash": detector_identity_hash,
            "threshold_hash": threshold_hash,
            "threshold_value": float(threshold_value),
            "pristine_score": float(pristine_score),
            "transformed_score": float(transformed_score),
            "pristine_detected": pristine_detected,
            "transformed_detected": transformed_detected,
        }
        return cls(
            plan_row.plan_row_hash,
            plan_row.source_group_id,
            plan_row.sample_id,
            plan_row.source_label,
            plan_row.condition,
            plan_row.budget,
            plan_row.replicate,
            detector_identity_hash,
            threshold_hash,
            float(threshold_value),
            float(pristine_score),
            float(transformed_score),
            pristine_detected,
            transformed_detected,
            sha256_json(payload),
        )

    @property
    def score_drop(self) -> float:
        return self.pristine_score - self.transformed_score

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SCORED_ROW_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "detector_identity_hash": self.detector_identity_hash,
            "threshold_hash": self.threshold_hash,
            "threshold_value": self.threshold_value,
            "pristine_score": self.pristine_score,
            "transformed_score": self.transformed_score,
            "pristine_detected": self.pristine_detected,
            "transformed_detected": self.transformed_detected,
        }


@dataclass(frozen=True, slots=True)
class MidDevECS1PredictorRow:
    source_group_id: str
    sample_id: str
    source_label: WatermarkLabel
    condition: MidDevCondition
    budget: int
    replicate: int
    analysis_split: MidDevAnalysisSplit
    word_edit_rate: float
    old_observation_replacement_ratio: float
    exact_destruction_ratio: float
    exact_survival_ratio: float
    detector_margin_drop: float
    predictor_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_group_id", self.source_group_id)
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.source_label, WatermarkLabel):
            raise TypeError("source_label must be WatermarkLabel")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        if not isinstance(self.analysis_split, MidDevAnalysisSplit):
            raise TypeError("analysis_split must be MidDevAnalysisSplit")
        for name in (
            "word_edit_rate",
            "old_observation_replacement_ratio",
            "exact_destruction_ratio",
            "exact_survival_ratio",
            "detector_margin_drop",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        require_sha256("predictor_hash", self.predictor_hash)
        if self.predictor_hash != sha256_json(self.payload()):
            raise ValueError("predictor_hash does not match E-CS1 predictor row")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_ECS1_PREDICTOR_VERSION,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "source_label": self.source_label.value,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "analysis_split": self.analysis_split.value,
            "word_edit_rate": self.word_edit_rate,
            "old_observation_replacement_ratio": self.old_observation_replacement_ratio,
            "exact_destruction_ratio": self.exact_destruction_ratio,
            "exact_survival_ratio": self.exact_survival_ratio,
            "detector_margin_drop": self.detector_margin_drop,
        }


def build_ecs1_predictor_rows(
    plan: MidDevFrozenPlan,
    scored_rows: Sequence[MidDevScoredRow],
    analysis_split_by_prompt: dict[str, MidDevAnalysisSplit],
) -> tuple[MidDevECS1PredictorRow, ...]:
    plan_by_hash = {value.plan_row_hash: value for value in plan.rows}
    quality_by_hash = {value.plan_row_hash: value for value in plan.quality_rows}
    output: list[MidDevECS1PredictorRow] = []
    for scored in scored_rows:
        plan_row = plan_by_hash.get(scored.plan_row_hash)
        quality = quality_by_hash.get(scored.plan_row_hash)
        if plan_row is None or quality is None:
            raise ValueError("E-CS1 scored row is not bound to the frozen plan and quality sidecar")
        split = analysis_split_by_prompt.get(plan_row.prompt_id)
        if split is None:
            raise ValueError("E-CS1 source has no frozen grouped-holdout assignment")
        payload = {
            "algorithm_version": MID_DEV_ECS1_PREDICTOR_VERSION,
            "source_group_id": scored.source_group_id,
            "sample_id": scored.sample_id,
            "source_label": scored.source_label.value,
            "condition": scored.condition.value,
            "budget": scored.budget,
            "replicate": scored.replicate,
            "analysis_split": split.value,
            "word_edit_rate": quality.word_edit_rate,
            "old_observation_replacement_ratio": quality.old_observation_replacement_ratio,
            "exact_destruction_ratio": quality.exact_destruction_ratio,
            "exact_survival_ratio": quality.exact_survival_ratio,
            "detector_margin_drop": scored.score_drop,
        }
        output.append(
            MidDevECS1PredictorRow(
                scored.source_group_id,
                scored.sample_id,
                scored.source_label,
                scored.condition,
                scored.budget,
                scored.replicate,
                split,
                quality.word_edit_rate,
                quality.old_observation_replacement_ratio,
                quality.exact_destruction_ratio,
                quality.exact_survival_ratio,
                scored.score_drop,
                sha256_json(payload),
            )
        )
    return tuple(
        sorted(
            output,
            key=lambda value: (
                value.source_group_id,
                value.sample_id,
                value.condition.value,
                value.budget,
                value.replicate,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class SourceGroupedControlAdjustedComparison:
    baseline_condition: MidDevCondition
    comparison_condition: MidDevCondition
    budget: int
    source_group_count: int
    mean_watermarked_difference: float
    mean_control_difference: float
    mean_control_adjusted_difference: float
    bootstrap_lower: float
    bootstrap_upper: float
    positive_adjusted_count: int
    negative_adjusted_count: int
    zero_adjusted_count: int
    two_sided_sign_p_value: float
    comparison_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.baseline_condition, MidDevCondition):
            raise TypeError("baseline_condition must be a MidDevCondition")
        if not isinstance(self.comparison_condition, MidDevCondition):
            raise TypeError("comparison_condition must be a MidDevCondition")
        require_int("budget", self.budget)
        require_int("source_group_count", self.source_group_count)
        if self.source_group_count < MID_DEV_MINIMUM_SOURCE_GROUPS:
            raise ValueError("source-group comparison requires at least 32 sources")
        for name in (
            "mean_watermarked_difference",
            "mean_control_difference",
            "mean_control_adjusted_difference",
            "bootstrap_lower",
            "bootstrap_upper",
            "two_sided_sign_p_value",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.bootstrap_lower > self.bootstrap_upper:
            raise ValueError("bootstrap interval is reversed")
        for name in ("positive_adjusted_count", "negative_adjusted_count", "zero_adjusted_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.positive_adjusted_count
            + self.negative_adjusted_count
            + self.zero_adjusted_count
            != self.source_group_count
        ):
            raise ValueError("sign counts must partition source groups")
        if not 0.0 <= self.two_sided_sign_p_value <= 1.0:
            raise ValueError("sign p-value must be between zero and one")
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self.payload()):
            raise ValueError("comparison_hash does not match source-group comparison")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SOURCE_COMPARISON_VERSION,
            "baseline_condition": self.baseline_condition.value,
            "comparison_condition": self.comparison_condition.value,
            "budget": self.budget,
            "source_group_count": self.source_group_count,
            "mean_watermarked_difference": self.mean_watermarked_difference,
            "mean_control_difference": self.mean_control_difference,
            "mean_control_adjusted_difference": self.mean_control_adjusted_difference,
            "bootstrap_lower": self.bootstrap_lower,
            "bootstrap_upper": self.bootstrap_upper,
            "positive_adjusted_count": self.positive_adjusted_count,
            "negative_adjusted_count": self.negative_adjusted_count,
            "zero_adjusted_count": self.zero_adjusted_count,
            "two_sided_sign_p_value": self.two_sided_sign_p_value,
        }


def _mean_score_drop(
    values: Sequence[MidDevScoredRow],
    *,
    label: WatermarkLabel,
    condition: MidDevCondition,
    budget: int,
) -> float:
    selected = tuple(
        value.score_drop
        for value in values
        if value.source_label is label
        and value.condition is condition
        and value.budget == budget
    )
    if not selected:
        raise ValueError("source group is missing a required scored condition")
    return sum(selected) / len(selected)


def source_grouped_control_adjusted_comparison(
    rows: Sequence[MidDevScoredRow],
    *,
    comparison_condition: MidDevCondition,
    budget: int,
    baseline_condition: MidDevCondition = MidDevCondition.CURRENT_STRONGEST_BASELINE,
    bootstrap_replicates: int = MID_DEV_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = 0x4D4944444556,
) -> SourceGroupedControlAdjustedComparison:
    require_int("budget", budget)
    require_int("bootstrap_replicates", bootstrap_replicates)
    require_int("bootstrap_seed", bootstrap_seed)
    if budget not in MID_DEV_BUDGETS:
        raise ValueError("comparison budget is not part of the frozen MidDev profile")
    if comparison_condition is MidDevCondition.NO_OP:
        raise ValueError("no-op is not a budget-matched primary comparison condition")
    if comparison_condition is MidDevCondition.CONTEXT_SURVIVAL_BEAM and budget not in MID_DEV_BEAM_BUDGETS:
        raise ValueError("beam comparison is only defined for B4/B6")
    if bootstrap_replicates <= 0 or bootstrap_seed < 0:
        raise ValueError("invalid bootstrap configuration")

    grouped: dict[str, list[MidDevScoredRow]] = {}
    for row in rows:
        if row.budget == budget:
            grouped.setdefault(row.source_group_id, []).append(row)
    watermarked_differences: list[float] = []
    control_differences: list[float] = []
    adjusted: list[float] = []
    for group_id in sorted(grouped):
        values = grouped[group_id]
        wm_base = _mean_score_drop(
            values,
            label=WatermarkLabel.WATERMARKED,
            condition=baseline_condition,
            budget=budget,
        )
        wm_comp = _mean_score_drop(
            values,
            label=WatermarkLabel.WATERMARKED,
            condition=comparison_condition,
            budget=budget,
        )
        ctrl_base = _mean_score_drop(
            values,
            label=WatermarkLabel.UNWATERMARKED,
            condition=baseline_condition,
            budget=budget,
        )
        ctrl_comp = _mean_score_drop(
            values,
            label=WatermarkLabel.UNWATERMARKED,
            condition=comparison_condition,
            budget=budget,
        )
        wm_delta = wm_comp - wm_base
        ctrl_delta = ctrl_comp - ctrl_base
        watermarked_differences.append(wm_delta)
        control_differences.append(ctrl_delta)
        adjusted.append(wm_delta - ctrl_delta)
    if len(adjusted) < MID_DEV_MINIMUM_SOURCE_GROUPS:
        raise ValueError("source-group comparison requires at least 32 independent sources")

    rng = random.Random(bootstrap_seed)
    count = len(adjusted)
    bootstrap_means = sorted(
        sum(adjusted[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(bootstrap_replicates)
    )
    lower_index = max(0, math.floor(0.025 * (bootstrap_replicates - 1)))
    upper_index = min(bootstrap_replicates - 1, math.ceil(0.975 * (bootstrap_replicates - 1)))
    positive = sum(value > 0 for value in adjusted)
    negative = sum(value < 0 for value in adjusted)
    zero = count - positive - negative
    nonzero = positive + negative
    if nonzero == 0:
        sign_p = 1.0
    else:
        tail = min(positive, negative)
        cumulative = sum(math.comb(nonzero, value) for value in range(tail + 1)) / (2**nonzero)
        sign_p = min(1.0, 2.0 * cumulative)
    payload = {
        "algorithm_version": MID_DEV_SOURCE_COMPARISON_VERSION,
        "baseline_condition": baseline_condition.value,
        "comparison_condition": comparison_condition.value,
        "budget": budget,
        "source_group_count": count,
        "mean_watermarked_difference": sum(watermarked_differences) / count,
        "mean_control_difference": sum(control_differences) / count,
        "mean_control_adjusted_difference": sum(adjusted) / count,
        "bootstrap_lower": bootstrap_means[lower_index],
        "bootstrap_upper": bootstrap_means[upper_index],
        "positive_adjusted_count": positive,
        "negative_adjusted_count": negative,
        "zero_adjusted_count": zero,
        "two_sided_sign_p_value": sign_p,
    }
    return SourceGroupedControlAdjustedComparison(
        baseline_condition,
        comparison_condition,
        budget,
        count,
        payload["mean_watermarked_difference"],
        payload["mean_control_difference"],
        payload["mean_control_adjusted_difference"],
        payload["bootstrap_lower"],
        payload["bootstrap_upper"],
        positive,
        negative,
        zero,
        sign_p,
        sha256_json(payload),
    )
