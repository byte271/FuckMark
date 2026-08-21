from __future__ import annotations

import json
import math
import re
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._validation import (
    require_bool,
    require_clean_string,
    require_int,
    require_sha256,
)
from ..geometry import (
    CounterfactualGeometryEngine,
    GeometryConfig,
    PublicRepetitionGeometry,
)
from ..hashing import sha256_json
from ..scheduling.algorithm_ids import (
    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
)
from ..scheduling.beam_v2 import beam_search_v2, diverse_beam_search
from ..scheduling.context_survival import ContextSurvivalExpander
from ..scheduling.state_search import SearchResult, SearchState, SearchTransition
from ..transforms import InvariantStatus, TransformRegistry, validate_hard_invariants
from ..transforms.contractions import (
    context_survival_contraction_rules,
    contraction_inverse_semantic_resolver,
)
from ..transforms.surface_rules import development_surface_rules
from .diverse_beam_corpus import (
    DIVERSE_BEAM_ANALYSIS_PER_LENGTH,
    DIVERSE_BEAM_TARGET_LENGTHS,
    DiverseBeamFrozenCorpus,
    DiverseBeamGeneratedSample,
)

DIVERSE_BEAM_AB_SEARCH_ROW_VERSION = "diverse-beam-real-corpus-search-row-v1"
DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION = "diverse-beam-real-corpus-search-shard-v1"
DIVERSE_BEAM_AB_ANALYSIS_VERSION = "diverse-beam-real-corpus-analysis-v1"
DIVERSE_BEAM_AB_PROMOTION_RULE_VERSION = "diverse-beam-zero-loss-promotion-rule-v1"
DIVERSE_BEAM_AB_BUDGETS = (1, 2, 4, 6)
DIVERSE_BEAM_AB_BEAM_WIDTH = 32
DIVERSE_BEAM_AB_MAX_RISK_TIER = 1
DIVERSE_BEAM_AB_NGRAM_LEN = 5
DIVERSE_BEAM_AB_CONTEXT_HISTORY_SIZE = 1024
DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT = 64
DIVERSE_BEAM_AB_MAX_VISIBLE_COST_RATIO = 1.10
DIVERSE_BEAM_AB_MAX_RUNTIME_RATIO = 2.0
PROMOTE_DIVERSE_BEAM_V1 = "PROMOTE_DIVERSE_BEAM_V1"
KEEP_BEAM_V2_NO_MATCHED_GAIN = "KEEP_BEAM_V2_NO_MATCHED_GAIN"
KEEP_BEAM_V2_DIVERSE_LOSSES = "KEEP_BEAM_V2_DIVERSE_LOSSES"
KEEP_BEAM_V2_FIDELITY_FAILURE = "KEEP_BEAM_V2_FIDELITY_FAILURE"
KEEP_BEAM_V2_COST_BOUND = "KEEP_BEAM_V2_COST_BOUND"
KEEP_BEAM_V2_RUNTIME_BOUND = "KEEP_BEAM_V2_RUNTIME_BOUND"
KEEP_BEAM_V2_REPLAY_FAILURE = "KEEP_BEAM_V2_REPLAY_FAILURE"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STRATEGIES = (
    CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
    CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
)
_BUDGET_SUMMARY_KEYS = {
    "budget",
    "sample_count",
    "beam_v2_success_count",
    "diverse_beam_success_count",
    "diverse_gain_count",
    "diverse_loss_count",
    "both_success_count",
    "both_failure_count",
    "exact_mcnemar_two_sided_p_value",
    "beam_v2_median_visible_cost",
    "diverse_beam_median_visible_cost",
    "diverse_to_beam_visible_cost_ratio",
    "beam_v2_median_runtime_ns",
    "diverse_beam_median_runtime_ns",
    "diverse_to_beam_runtime_ratio",
    "beam_v2_median_unique_reachable_states",
    "diverse_beam_median_unique_reachable_states",
    "beam_v2_dead_end_row_count",
    "diverse_beam_dead_end_row_count",
    "beam_v2_duplicate_state_suppression_count",
    "diverse_beam_duplicate_state_suppression_count",
}
_AGGREGATE_KEYS = {
    "paired_row_count",
    "beam_v2_success_count",
    "diverse_beam_success_count",
    "diverse_gain_count",
    "diverse_loss_count",
    "both_success_count",
    "both_failure_count",
    "exact_mcnemar_reported_by_budget",
    "beam_v2_median_visible_cost",
    "diverse_beam_median_visible_cost",
    "diverse_to_beam_visible_cost_ratio",
    "beam_v2_median_runtime_ns",
    "diverse_beam_median_runtime_ns",
    "diverse_to_beam_runtime_ratio",
    "hard_invariant_accepted_violation_count",
    "protected_content_accepted_violation_count",
    "deterministic_replay_failure_count",
    "detector_access_observed",
    "secret_access_observed",
}


