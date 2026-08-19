from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..corpus.schema import CorpusDomain, WatermarkLabel
from ..hashing import sha256_json, sha256_text
from ..scheduling.algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION


MID_DEV_LEGACY_PLAN_VERSION = "mid-dev-context-survival-plan-v2"
MID_DEV_DETERMINISTIC_PLAN_VERSION = "mid-dev-context-survival-plan-v4"
MID_DEV_SELECTION_CONFIG_VERSION = "mid-dev-selection-config-v1"
MID_DEV_SELECTION_ATTESTATION_VERSION = "mid-dev-selection-attestation-v1"
MID_DEV_QUALITY_VERSION = "mid-dev-quality-sidecar-v1"
MID_DEV_DETERMINISTIC_COMPUTE_VERSION = "mid-dev-deterministic-compute-v1"
MID_DEV_BUDGETS = (1, 2, 4, 6)
MID_DEV_BEAM_BUDGETS = (4, 6)
MID_DEV_RANDOM_REPLICATES = 16
MID_DEV_BEAM_WIDTH = 32
MID_DEV_MAX_RISK_TIER = 1
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
class MidDevSelectionConfigView:
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
        if self.budgets != MID_DEV_BUDGETS or self.beam_budgets != MID_DEV_BEAM_BUDGETS:
            raise ValueError("MidDev selection budgets do not match the frozen profile")
        require_int("random_replicates", self.random_replicates)
        require_int("beam_width", self.beam_width)
        require_int("max_risk_tier", self.max_risk_tier)
        if self.random_replicates != MID_DEV_RANDOM_REPLICATES:
            raise ValueError("MidDev selection requires sixteen random replicates")
        if self.beam_width != MID_DEV_BEAM_WIDTH or self.max_risk_tier != MID_DEV_MAX_RISK_TIER:
            raise ValueError("MidDev selection search profile drifted")
        if self.beam_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
            raise ValueError("MidDev selection must bind beam v2")
        require_sha256("config_hash", self.config_hash)
        if self.config_hash != sha256_json(self.payload()):
            raise ValueError("config_hash does not match MidDev selection config")

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
class MidDevSelectionAttestationView:
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
        require_int("detector_query_count", self.detector_query_count)
        require_int("secret_query_count", self.secret_query_count)
        if self.attested_expander_count <= 0:
            raise ValueError("MidDev selection must attest real expanders")
        if not isinstance(self.detector_access_observed, bool) or not isinstance(self.secret_access_observed, bool):
            raise TypeError("selection access observations must be boolean")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("MidDev selection attestation is contaminated")
        if self.detector_query_count or self.secret_query_count:
            raise ValueError("MidDev selection attestation recorded forbidden queries")
        require_sha256("attestation_hash", self.attestation_hash)
        if self.attestation_hash != sha256_json(self.payload()):
            raise ValueError("attestation_hash does not match MidDev selection attestation")

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
class MidDevPlanRowView:
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
            raise TypeError("source_label must be WatermarkLabel")
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be CorpusDomain")
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        require_int("target_length", self.target_length)
        require_int("budget", self.budget)
        require_int("replicate", self.replicate)
        require_int("operation_count", self.operation_count)
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        require_sha256("selection_trace_hash", self.selection_trace_hash)
        require_sha256("plan_row_hash", self.plan_row_hash)
        if self.target_length not in (128, 256):
            raise ValueError("MidDev target length must be 128 or 256")
        if not isinstance(self.transformed_text, str) or not self.transformed_text:
            raise ValueError("transformed_text must be non-empty")
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed text")
        if self.status not in VALID_PLAN_STATUSES:
            raise ValueError("unsupported MidDev plan status")
        if self.condition is MidDevCondition.NO_OP:
            if self.budget != 0 or self.replicate != 0 or self.operation_count != 0 or self.status != SUCCESS:
                raise ValueError("MidDev no-op row is malformed")
        else:
            if self.budget not in MID_DEV_BUDGETS:
                raise ValueError("MidDev budget is not frozen")
            if self.operation_count < 0 or self.operation_count > self.budget:
                raise ValueError("MidDev realized edit cost is outside the requested budget")
            if self.condition is MidDevCondition.RANDOM_SAFE:
                if not 0 <= self.replicate < MID_DEV_RANDOM_REPLICATES:
                    raise ValueError("MidDev random replicate is outside the frozen range")
            elif self.replicate != 0:
                raise ValueError("MidDev deterministic row must use replicate zero")
            if self.condition is MidDevCondition.CONTEXT_SURVIVAL_BEAM and self.budget not in MID_DEV_BEAM_BUDGETS:
                raise ValueError("MidDev beam row is only defined at B4/B6")
            if self.status == SUCCESS and self.operation_count != self.budget:
                raise ValueError("successful MidDev row must realize its requested budget")
            if self.status == NO_CANDIDATES and self.operation_count != 0:
                raise ValueError("NO_CANDIDATES must realize zero operations")
        if self.plan_row_hash != sha256_json(self.payload()):
            raise ValueError("plan_row_hash does not match MidDev plan row")

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
class MidDevQualityRowView:
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
        require_sha256("quality_hash", self.quality_hash)
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
        if not math.isclose(self.exact_destruction_ratio + self.exact_survival_ratio, 1.0, abs_tol=1e-12):
            raise ValueError("exact destruction and survival must sum to one")
        require_int("token_edit_distance", self.token_edit_distance)
        require_int("protected_span_violation_count", self.protected_span_violation_count)
        if self.token_edit_distance < 0 or self.protected_span_violation_count != 0:
            raise ValueError("MidDev fidelity invariants failed")
        if isinstance(self.length_ratio, bool) or not isinstance(self.length_ratio, (int, float)):
            raise ValueError("length_ratio must be numeric")
        if not math.isfinite(float(self.length_ratio)) or self.length_ratio <= 0:
            raise ValueError("length_ratio must be finite and positive")
        if self.hard_invariant_status != "pass":
            raise ValueError("MidDev hard invariant status must pass")
        if self.quality_hash != sha256_json(self.payload()):
            raise ValueError("quality_hash does not match MidDev quality row")

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
class MidDevDeterministicComputeRowView:
    plan_row_hash: str
    expanded_state_count: int
    pruned_state_count: int
    candidate_evaluation_count: int
    expansion_cache_hit_count: int
    expansion_cache_miss_count: int
    geometry_cache_hit_count: int
    selection_detector_query_count: int
    selection_secret_query_count: int
    compute_hash: str

    def __post_init__(self) -> None:
        require_sha256("plan_row_hash", self.plan_row_hash)
        require_sha256("compute_hash", self.compute_hash)
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
            raise ValueError("MidDev compute row recorded forbidden selection queries")
        if self.compute_hash != sha256_json(self.payload()):
            raise ValueError("compute_hash does not match MidDev compute row")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_DETERMINISTIC_COMPUTE_VERSION,
            "plan_row_hash": self.plan_row_hash,
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "candidate_evaluation_count": self.candidate_evaluation_count,
            "expansion_cache_hit_count": self.expansion_cache_hit_count,
            "expansion_cache_miss_count": self.expansion_cache_miss_count,
            "geometry_cache_hit_count": self.geometry_cache_hit_count,
            "selection_detector_query_count": self.selection_detector_query_count,
            "selection_secret_query_count": self.selection_secret_query_count,
        }