def _optional_nonnegative(name: str, value: int | None) -> None:
    if value is None:
        return
    require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class DiverseBeamSearchRow:
    algorithm_version: str
    sample_ordinal: int
    sample_id: str
    prompt_family_id: str
    domain: str
    target_length: int
    source_text_hash: str
    strategy: str
    budget: int
    beam_width: int
    max_risk_tier: int
    ruleset_hash: str
    geometry_config_hash: str
    repetition_policy_hash: str
    candidate_pool_hash: str
    root_state_hash: str
    root_candidate_count: int
    root_protected_span_count: int
    exact_depth_success: bool
    exact_state_count: int
    final_state_count: int
    frontier_state_count: int
    result_state_hashes: tuple[str, ...]
    frontier_state_hashes: tuple[str, ...]
    selected_state_hash: str | None
    selected_text_hash: str | None
    selected_operation_hashes: tuple[str, ...]
    highest_risk_tier: int | None
    visible_cost: int | None
    token_edit_distance: int | None
    unique_reachable_state_count: int
    dead_end_state_count: int
    accepted_transition_count: int
    duplicate_state_suppression_count: int
    expanded_state_count: int
    pruned_state_count: int
    expansion_cache_hit_count: int
    expansion_cache_miss_count: int
    hard_invariant_accepted_violation_count: int
    protected_content_accepted_violation_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    search_result_hash: str
    structural_result_hash: str
    deterministic_replay_passed: bool
    runtime_ns: int
    row_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != DIVERSE_BEAM_AB_SEARCH_ROW_VERSION:
            raise ValueError("unsupported Diverse Beam search row version")
        for name in ("sample_id", "prompt_family_id", "domain", "strategy"):
            require_clean_string(name, getattr(self, name))
        if self.strategy not in _STRATEGIES:
            raise ValueError("search row strategy is not part of the matched A/B")
        for name in (
            "sample_ordinal",
            "target_length",
            "budget",
            "beam_width",
            "max_risk_tier",
            "root_candidate_count",
            "root_protected_span_count",
            "exact_state_count",
            "final_state_count",
            "frontier_state_count",
            "unique_reachable_state_count",
            "dead_end_state_count",
            "accepted_transition_count",
            "duplicate_state_suppression_count",
            "expanded_state_count",
            "pruned_state_count",
            "expansion_cache_hit_count",
            "expansion_cache_miss_count",
            "hard_invariant_accepted_violation_count",
            "protected_content_accepted_violation_count",
            "runtime_ns",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.sample_ordinal < 0:
            raise ValueError("sample_ordinal must be non-negative")
        if self.budget not in DIVERSE_BEAM_AB_BUDGETS:
            raise ValueError("search row budget drifted")
        if self.beam_width != DIVERSE_BEAM_AB_BEAM_WIDTH:
            raise ValueError("search row beam width drifted")
        if self.max_risk_tier != DIVERSE_BEAM_AB_MAX_RISK_TIER:
            raise ValueError("search row risk ceiling drifted")
        if self.runtime_ns <= 0:
            raise ValueError("runtime_ns must be positive")
        for name in (
            "source_text_hash",
            "ruleset_hash",
            "geometry_config_hash",
            "repetition_policy_hash",
            "candidate_pool_hash",
            "root_state_hash",
            "search_result_hash",
            "structural_result_hash",
            "row_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in (
            "exact_depth_success",
            "detector_access_observed",
            "secret_access_observed",
            "deterministic_replay_passed",
        ):
            require_bool(name, getattr(self, name))
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("search row is contaminated")
        if not self.deterministic_replay_passed:
            raise ValueError("search row did not replay deterministically")
        for name in (
            "result_state_hashes",
            "frontier_state_hashes",
            "selected_operation_hashes",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise TypeError(f"{name} must be a tuple")
            for item in value:
                require_sha256(name, item)
        for name in ("selected_state_hash", "selected_text_hash"):
            value = getattr(self, name)
            if value is not None:
                require_sha256(name, value)
        for name in ("highest_risk_tier", "visible_cost", "token_edit_distance"):
            _optional_nonnegative(name, getattr(self, name))
        selected_values = (
            self.selected_state_hash,
            self.selected_text_hash,
            self.highest_risk_tier,
            self.visible_cost,
            self.token_edit_distance,
        )
        if self.exact_depth_success:
            if any(value is None for value in selected_values):
                raise ValueError("successful search row must bind a selected state")
            if self.exact_state_count <= 0:
                raise ValueError("successful search row must contain an exact state")
            if len(self.selected_operation_hashes) != self.budget:
                raise ValueError(
                    "selected operation history must match the exact budget"
                )
        elif (
            any(value is not None for value in selected_values)
            or self.selected_operation_hashes
        ):
            raise ValueError("failed search row cannot bind a selected state")
        if self.exact_depth_success != (self.exact_state_count > 0):
            raise ValueError("exact-depth success does not match exact state count")
        if self.exact_state_count != self.final_state_count:
            raise ValueError("every final state must be at the requested exact depth")
        if self.frontier_state_count > self.final_state_count:
            raise ValueError("frontier state count exceeds final state count")
        if len(self.result_state_hashes) != self.final_state_count:
            raise ValueError("result state hash count mismatch")
        if len(self.frontier_state_hashes) != self.frontier_state_count:
            raise ValueError("frontier state hash count mismatch")
        if len(set(self.result_state_hashes)) != len(self.result_state_hashes):
            raise ValueError("result state hashes must be unique")
        if len(set(self.frontier_state_hashes)) != len(self.frontier_state_hashes):
            raise ValueError("frontier state hashes must be unique")
        if not set(self.frontier_state_hashes).issubset(self.result_state_hashes):
            raise ValueError("frontier state hashes must be a subset of result states")
        if self.selected_state_hash is not None and self.selected_state_hash not in set(
            self.result_state_hashes
        ):
            raise ValueError("selected state must be one of the exact result states")
        if self.duplicate_state_suppression_count > self.accepted_transition_count:
            raise ValueError("duplicate suppression exceeds accepted transitions")
        if self.unique_reachable_state_count > self.accepted_transition_count:
            raise ValueError("unique reachable states exceed accepted transitions")
        if self.dead_end_state_count > self.expanded_state_count:
            raise ValueError("dead-end states exceed expanded states")
        if self.expanded_state_count != (
            self.expansion_cache_hit_count + self.expansion_cache_miss_count
        ):
            raise ValueError(
                "expansion cache accounting does not match expanded states"
            )
        if (
            self.hard_invariant_accepted_violation_count
            or self.protected_content_accepted_violation_count
        ):
            raise ValueError("accepted invariant violations are forbidden")
        if self.structural_result_hash != sha256_json(self.structural_payload()):
            raise ValueError("search row structural result hash mismatch")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("search row hash mismatch")

    def structural_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": DIVERSE_BEAM_AB_SEARCH_ROW_VERSION,
            "sample_ordinal": self.sample_ordinal,
            "sample_id": self.sample_id,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain,
            "target_length": self.target_length,
            "source_text_hash": self.source_text_hash,
            "strategy": self.strategy,
            "budget": self.budget,
            "beam_width": self.beam_width,
            "max_risk_tier": self.max_risk_tier,
            "ruleset_hash": self.ruleset_hash,
            "geometry_config_hash": self.geometry_config_hash,
            "repetition_policy_hash": self.repetition_policy_hash,
            "candidate_pool_hash": self.candidate_pool_hash,
            "root_state_hash": self.root_state_hash,
            "root_candidate_count": self.root_candidate_count,
            "root_protected_span_count": self.root_protected_span_count,
            "exact_depth_success": self.exact_depth_success,
            "exact_state_count": self.exact_state_count,
            "final_state_count": self.final_state_count,
            "frontier_state_count": self.frontier_state_count,
            "result_state_hashes": self.result_state_hashes,
            "frontier_state_hashes": self.frontier_state_hashes,
            "selected_state_hash": self.selected_state_hash,
            "selected_text_hash": self.selected_text_hash,
            "selected_operation_hashes": self.selected_operation_hashes,
            "highest_risk_tier": self.highest_risk_tier,
            "visible_cost": self.visible_cost,
            "token_edit_distance": self.token_edit_distance,
            "unique_reachable_state_count": self.unique_reachable_state_count,
            "dead_end_state_count": self.dead_end_state_count,
            "accepted_transition_count": self.accepted_transition_count,
            "duplicate_state_suppression_count": self.duplicate_state_suppression_count,
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "expansion_cache_hit_count": self.expansion_cache_hit_count,
            "expansion_cache_miss_count": self.expansion_cache_miss_count,
            "hard_invariant_accepted_violation_count": self.hard_invariant_accepted_violation_count,
            "protected_content_accepted_violation_count": self.protected_content_accepted_violation_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
            "search_result_hash": self.search_result_hash,
        }

    def payload(self) -> dict[str, object]:
        return {
            **self.structural_payload(),
            "structural_result_hash": self.structural_result_hash,
            "deterministic_replay_passed": self.deterministic_replay_passed,
            "runtime_ns": self.runtime_ns,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "row_hash": self.row_hash}

    @classmethod
    def create(
        cls,
        structural_payload: dict[str, object],
        *,
        runtime_ns: int,
        replay_structural_hash: str,
    ) -> DiverseBeamSearchRow:
        structural_hash = sha256_json(structural_payload)
        replay_passed = structural_hash == replay_structural_hash
        payload = {
            **structural_payload,
            "structural_result_hash": structural_hash,
            "deterministic_replay_passed": replay_passed,
            "runtime_ns": runtime_ns,
        }
        return cls(**payload, row_hash=sha256_json(payload))


@dataclass(frozen=True, slots=True)
class DiverseBeamSearchShard:
    algorithm_version: str
    source_code_commit: str
    frozen_corpus_hash: str
    runtime_tokenizer_identity_hash: str
    ruleset_hash: str
    geometry_config_hash: str
    repetition_policy_hash: str
    budgets: tuple[int, ...]
    beam_width: int
    max_risk_tier: int
    shard_index: int
    shard_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    rows: tuple[DiverseBeamSearchRow, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION:
            raise ValueError("unsupported Diverse Beam search shard version")
        if _GIT_SHA_RE.fullmatch(self.source_code_commit) is None:
            raise ValueError("source_code_commit must be a lowercase Git SHA")
        for name in (
            "frozen_corpus_hash",
            "runtime_tokenizer_identity_hash",
            "ruleset_hash",
            "geometry_config_hash",
            "repetition_policy_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if self.budgets != DIVERSE_BEAM_AB_BUDGETS:
            raise ValueError("search shard budgets drifted")
        if self.beam_width != DIVERSE_BEAM_AB_BEAM_WIDTH:
            raise ValueError("search shard beam width drifted")
        if self.max_risk_tier != DIVERSE_BEAM_AB_MAX_RISK_TIER:
            raise ValueError("search shard risk ceiling drifted")
        require_int("shard_index", self.shard_index)
        require_int("shard_count", self.shard_count)
        if self.shard_count != DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT:
            raise ValueError("search shard count drifted")
        if not 0 <= self.shard_index < self.shard_count:
            raise ValueError("search shard index is out of range")
        require_bool("detector_access_observed", self.detector_access_observed)
        require_bool("secret_access_observed", self.secret_access_observed)
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("search shard is contaminated")
        if not isinstance(self.rows, tuple) or any(
            not isinstance(value, DiverseBeamSearchRow) for value in self.rows
        ):
            raise TypeError("rows must contain DiverseBeamSearchRow values")
        expected_order = tuple(
            sorted(
                self.rows,
                key=lambda value: (value.sample_id, value.budget, value.strategy),
            )
        )
        if self.rows != expected_order:
            raise ValueError("search shard rows must be canonically ordered")
        keys = tuple(
            (value.sample_id, value.budget, value.strategy) for value in self.rows
        )
        if len(set(keys)) != len(keys):
            raise ValueError("search shard row keys must be unique")
        for row in self.rows:
            if row.ruleset_hash != self.ruleset_hash:
                raise ValueError("search shard row ruleset drifted")
            if row.geometry_config_hash != self.geometry_config_hash:
                raise ValueError("search shard row geometry config drifted")
            if row.repetition_policy_hash != self.repetition_policy_hash:
                raise ValueError("search shard row repetition policy drifted")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("search shard artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_code_commit": self.source_code_commit,
            "frozen_corpus_hash": self.frozen_corpus_hash,
            "runtime_tokenizer_identity_hash": self.runtime_tokenizer_identity_hash,
            "ruleset_hash": self.ruleset_hash,
            "geometry_config_hash": self.geometry_config_hash,
            "repetition_policy_hash": self.repetition_policy_hash,
            "budgets": self.budgets,
            "beam_width": self.beam_width,
            "max_risk_tier": self.max_risk_tier,
            "shard_index": self.shard_index,
            "shard_count": self.shard_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
            "rows": tuple(value.as_dict() for value in self.rows),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "artifact_hash": self.artifact_hash}


class _ObservedMemoizedExpander:
    def __init__(
        self,
        expander: ContextSurvivalExpander,
        *,
        source_text: str,
        registry: TransformRegistry,
    ) -> None:
        self._expander = expander
        self._source_text = source_text
        self._registry = registry
        self._cache: dict[str, tuple[SearchTransition, ...]] = {}
        self.begin()

    @property
    def detector_access_observed(self) -> bool:
        return self._expander.detector_access_observed

    @property
    def secret_access_observed(self) -> bool:
        return self._expander.secret_access_observed

    def begin(self) -> None:
        self._accepted = 0
        self._dead_ends = 0
        self._hits = 0
        self._misses = 0
        self._child_hashes: set[str] = set()
        self._child_hashes_by_depth: dict[int, list[str]] = defaultdict(list)

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        transitions = self._cache.get(state.search_state_hash)
        if transitions is None:
            transitions = tuple(self._expander.expand(state))
            for transition in transitions:
                report = validate_hard_invariants(
                    self._source_text,
                    transition.child.text,
                    self._registry.identifiers,
                )
                if report.status is not InvariantStatus.PASS:
                    raise RuntimeError(
                        "search expander accepted a hard-invariant violation"
                    )
                if report.protected_report.status is not InvariantStatus.PASS:
                    raise RuntimeError(
                        "search expander accepted a protected-content violation"
                    )
            self._cache[state.search_state_hash] = transitions
            self._misses += 1
        else:
            self._hits += 1
        if not transitions:
            self._dead_ends += 1
        self._accepted += len(transitions)
        for transition in transitions:
            child = transition.child
            self._child_hashes.add(child.text_hash)
            self._child_hashes_by_depth[child.depth].append(child.text_hash)
        return transitions

    def metrics(self) -> dict[str, int]:
        duplicate_count = sum(
            len(values) - len(set(values))
            for values in self._child_hashes_by_depth.values()
        )
        return {
            "unique_reachable_state_count": len(self._child_hashes),
            "dead_end_state_count": self._dead_ends,
            "accepted_transition_count": self._accepted,
            "duplicate_state_suppression_count": duplicate_count,
            "expansion_cache_hit_count": self._hits,
            "expansion_cache_miss_count": self._misses,
            "hard_invariant_accepted_violation_count": 0,
            "protected_content_accepted_violation_count": 0,
        }


@dataclass(frozen=True, slots=True)
class _SearchObservation:
    structural_payload: dict[str, object]
    structural_hash: str
    runtime_ns: int


def _registry() -> TransformRegistry:
    return TransformRegistry(
        (*context_survival_contraction_rules(), *development_surface_rules())
    )


def _state_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.surviving_root_observations,
        -state.newly_masked_count,
        state.highest_risk_tier,
        state.visible_cost,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _encode_with_offsets(
    tokenizer: Any,
    sample: DiverseBeamGeneratedSample,
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    encoded = tokenizer(
        sample.text, add_special_tokens=False, return_offsets_mapping=True
    )
    ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]
    if ids and isinstance(ids[0], list):
        if len(ids) != 1:
            raise ValueError("unexpected batched tokenizer output")
        ids = ids[0]
        offsets = offsets[0]
    token_ids = tuple(int(value) for value in ids)
    normalized_offsets = tuple((int(start), int(end)) for start, end in offsets)
    if token_ids != sample.text_only_token_ids:
        raise ValueError(
            "runtime tokenizer does not replay the frozen text-only token track"
        )
    if len(token_ids) != len(normalized_offsets):
        raise ValueError("runtime tokenizer IDs and offsets differ in length")
    return token_ids, normalized_offsets


def _search_function(strategy: str) -> Callable[..., SearchResult]:
    if strategy == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
        return beam_search_v2
    if strategy == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION:
        return diverse_beam_search
    raise ValueError("unknown Diverse Beam A/B strategy")


def _run_strategy_pass(
    *,
    sample: DiverseBeamGeneratedSample,
    tokenizer: Any,
    registry: TransformRegistry,
    repetition: PublicRepetitionGeometry,
    config: GeometryConfig,
    strategy: str,
) -> dict[int, _SearchObservation]:
    token_ids, offsets = _encode_with_offsets(tokenizer, sample)
    geometry_engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=config,
        eligibility_policy=repetition.eligibility_policy,
    )
    base_expander = ContextSurvivalExpander(
        registry=registry,
        geometry_engine=geometry_engine,
        source_sample_id=sample.sample_id,
        source_text=sample.text,
        max_risk_tier=DIVERSE_BEAM_AB_MAX_RISK_TIER,
        inverse_semantic_resolver=contraction_inverse_semantic_resolver,
    )
    expander = _ObservedMemoizedExpander(
        base_expander,
        source_text=sample.text,
        registry=registry,
    )
    root = base_expander.root_state
    geometry_root = geometry_engine.build_root(
        source_sample_id=sample.sample_id,
        source_text=sample.text,
    )
    if tuple(geometry_root.root_tokens) != token_ids:
        raise ValueError("geometry root does not replay the frozen token track")
    enumeration = registry.enumerate(sample.text)
    protected_count = len(enumeration.protected_manifest.spans)
    candidate_pool_hash = sha256_json(
        {
            "ruleset_hash": registry.ruleset_hash,
            "enumeration_hash": enumeration.enumeration_hash,
            "geometry_config_hash": config.config_hash,
            "repetition_policy_hash": repetition.policy_hash,
            "token_ids": token_ids,
            "offsets": offsets,
        }
    )
    search = _search_function(strategy)
    output = {}
    for budget in DIVERSE_BEAM_AB_BUDGETS:
        expander.begin()
        started = time.perf_counter_ns()
        result = search(expander, root, budget, DIVERSE_BEAM_AB_BEAM_WIDTH)
        runtime_ns = time.perf_counter_ns() - started
        if runtime_ns <= 0:
            runtime_ns = 1
        exact_states = tuple(value for value in result.states if value.depth == budget)
        selected = min(exact_states, key=_state_rank) if exact_states else None
        metrics = expander.metrics()
        structural = {
            "algorithm_version": DIVERSE_BEAM_AB_SEARCH_ROW_VERSION,
            "sample_ordinal": sample.ordinal,
            "sample_id": sample.sample_id,
            "prompt_family_id": sample.prompt_family_id,
            "domain": sample.domain,
            "target_length": sample.target_length,
            "source_text_hash": sample.text_hash,
            "strategy": strategy,
            "budget": budget,
            "beam_width": DIVERSE_BEAM_AB_BEAM_WIDTH,
            "max_risk_tier": DIVERSE_BEAM_AB_MAX_RISK_TIER,
            "ruleset_hash": registry.ruleset_hash,
            "geometry_config_hash": config.config_hash,
            "repetition_policy_hash": repetition.policy_hash,
            "candidate_pool_hash": candidate_pool_hash,
            "root_state_hash": root.search_state_hash,
            "root_candidate_count": len(enumeration.candidates),
            "root_protected_span_count": protected_count,
            "exact_depth_success": bool(exact_states),
            "exact_state_count": len(exact_states),
            "final_state_count": len(result.states),
            "frontier_state_count": len(result.frontier),
            "result_state_hashes": tuple(
                value.search_state_hash for value in result.states
            ),
            "frontier_state_hashes": tuple(
                value.search_state_hash for value in result.frontier
            ),
            "selected_state_hash": selected.search_state_hash
            if selected is not None
            else None,
            "selected_text_hash": selected.text_hash if selected is not None else None,
            "selected_operation_hashes": selected.operation_hashes
            if selected is not None
            else (),
            "highest_risk_tier": selected.highest_risk_tier
            if selected is not None
            else None,
            "visible_cost": selected.visible_cost if selected is not None else None,
            "token_edit_distance": selected.token_edit_distance
            if selected is not None
            else None,
            **metrics,
            "expanded_state_count": result.expanded_state_count,
            "pruned_state_count": result.pruned_state_count,
            "detector_access_observed": result.detector_access_observed,
            "secret_access_observed": result.secret_access_observed,
            "search_result_hash": result.result_hash,
        }
        output[budget] = _SearchObservation(
            structural_payload=structural,
            structural_hash=sha256_json(structural),
            runtime_ns=runtime_ns,
        )
    return output


def _run_strategy(
    *,
    sample: DiverseBeamGeneratedSample,
    tokenizer: Any,
    registry: TransformRegistry,
    repetition: PublicRepetitionGeometry,
    config: GeometryConfig,
    strategy: str,
) -> tuple[DiverseBeamSearchRow, ...]:
    first = _run_strategy_pass(
        sample=sample,
        tokenizer=tokenizer,
        registry=registry,
        repetition=repetition,
        config=config,
        strategy=strategy,
    )
    replay = _run_strategy_pass(
        sample=sample,
        tokenizer=tokenizer,
        registry=registry,
        repetition=repetition,
        config=config,
        strategy=strategy,
    )
    return tuple(
        DiverseBeamSearchRow.create(
            first[budget].structural_payload,
            runtime_ns=first[budget].runtime_ns,
            replay_structural_hash=replay[budget].structural_hash,
        )
        for budget in DIVERSE_BEAM_AB_BUDGETS
    )


def run_diverse_beam_search_shard(
    corpus: DiverseBeamFrozenCorpus,
    tokenizer: Any,
    *,
    runtime_tokenizer_identity_hash: str,
    shard_index: int,
    shard_count: int,
    source_code_commit: str,
) -> DiverseBeamSearchShard:
    require_int("shard_index", shard_index)
    require_int("shard_count", shard_count)
    if shard_count != DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT:
        raise ValueError("shard_count must match the frozen search profile")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index is out of range")
    if source_code_commit != corpus.source_code_commit:
        raise ValueError("search source commit does not match the frozen corpus")
    require_sha256("runtime_tokenizer_identity_hash", runtime_tokenizer_identity_hash)
    if runtime_tokenizer_identity_hash != corpus.model_identity_hash:
        raise ValueError("runtime tokenizer identity does not match the frozen corpus")
    registry = _registry()
    repetition = PublicRepetitionGeometry.create(
        ngram_len=DIVERSE_BEAM_AB_NGRAM_LEN,
        context_history_size=DIVERSE_BEAM_AB_CONTEXT_HISTORY_SIZE,
    )
    config = GeometryConfig.create(
        tokenizer_identity_hash=runtime_tokenizer_identity_hash,
        ngram_len=DIVERSE_BEAM_AB_NGRAM_LEN,
        repetition_mask_policy_id=repetition.policy_id,
    )
    samples = tuple(
        value for value in corpus.samples if value.ordinal % shard_count == shard_index
    )
    rows = []
    for sample in samples:
        strategies = (
            _STRATEGIES if sample.ordinal % 2 == 0 else tuple(reversed(_STRATEGIES))
        )
        for strategy in strategies:
            rows.extend(
                _run_strategy(
                    sample=sample,
                    tokenizer=tokenizer,
                    registry=registry,
                    repetition=repetition,
                    config=config,
                    strategy=strategy,
                )
            )
    ordered = tuple(
        sorted(rows, key=lambda value: (value.sample_id, value.budget, value.strategy))
    )
    payload = {
        "algorithm_version": DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION,
        "source_code_commit": source_code_commit,
        "frozen_corpus_hash": corpus.artifact_hash,
        "runtime_tokenizer_identity_hash": runtime_tokenizer_identity_hash,
        "ruleset_hash": registry.ruleset_hash,
        "geometry_config_hash": config.config_hash,
        "repetition_policy_hash": repetition.policy_hash,
        "budgets": DIVERSE_BEAM_AB_BUDGETS,
        "beam_width": DIVERSE_BEAM_AB_BEAM_WIDTH,
        "max_risk_tier": DIVERSE_BEAM_AB_MAX_RISK_TIER,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "rows": tuple(value.as_dict() for value in ordered),
    }
    return DiverseBeamSearchShard(
        algorithm_version=DIVERSE_BEAM_AB_SEARCH_SHARD_VERSION,
        source_code_commit=source_code_commit,
        frozen_corpus_hash=corpus.artifact_hash,
        runtime_tokenizer_identity_hash=runtime_tokenizer_identity_hash,
        ruleset_hash=registry.ruleset_hash,
        geometry_config_hash=config.config_hash,
        repetition_policy_hash=repetition.policy_hash,
        budgets=DIVERSE_BEAM_AB_BUDGETS,
        beam_width=DIVERSE_BEAM_AB_BEAM_WIDTH,
        max_risk_tier=DIVERSE_BEAM_AB_MAX_RISK_TIER,
        shard_index=shard_index,
        shard_count=shard_count,
        detector_access_observed=False,
        secret_access_observed=False,
        rows=ordered,
        artifact_hash=sha256_json(payload),
    )


def _exact_mcnemar_p_value(gain_count: int, loss_count: int) -> float:
    require_int("gain_count", gain_count)
    require_int("loss_count", loss_count)
    if gain_count < 0 or loss_count < 0:
        raise ValueError("McNemar discordant counts must be non-negative")
    discordant = gain_count + loss_count
    if discordant == 0:
        return 1.0
    lower = min(gain_count, loss_count)
    numerator = sum(math.comb(discordant, value) for value in range(lower + 1))
    return min(1.0, 2.0 * (numerator / (2**discordant)))


def _median(values: Sequence[int]) -> float | None:
    materialized = tuple(values)
    if not materialized:
        return None
    return float(statistics.median(materialized))


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0.0:
        return 1.0 if numerator == 0.0 else None
    return numerator / denominator


def _promotion_decision(
    *,
    gains: int,
    losses: int,
    cost_ok: bool,
    runtime_ok: bool,
    fidelity_ok: bool,
    replay_ok: bool,
) -> str:
    if not replay_ok:
        return KEEP_BEAM_V2_REPLAY_FAILURE
    if not fidelity_ok:
        return KEEP_BEAM_V2_FIDELITY_FAILURE
    if gains == 0:
        return KEEP_BEAM_V2_NO_MATCHED_GAIN
    if losses > 0:
        return KEEP_BEAM_V2_DIVERSE_LOSSES
    if not cost_ok:
        return KEEP_BEAM_V2_COST_BOUND
    if not runtime_ok:
        return KEEP_BEAM_V2_RUNTIME_BOUND
    return PROMOTE_DIVERSE_BEAM_V1


def _budget_summary(
    budget: int,
    rows: Sequence[DiverseBeamSearchRow],
) -> dict[str, object]:
    by_key = {
        (value.sample_id, value.strategy): value
        for value in rows
        if value.budget == budget
    }
    sample_ids = tuple(
        sorted({value.sample_id for value in rows if value.budget == budget})
    )
    beam_rows = tuple(
        by_key[(sample_id, CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION)]
        for sample_id in sample_ids
    )
    diverse_rows = tuple(
        by_key[(sample_id, CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION)]
        for sample_id in sample_ids
    )
    gains = sum(
        not beam.exact_depth_success and diverse.exact_depth_success
        for beam, diverse in zip(beam_rows, diverse_rows)
    )
    losses = sum(
        beam.exact_depth_success and not diverse.exact_depth_success
        for beam, diverse in zip(beam_rows, diverse_rows)
    )
    matched = tuple(
        (beam, diverse)
        for beam, diverse in zip(beam_rows, diverse_rows)
        if beam.exact_depth_success and diverse.exact_depth_success
    )
    beam_cost = _median(tuple(value[0].visible_cost for value in matched))
    diverse_cost = _median(tuple(value[1].visible_cost for value in matched))
    beam_runtime = _median(tuple(value.runtime_ns for value in beam_rows))
    diverse_runtime = _median(tuple(value.runtime_ns for value in diverse_rows))
    return {
        "budget": budget,
        "sample_count": len(sample_ids),
        "beam_v2_success_count": sum(value.exact_depth_success for value in beam_rows),
        "diverse_beam_success_count": sum(
            value.exact_depth_success for value in diverse_rows
        ),
        "diverse_gain_count": gains,
        "diverse_loss_count": losses,
        "both_success_count": len(matched),
        "both_failure_count": sum(
            not beam.exact_depth_success and not diverse.exact_depth_success
            for beam, diverse in zip(beam_rows, diverse_rows)
        ),
        "exact_mcnemar_two_sided_p_value": _exact_mcnemar_p_value(gains, losses),
        "beam_v2_median_visible_cost": beam_cost,
        "diverse_beam_median_visible_cost": diverse_cost,
        "diverse_to_beam_visible_cost_ratio": _ratio(diverse_cost, beam_cost),
        "beam_v2_median_runtime_ns": beam_runtime,
        "diverse_beam_median_runtime_ns": diverse_runtime,
        "diverse_to_beam_runtime_ratio": _ratio(diverse_runtime, beam_runtime),
        "beam_v2_median_unique_reachable_states": _median(
            tuple(value.unique_reachable_state_count for value in beam_rows)
        ),
        "diverse_beam_median_unique_reachable_states": _median(
            tuple(value.unique_reachable_state_count for value in diverse_rows)
        ),
        "beam_v2_dead_end_row_count": sum(
            value.dead_end_state_count > 0 for value in beam_rows
        ),
        "diverse_beam_dead_end_row_count": sum(
            value.dead_end_state_count > 0 for value in diverse_rows
        ),
        "beam_v2_duplicate_state_suppression_count": sum(
            value.duplicate_state_suppression_count for value in beam_rows
        ),
        "diverse_beam_duplicate_state_suppression_count": sum(
            value.duplicate_state_suppression_count for value in diverse_rows
        ),
    }


def _validate_search_shards_against_corpus(
    corpus: DiverseBeamFrozenCorpus,
    shards: Sequence[DiverseBeamSearchShard],
) -> tuple[DiverseBeamSearchRow, ...]:
    materialized = tuple(sorted(shards, key=lambda value: value.shard_index))
    if len(materialized) != DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT:
        raise ValueError("analysis requires every Diverse Beam search shard")
    if tuple(value.shard_index for value in materialized) != tuple(
        range(DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT)
    ):
        raise ValueError("search shard indices must be complete")
    for name in (
        "source_code_commit",
        "frozen_corpus_hash",
        "runtime_tokenizer_identity_hash",
        "ruleset_hash",
        "geometry_config_hash",
        "repetition_policy_hash",
    ):
        values = {getattr(value, name) for value in materialized}
        if len(values) != 1:
            raise ValueError(f"search shards mixed {name}")
    if materialized[0].source_code_commit != corpus.source_code_commit:
        raise ValueError("search shards do not bind the frozen corpus source commit")
    if materialized[0].frozen_corpus_hash != corpus.artifact_hash:
        raise ValueError("search shards do not bind the frozen corpus hash")
    if materialized[0].runtime_tokenizer_identity_hash != corpus.model_identity_hash:
        raise ValueError("search shards do not bind the frozen tokenizer identity")
    rows = tuple(
        sorted(
            (row for shard in materialized for row in shard.rows),
            key=lambda value: (value.sample_id, value.budget, value.strategy),
        )
    )
    expected_keys = {
        (sample.sample_id, budget, strategy)
        for sample in corpus.samples
        for budget in DIVERSE_BEAM_AB_BUDGETS
        for strategy in _STRATEGIES
    }
    keys = {(value.sample_id, value.budget, value.strategy) for value in rows}
    if len(rows) != len(expected_keys) or keys != expected_keys:
        raise ValueError(
            "search shards do not cover every frozen sample/budget/strategy cell"
        )
    samples = {value.sample_id: value for value in corpus.samples}
    shard_by_row_hash = {
        row.row_hash: shard.shard_index for shard in materialized for row in shard.rows
    }
    if len(shard_by_row_hash) != len(rows):
        raise ValueError("search row hashes must be unique across shards")
    by_pair: dict[tuple[str, int], list[DiverseBeamSearchRow]] = defaultdict(list)
    for row in rows:
        sample = samples[row.sample_id]
        if (
            row.sample_ordinal % DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT
            != shard_by_row_hash[row.row_hash]
        ):
            raise ValueError("search row is assigned to the wrong shard")
        if (
            row.sample_ordinal,
            row.prompt_family_id,
            row.domain,
            row.target_length,
            row.source_text_hash,
        ) != (
            sample.ordinal,
            sample.prompt_family_id,
            sample.domain,
            sample.target_length,
            sample.text_hash,
        ):
            raise ValueError("search row does not bind its frozen source sample")
        by_pair[(row.sample_id, row.budget)].append(row)
    for pair in by_pair.values():
        if len(pair) != 2:
            raise ValueError("matched search pair is incomplete")
        left, right = pair
        if (
            left.candidate_pool_hash,
            left.root_state_hash,
            left.root_candidate_count,
            left.root_protected_span_count,
        ) != (
            right.candidate_pool_hash,
            right.root_state_hash,
            right.root_candidate_count,
            right.root_protected_span_count,
        ):
            raise ValueError("matched search conditions differ beyond pruning strategy")
    return rows


def analyze_diverse_beam_search(
    corpus: DiverseBeamFrozenCorpus,
    shards: Sequence[DiverseBeamSearchShard],
) -> dict[str, object]:
    materialized = tuple(sorted(shards, key=lambda value: value.shard_index))
    rows = _validate_search_shards_against_corpus(corpus, materialized)
    per_budget = tuple(
        _budget_summary(value, rows) for value in DIVERSE_BEAM_AB_BUDGETS
    )
    beam_rows = tuple(
        value
        for value in rows
        if value.strategy == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
    )
    diverse_rows = tuple(
        value
        for value in rows
        if value.strategy == CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    )
    pair_map = {(value.sample_id, value.budget): value for value in diverse_rows}
    gains = sum(
        not value.exact_depth_success
        and pair_map[(value.sample_id, value.budget)].exact_depth_success
        for value in beam_rows
    )
    losses = sum(
        value.exact_depth_success
        and not pair_map[(value.sample_id, value.budget)].exact_depth_success
        for value in beam_rows
    )
    matched = tuple(
        (value, pair_map[(value.sample_id, value.budget)])
        for value in beam_rows
        if value.exact_depth_success
        and pair_map[(value.sample_id, value.budget)].exact_depth_success
    )
    beam_cost = _median(tuple(value[0].visible_cost for value in matched))
    diverse_cost = _median(tuple(value[1].visible_cost for value in matched))
    beam_runtime = _median(tuple(value.runtime_ns for value in beam_rows))
    diverse_runtime = _median(tuple(value.runtime_ns for value in diverse_rows))
    aggregate = {
        "paired_row_count": len(beam_rows),
        "beam_v2_success_count": sum(value.exact_depth_success for value in beam_rows),
        "diverse_beam_success_count": sum(
            value.exact_depth_success for value in diverse_rows
        ),
        "diverse_gain_count": gains,
        "diverse_loss_count": losses,
        "both_success_count": len(matched),
        "both_failure_count": sum(
            not value.exact_depth_success
            and not pair_map[(value.sample_id, value.budget)].exact_depth_success
            for value in beam_rows
        ),
        "exact_mcnemar_reported_by_budget": True,
        "beam_v2_median_visible_cost": beam_cost,
        "diverse_beam_median_visible_cost": diverse_cost,
        "diverse_to_beam_visible_cost_ratio": _ratio(diverse_cost, beam_cost),
        "beam_v2_median_runtime_ns": beam_runtime,
        "diverse_beam_median_runtime_ns": diverse_runtime,
        "diverse_to_beam_runtime_ratio": _ratio(diverse_runtime, beam_runtime),
        "hard_invariant_accepted_violation_count": sum(
            value.hard_invariant_accepted_violation_count for value in rows
        ),
        "protected_content_accepted_violation_count": sum(
            value.protected_content_accepted_violation_count for value in rows
        ),
        "deterministic_replay_failure_count": sum(
            not value.deterministic_replay_passed for value in rows
        ),
        "detector_access_observed": any(
            value.detector_access_observed for value in rows
        ),
        "secret_access_observed": any(value.secret_access_observed for value in rows),
    }
    cost_cells = tuple(
        value
        for value in per_budget
        if value["diverse_gain_count"] or value["both_success_count"]
    )
    cost_ok = bool(cost_cells) and all(
        value["diverse_to_beam_visible_cost_ratio"] is not None
        and value["diverse_to_beam_visible_cost_ratio"]
        <= DIVERSE_BEAM_AB_MAX_VISIBLE_COST_RATIO
        for value in cost_cells
    )
    runtime_ok = aggregate["diverse_to_beam_runtime_ratio"] is not None and (
        aggregate["diverse_to_beam_runtime_ratio"] <= DIVERSE_BEAM_AB_MAX_RUNTIME_RATIO
    )
    fidelity_ok = (
        aggregate["hard_invariant_accepted_violation_count"] == 0
        and aggregate["protected_content_accepted_violation_count"] == 0
        and not aggregate["detector_access_observed"]
        and not aggregate["secret_access_observed"]
    )
    replay_ok = aggregate["deterministic_replay_failure_count"] == 0
    decision = _promotion_decision(
        gains=gains,
        losses=losses,
        cost_ok=cost_ok,
        runtime_ok=runtime_ok,
        fidelity_ok=fidelity_ok,
        replay_ok=replay_ok,
    )
    promoted = decision == PROMOTE_DIVERSE_BEAM_V1
    payload = {
        "algorithm_version": DIVERSE_BEAM_AB_ANALYSIS_VERSION,
        "promotion_rule_version": DIVERSE_BEAM_AB_PROMOTION_RULE_VERSION,
        "source_code_commit": corpus.source_code_commit,
        "frozen_corpus_hash": corpus.artifact_hash,
        "search_shard_hashes": tuple(value.artifact_hash for value in materialized),
        "sample_count": len(corpus.samples),
        "samples_per_target_length": corpus.samples_per_target_length,
        "duplicate_excluded_count": corpus.duplicate_excluded_count,
        "row_count": len(rows),
        "budgets": DIVERSE_BEAM_AB_BUDGETS,
        "beam_width": DIVERSE_BEAM_AB_BEAM_WIDTH,
        "max_risk_tier": DIVERSE_BEAM_AB_MAX_RISK_TIER,
        "beam_v2_algorithm_version": CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        "diverse_beam_algorithm_version": CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION,
        "promotion_requires_strict_gain": True,
        "promotion_allowed_loss_count": 0,
        "max_visible_cost_ratio": DIVERSE_BEAM_AB_MAX_VISIBLE_COST_RATIO,
        "max_runtime_ratio": DIVERSE_BEAM_AB_MAX_RUNTIME_RATIO,
        "per_budget": per_budget,
        "aggregate": aggregate,
        "cost_bound_passed": cost_ok,
        "runtime_bound_passed": runtime_ok,
        "fidelity_gate_passed": fidelity_ok,
        "replay_gate_passed": replay_ok,
        "decision": decision,
        "promoted": promoted,
        "scientific_scope": "Detector-blind DEV_KEYS attack-development search-pruning comparison only",
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs
    )
    if not isinstance(value, dict):
        raise TypeError("artifact must be a JSON object")
    return value


def _require_keys(value: dict[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match the frozen schema")


def _row_from_dict(value: object) -> DiverseBeamSearchRow:
    if not isinstance(value, dict):
        raise TypeError("search row must be an object")
    expected = set(DiverseBeamSearchRow.__dataclass_fields__)
    _require_keys(value, expected, "search row")
    normalized = dict(value)
    for name in (
        "result_state_hashes",
        "frontier_state_hashes",
        "selected_operation_hashes",
    ):
        if not isinstance(normalized[name], list):
            raise TypeError(f"{name} must be a list")
        normalized[name] = tuple(normalized[name])
    return DiverseBeamSearchRow(**normalized)


def load_diverse_beam_search_shard(path: Path) -> DiverseBeamSearchShard:
    value = _read_object(path)
    expected = set(DiverseBeamSearchShard.__dataclass_fields__)
    _require_keys(value, expected, "search shard")
    for name in ("budgets", "rows"):
        if not isinstance(value[name], list):
            raise TypeError(f"{name} must be a list")
    return DiverseBeamSearchShard(
        algorithm_version=value["algorithm_version"],
        source_code_commit=value["source_code_commit"],
        frozen_corpus_hash=value["frozen_corpus_hash"],
        runtime_tokenizer_identity_hash=value["runtime_tokenizer_identity_hash"],
        ruleset_hash=value["ruleset_hash"],
        geometry_config_hash=value["geometry_config_hash"],
        repetition_policy_hash=value["repetition_policy_hash"],
        budgets=tuple(value["budgets"]),
        beam_width=value["beam_width"],
        max_risk_tier=value["max_risk_tier"],
        shard_index=value["shard_index"],
        shard_count=value["shard_count"],
        detector_access_observed=value["detector_access_observed"],
        secret_access_observed=value["secret_access_observed"],
        rows=tuple(_row_from_dict(item) for item in value["rows"]),
        artifact_hash=value["artifact_hash"],
    )


def _require_nonnegative_integer(name: str, value: object) -> int:
    require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_finite_number(
    name: str,
    value: object,
    *,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    if normalized < 0.0 or (positive and normalized <= 0.0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be {qualifier}")
    return normalized


def _require_optional_number(
    name: str,
    value: object,
    *,
    present: bool,
    positive: bool = False,
) -> float | None:
    if not present:
        if value is not None:
            raise ValueError(f"{name} must be null without matched observations")
        return None
    return _require_finite_number(name, value, positive=positive)


def _require_matching_ratio(
    name: str,
    value: object,
    numerator: float | None,
    denominator: float | None,
) -> None:
    expected = _ratio(numerator, denominator)
    if expected is None:
        if value is not None:
            raise ValueError(f"{name} must be null when its ratio is undefined")
        return
    observed = _require_finite_number(name, value)
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError(f"{name} does not match its component medians")


def _validate_budget_summary(
    value: object, expected_budget: int, sample_count: int
) -> None:
    if not isinstance(value, dict):
        raise TypeError("Diverse Beam budget summary must be an object")
    _require_keys(value, _BUDGET_SUMMARY_KEYS, "Diverse Beam budget summary")
    if value["budget"] != expected_budget or value["sample_count"] != sample_count:
        raise ValueError("Diverse Beam budget summary cell drifted")
    count_names = (
        "beam_v2_success_count",
        "diverse_beam_success_count",
        "diverse_gain_count",
        "diverse_loss_count",
        "both_success_count",
        "both_failure_count",
        "beam_v2_dead_end_row_count",
        "diverse_beam_dead_end_row_count",
        "beam_v2_duplicate_state_suppression_count",
        "diverse_beam_duplicate_state_suppression_count",
    )
    counts = {
        name: _require_nonnegative_integer(name, value[name]) for name in count_names
    }
    for name in count_names[:8]:
        if counts[name] > sample_count:
            raise ValueError(f"{name} exceeds the budget sample count")
    if counts["beam_v2_success_count"] != (
        counts["both_success_count"] + counts["diverse_loss_count"]
    ):
        raise ValueError("Beam v2 budget success accounting is inconsistent")
    if counts["diverse_beam_success_count"] != (
        counts["both_success_count"] + counts["diverse_gain_count"]
    ):
        raise ValueError("Diverse Beam budget success accounting is inconsistent")
    if sample_count != (
        counts["both_success_count"]
        + counts["both_failure_count"]
        + counts["diverse_gain_count"]
        + counts["diverse_loss_count"]
    ):
        raise ValueError("Diverse Beam budget pair accounting is inconsistent")
    p_value = _require_finite_number(
        "exact_mcnemar_two_sided_p_value",
        value["exact_mcnemar_two_sided_p_value"],
    )
    if p_value > 1.0 or not math.isclose(
        p_value,
        _exact_mcnemar_p_value(
            counts["diverse_gain_count"], counts["diverse_loss_count"]
        ),
        rel_tol=1e-12,
        abs_tol=0.0,
    ):
        raise ValueError("Diverse Beam budget McNemar result is inconsistent")
    has_matched_success = counts["both_success_count"] > 0
    beam_cost = _require_optional_number(
        "beam_v2_median_visible_cost",
        value["beam_v2_median_visible_cost"],
        present=has_matched_success,
        positive=True,
    )
    diverse_cost = _require_optional_number(
        "diverse_beam_median_visible_cost",
        value["diverse_beam_median_visible_cost"],
        present=has_matched_success,
        positive=True,
    )
    _require_matching_ratio(
        "diverse_to_beam_visible_cost_ratio",
        value["diverse_to_beam_visible_cost_ratio"],
        diverse_cost,
        beam_cost,
    )
    beam_runtime = _require_finite_number(
        "beam_v2_median_runtime_ns",
        value["beam_v2_median_runtime_ns"],
        positive=True,
    )
    diverse_runtime = _require_finite_number(
        "diverse_beam_median_runtime_ns",
        value["diverse_beam_median_runtime_ns"],
        positive=True,
    )
    _require_matching_ratio(
        "diverse_to_beam_runtime_ratio",
        value["diverse_to_beam_runtime_ratio"],
        diverse_runtime,
        beam_runtime,
    )
    _require_finite_number(
        "beam_v2_median_unique_reachable_states",
        value["beam_v2_median_unique_reachable_states"],
    )
    _require_finite_number(
        "diverse_beam_median_unique_reachable_states",
        value["diverse_beam_median_unique_reachable_states"],
    )


def load_diverse_beam_analysis(path: Path) -> dict[str, object]:
    value = _read_object(path)
    expected = {
        "algorithm_version",
        "promotion_rule_version",
        "source_code_commit",
        "frozen_corpus_hash",
        "search_shard_hashes",
        "sample_count",
        "samples_per_target_length",
        "duplicate_excluded_count",
        "row_count",
        "budgets",
        "beam_width",
        "max_risk_tier",
        "beam_v2_algorithm_version",
        "diverse_beam_algorithm_version",
        "promotion_requires_strict_gain",
        "promotion_allowed_loss_count",
        "max_visible_cost_ratio",
        "max_runtime_ratio",
        "per_budget",
        "aggregate",
        "cost_bound_passed",
        "runtime_bound_passed",
        "fidelity_gate_passed",
        "replay_gate_passed",
        "decision",
        "promoted",
        "scientific_scope",
        "artifact_hash",
    }
    _require_keys(value, expected, "Diverse Beam analysis")
    if value["algorithm_version"] != DIVERSE_BEAM_AB_ANALYSIS_VERSION:
        raise ValueError("unsupported Diverse Beam analysis version")
    if value["promotion_rule_version"] != DIVERSE_BEAM_AB_PROMOTION_RULE_VERSION:
        raise ValueError("Diverse Beam promotion rule version drifted")
    if _GIT_SHA_RE.fullmatch(value["source_code_commit"] or "") is None:
        raise ValueError("Diverse Beam analysis source commit is invalid")
    require_sha256("frozen_corpus_hash", value["frozen_corpus_hash"])
    if not isinstance(value["search_shard_hashes"], list):
        raise TypeError("search_shard_hashes must be a list")
    if len(value["search_shard_hashes"]) != DIVERSE_BEAM_AB_SEARCH_SHARD_COUNT:
        raise ValueError("Diverse Beam analysis requires every search shard hash")
    if len(set(value["search_shard_hashes"])) != len(value["search_shard_hashes"]):
        raise ValueError("Diverse Beam search shard hashes must be unique")
    for item in value["search_shard_hashes"]:
        require_sha256("search_shard_hash", item)
    expected_sample_count = (
        len(DIVERSE_BEAM_TARGET_LENGTHS) * DIVERSE_BEAM_ANALYSIS_PER_LENGTH
    )
    if value["sample_count"] != expected_sample_count:
        raise ValueError("Diverse Beam analysis sample count drifted")
    if value["samples_per_target_length"] != DIVERSE_BEAM_ANALYSIS_PER_LENGTH:
        raise ValueError("Diverse Beam analysis length-cell size drifted")
    _require_nonnegative_integer(
        "duplicate_excluded_count", value["duplicate_excluded_count"]
    )
    expected_row_count = expected_sample_count * len(DIVERSE_BEAM_AB_BUDGETS) * 2
    if value["row_count"] != expected_row_count:
        raise ValueError("Diverse Beam analysis row count drifted")
    if value["budgets"] != list(DIVERSE_BEAM_AB_BUDGETS):
        raise ValueError("Diverse Beam analysis budgets drifted")
    if value["beam_width"] != DIVERSE_BEAM_AB_BEAM_WIDTH:
        raise ValueError("Diverse Beam analysis beam width drifted")
    if value["max_risk_tier"] != DIVERSE_BEAM_AB_MAX_RISK_TIER:
        raise ValueError("Diverse Beam analysis risk ceiling drifted")
    if value["beam_v2_algorithm_version"] != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
        raise ValueError("Diverse Beam analysis Beam v2 identity drifted")
    if (
        value["diverse_beam_algorithm_version"]
        != CONTEXT_SURVIVAL_DIVERSE_BEAM_ALGORITHM_VERSION
    ):
        raise ValueError("Diverse Beam analysis strategy identity drifted")
    require_bool(
        "promotion_requires_strict_gain", value["promotion_requires_strict_gain"]
    )
    if not value["promotion_requires_strict_gain"]:
        raise ValueError("Diverse Beam promotion must require a strict gain")
    if value["promotion_allowed_loss_count"] != 0:
        raise ValueError("Diverse Beam promotion must allow zero losses")
    if value["max_visible_cost_ratio"] != DIVERSE_BEAM_AB_MAX_VISIBLE_COST_RATIO:
        raise ValueError("Diverse Beam visible-cost bound drifted")
    if value["max_runtime_ratio"] != DIVERSE_BEAM_AB_MAX_RUNTIME_RATIO:
        raise ValueError("Diverse Beam runtime bound drifted")
    if not isinstance(value["per_budget"], list):
        raise TypeError("Diverse Beam per_budget must be a list")
    if len(value["per_budget"]) != len(DIVERSE_BEAM_AB_BUDGETS):
        raise ValueError("Diverse Beam budget summaries are incomplete")
    for summary, budget in zip(value["per_budget"], DIVERSE_BEAM_AB_BUDGETS):
        _validate_budget_summary(summary, budget, expected_sample_count)
    aggregate = value["aggregate"]
    if not isinstance(aggregate, dict):
        raise TypeError("Diverse Beam aggregate must be an object")
    _require_keys(aggregate, _AGGREGATE_KEYS, "Diverse Beam aggregate")
    aggregate_count_names = (
        "paired_row_count",
        "beam_v2_success_count",
        "diverse_beam_success_count",
        "diverse_gain_count",
        "diverse_loss_count",
        "both_success_count",
        "both_failure_count",
        "hard_invariant_accepted_violation_count",
        "protected_content_accepted_violation_count",
        "deterministic_replay_failure_count",
    )
    aggregate_counts = {
        name: _require_nonnegative_integer(name, aggregate[name])
        for name in aggregate_count_names
    }
    expected_pair_count = expected_sample_count * len(DIVERSE_BEAM_AB_BUDGETS)
    if aggregate_counts["paired_row_count"] != expected_pair_count:
        raise ValueError("Diverse Beam aggregate pair count drifted")
    for name in aggregate_count_names[1:7]:
        if aggregate_counts[name] != sum(
            summary[name] for summary in value["per_budget"]
        ):
            raise ValueError(f"Diverse Beam aggregate {name} is inconsistent")
    if aggregate_counts["beam_v2_success_count"] != (
        aggregate_counts["both_success_count"] + aggregate_counts["diverse_loss_count"]
    ):
        raise ValueError("Diverse Beam aggregate Beam v2 accounting is inconsistent")
    if aggregate_counts["diverse_beam_success_count"] != (
        aggregate_counts["both_success_count"] + aggregate_counts["diverse_gain_count"]
    ):
        raise ValueError("Diverse Beam aggregate strategy accounting is inconsistent")
    if expected_pair_count != (
        aggregate_counts["both_success_count"]
        + aggregate_counts["both_failure_count"]
        + aggregate_counts["diverse_gain_count"]
        + aggregate_counts["diverse_loss_count"]
    ):
        raise ValueError("Diverse Beam aggregate pair accounting is inconsistent")
    require_bool(
        "exact_mcnemar_reported_by_budget",
        aggregate["exact_mcnemar_reported_by_budget"],
    )
    if not aggregate["exact_mcnemar_reported_by_budget"]:
        raise ValueError("Diverse Beam analysis must report McNemar by budget")
    has_aggregate_success = aggregate_counts["both_success_count"] > 0
    beam_cost = _require_optional_number(
        "beam_v2_median_visible_cost",
        aggregate["beam_v2_median_visible_cost"],
        present=has_aggregate_success,
        positive=True,
    )
    diverse_cost = _require_optional_number(
        "diverse_beam_median_visible_cost",
        aggregate["diverse_beam_median_visible_cost"],
        present=has_aggregate_success,
        positive=True,
    )
    _require_matching_ratio(
        "diverse_to_beam_visible_cost_ratio",
        aggregate["diverse_to_beam_visible_cost_ratio"],
        diverse_cost,
        beam_cost,
    )
    beam_runtime = _require_finite_number(
        "beam_v2_median_runtime_ns",
        aggregate["beam_v2_median_runtime_ns"],
        positive=True,
    )
    diverse_runtime = _require_finite_number(
        "diverse_beam_median_runtime_ns",
        aggregate["diverse_beam_median_runtime_ns"],
        positive=True,
    )
    _require_matching_ratio(
        "diverse_to_beam_runtime_ratio",
        aggregate["diverse_to_beam_runtime_ratio"],
        diverse_runtime,
        beam_runtime,
    )
    for name in ("detector_access_observed", "secret_access_observed"):
        require_bool(name, aggregate[name])
    cost_cells = tuple(
        summary
        for summary in value["per_budget"]
        if summary["diverse_gain_count"] or summary["both_success_count"]
    )
    expected_cost_ok = bool(cost_cells) and all(
        summary["diverse_to_beam_visible_cost_ratio"] is not None
        and summary["diverse_to_beam_visible_cost_ratio"]
        <= DIVERSE_BEAM_AB_MAX_VISIBLE_COST_RATIO
        for summary in cost_cells
    )
    expected_runtime_ok = (
        aggregate["diverse_to_beam_runtime_ratio"] is not None
        and aggregate["diverse_to_beam_runtime_ratio"]
        <= DIVERSE_BEAM_AB_MAX_RUNTIME_RATIO
    )
    expected_fidelity_ok = (
        aggregate_counts["hard_invariant_accepted_violation_count"] == 0
        and aggregate_counts["protected_content_accepted_violation_count"] == 0
        and not aggregate["detector_access_observed"]
        and not aggregate["secret_access_observed"]
    )
    expected_replay_ok = aggregate_counts["deterministic_replay_failure_count"] == 0
    for name, expected_value in (
        ("cost_bound_passed", expected_cost_ok),
        ("runtime_bound_passed", expected_runtime_ok),
        ("fidelity_gate_passed", expected_fidelity_ok),
        ("replay_gate_passed", expected_replay_ok),
    ):
        require_bool(name, value[name])
        if value[name] != expected_value:
            raise ValueError(f"Diverse Beam {name} is inconsistent")
    expected_decision = _promotion_decision(
        gains=aggregate_counts["diverse_gain_count"],
        losses=aggregate_counts["diverse_loss_count"],
        cost_ok=expected_cost_ok,
        runtime_ok=expected_runtime_ok,
        fidelity_ok=expected_fidelity_ok,
        replay_ok=expected_replay_ok,
    )
    if value["decision"] != expected_decision:
        raise ValueError("Diverse Beam promotion decision is inconsistent")
    require_bool("promoted", value["promoted"])
    if value["promoted"] != (expected_decision == PROMOTE_DIVERSE_BEAM_V1):
        raise ValueError("Diverse Beam promotion flag and decision disagree")
    if (
        value["scientific_scope"]
        != "Detector-blind DEV_KEYS attack-development search-pruning comparison only"
    ):
        raise ValueError("Diverse Beam scientific scope drifted")
    payload = {key: item for key, item in value.items() if key != "artifact_hash"}
    require_sha256("artifact_hash", value["artifact_hash"])
    if value["artifact_hash"] != sha256_json(payload):
        raise ValueError("Diverse Beam analysis artifact hash mismatch")
    return value