@dataclass(frozen=True, slots=True)
class MidDevFrozenPlanView:
    algorithm_version: str
    corpus_artifact_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    source_code_commit: str
    ngram_len: int
    context_history_size: int
    selection_config: MidDevSelectionConfigView
    selection_attestation: MidDevSelectionAttestationView
    rows: tuple[MidDevPlanRowView, ...]
    quality_rows: tuple[MidDevQualityRowView, ...]
    compute_rows: tuple[MidDevDeterministicComputeRowView, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != MID_DEV_DETERMINISTIC_PLAN_VERSION:
            raise ValueError("unsupported MidDev frozen plan version")
        for name in ("corpus_artifact_hash", "source_profile_hash", "analysis_split_hash", "plan_hash"):
            require_sha256(name, getattr(self, name))
        require_clean_string("source_code_commit", self.source_code_commit)
        require_int("ngram_len", self.ngram_len)
        require_int("context_history_size", self.context_history_size)
        if self.ngram_len < 2 or self.context_history_size < 0:
            raise ValueError("invalid MidDev geometry profile")
        if not isinstance(self.selection_config, MidDevSelectionConfigView):
            raise TypeError("selection_config must be MidDevSelectionConfigView")
        if not isinstance(self.selection_attestation, MidDevSelectionAttestationView):
            raise TypeError("selection_attestation must be MidDevSelectionAttestationView")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("MidDev plan rows must be a non-empty tuple")
        row_hashes = {row.plan_row_hash for row in self.rows}
        if len(row_hashes) != len(self.rows):
            raise ValueError("MidDev plan rows must be unique")
        if len(self.quality_rows) != len(self.rows) or {row.plan_row_hash for row in self.quality_rows} != row_hashes:
            raise ValueError("MidDev quality sidecar does not bind every plan row")
        if len(self.compute_rows) != len(self.rows) or {row.plan_row_hash for row in self.compute_rows} != row_hashes:
            raise ValueError("MidDev compute sidecar does not bind every plan row")
        if self.plan_hash != sha256_json(self.payload()):
            raise ValueError("plan_hash does not match MidDev frozen plan")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "legacy_foundation_version": MID_DEV_LEGACY_PLAN_VERSION,
            "corpus_artifact_hash": self.corpus_artifact_hash,
            "source_profile_hash": self.source_profile_hash,
            "analysis_split_hash": self.analysis_split_hash,
            "source_code_commit": self.source_code_commit,
            "ngram_len": self.ngram_len,
            "context_history_size": self.context_history_size,
            "selection_config_hash": self.selection_config.config_hash,
            "selection_attestation_hash": self.selection_attestation.attestation_hash,
            "row_hashes": tuple(row.plan_row_hash for row in self.rows),
            "quality_hashes": tuple(row.quality_hash for row in self.quality_rows),
            "compute_hashes": tuple(row.compute_hash for row in self.compute_rows),
        }


def expected_mid_dev_keys_for_sample() -> set[tuple[MidDevCondition, int, int]]:
    expected = {(MidDevCondition.NO_OP, 0, 0)}
    for budget in MID_DEV_BUDGETS:
        for condition in DETERMINISTIC_BUDGET_CONDITIONS:
            expected.add((condition, budget, 0))
        for replicate in range(MID_DEV_RANDOM_REPLICATES):
            expected.add((MidDevCondition.RANDOM_SAFE, budget, replicate))
    for budget in MID_DEV_BEAM_BUDGETS:
        expected.add((MidDevCondition.CONTEXT_SURVIVAL_BEAM, budget, 0))
    return expected


def validate_complete_mid_dev_matrix(rows: tuple[MidDevPlanRowView, ...]) -> None:
    source_groups = {row.source_group_id for row in rows}
    sample_ids = {row.sample_id for row in rows}
    if len(source_groups) != 36 or len(sample_ids) != 72 or len(rows) != 5688:
        raise ValueError("MidDev frozen plan matrix must be exactly 36 groups, 72 samples, and 5688 rows")
    by_sample: dict[tuple[str, str], list[MidDevPlanRowView]] = {}
    group_labels: dict[str, set[WatermarkLabel]] = {}
    group_metadata: dict[str, set[tuple[str, str, CorpusDomain, int]]] = {}
    for row in rows:
        by_sample.setdefault((row.source_group_id, row.sample_id), []).append(row)
        group_labels.setdefault(row.source_group_id, set()).add(row.source_label)
        group_metadata.setdefault(row.source_group_id, set()).add(
            (row.prompt_id, row.prompt_family_id, row.domain, row.target_length)
        )
    expected = expected_mid_dev_keys_for_sample()
    for group_id in source_groups:
        if group_labels[group_id] != {WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED}:
            raise ValueError("each MidDev source group must contain watermarked and control sources")
        if len(group_metadata[group_id]) != 1:
            raise ValueError("matched MidDev sources must share prompt metadata")
    for values in by_sample.values():
        keys = {(row.condition, row.budget, row.replicate) for row in values}
        if keys != expected or len(values) != len(expected):
            raise ValueError("each MidDev sample must contain the complete frozen plan matrix")
