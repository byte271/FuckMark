from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..corpus.mid_dev import MidDevAttackArtifact
from ..corpus.mid_dev_validation import validate_mid_dev_experiment_identity
from ..geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from ..hashing import derive_seed, sha256_json, sha256_text
from ..scheduling.beam_v2 import beam_search_v2
from ..scheduling.context_survival import ContextSurvivalExpander
from ..scheduling.state_search import SearchResult, SearchState, greedy_search
from ..transforms import (
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    build_candidate_tokenizer_geometry,
)
from ..transforms.contractions import contraction_inverse_semantic_resolver
from .context_survival_plan import (
    _baseline_variant,
    _context_registry,
    _encode_with_offsets,
    _select_result_state,
    _state_variant,
    _stateful_random,
)
from .mid_dev_context_survival import (
    MID_DEV_BEAM_BUDGETS,
    MID_DEV_BUDGETS,
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
    SUCCESS,
)
from .mid_dev_freeze import (
    MidDevDeterministicComputeRow,
    MidDevDeterministicFrozenPlan,
)
from .mid_dev_quality import (
    numbers_preserved_fraction,
    old_observation_replacement_ratio,
    protected_span_violation_count,
    urls_preserved_fraction,
    word_edit_rate,
)


MID_DEV_PLAN_BUILDER_VERSION = "mid-dev-plan-builder-v1"
MID_DEV_SELECTION_TRACE_VERSION = "mid-dev-selection-trace-v1"
MID_DEV_TRACE_ARTIFACT_VERSION = "mid-dev-selection-trace-artifact-v1"
MID_DEV_SEED_DERIVATION_BASE = 0x4D49444445565031


@dataclass(frozen=True, slots=True)
class MidDevSelectionTrace:
    source_group_id: str
    sample_id: str
    condition: MidDevCondition
    budget: int
    replicate: int
    schedule_seed: int
    candidate_pool_hash: str
    scheduler_input_hash: str
    schedule_result_hash: str
    final_search_state_hash: str | None
    operation_hashes: tuple[str, ...]
    transition_hashes: tuple[str, ...]
    status: str
    trace_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.condition, MidDevCondition):
            raise TypeError("condition must be MidDevCondition")
        for name in (
            "candidate_pool_hash",
            "scheduler_input_hash",
            "schedule_result_hash",
            "trace_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{name} must be a SHA-256 hex digest")
        if self.final_search_state_hash is not None and len(self.final_search_state_hash) != 64:
            raise ValueError("final_search_state_hash must be a SHA-256 hex digest")
        if self.trace_hash != sha256_json(self.payload()):
            raise ValueError("trace_hash does not match MidDev selection trace")

    @classmethod
    def create(
        cls,
        *,
        source_group_id: str,
        sample_id: str,
        condition: MidDevCondition,
        budget: int,
        replicate: int,
        schedule_seed: int,
        candidate_pool_hash: str,
        scheduler_input_hash: str,
        schedule_result_hash: str,
        final_search_state_hash: str | None,
        operation_hashes: tuple[str, ...],
        transition_hashes: tuple[str, ...],
        status: str,
    ) -> "MidDevSelectionTrace":
        payload = {
            "algorithm_version": MID_DEV_SELECTION_TRACE_VERSION,
            "source_group_id": source_group_id,
            "sample_id": sample_id,
            "condition": condition.value,
            "budget": budget,
            "replicate": replicate,
            "schedule_seed": schedule_seed,
            "candidate_pool_hash": candidate_pool_hash,
            "scheduler_input_hash": scheduler_input_hash,
            "schedule_result_hash": schedule_result_hash,
            "final_search_state_hash": final_search_state_hash,
            "operation_hashes": operation_hashes,
            "transition_hashes": transition_hashes,
            "status": status,
        }
        return cls(
            source_group_id,
            sample_id,
            condition,
            budget,
            replicate,
            schedule_seed,
            candidate_pool_hash,
            scheduler_input_hash,
            schedule_result_hash,
            final_search_state_hash,
            operation_hashes,
            transition_hashes,
            status,
            sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_SELECTION_TRACE_VERSION,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "condition": self.condition.value,
            "budget": self.budget,
            "replicate": self.replicate,
            "schedule_seed": self.schedule_seed,
            "candidate_pool_hash": self.candidate_pool_hash,
            "scheduler_input_hash": self.scheduler_input_hash,
            "schedule_result_hash": self.schedule_result_hash,
            "final_search_state_hash": self.final_search_state_hash,
            "operation_hashes": self.operation_hashes,
            "transition_hashes": self.transition_hashes,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class MidDevSelectionTraceArtifact:
    plan_hash: str
    traces: tuple[MidDevSelectionTrace, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.plan_hash, str) or len(self.plan_hash) != 64:
            raise ValueError("plan_hash must be a SHA-256 hex digest")
        if not isinstance(self.traces, tuple) or not self.traces:
            raise ValueError("traces must be a non-empty tuple")
        if len({value.trace_hash for value in self.traces}) != len(self.traces):
            raise ValueError("selection trace hashes must be unique")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match selection trace artifact")

    @classmethod
    def create(
        cls,
        *,
        plan_hash: str,
        traces: tuple[MidDevSelectionTrace, ...],
    ) -> "MidDevSelectionTraceArtifact":
        materialized = tuple(
            sorted(
                traces,
                key=lambda value: (
                    value.source_group_id,
                    value.sample_id,
                    value.condition.value,
                    value.budget,
                    value.replicate,
                ),
            )
        )
        payload = {
            "algorithm_version": MID_DEV_TRACE_ARTIFACT_VERSION,
            "plan_hash": plan_hash,
            "trace_hashes": tuple(value.trace_hash for value in materialized),
        }
        return cls(plan_hash, materialized, sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_TRACE_ARTIFACT_VERSION,
            "plan_hash": self.plan_hash,
            "trace_hashes": tuple(value.trace_hash for value in self.traces),
        }


@dataclass(frozen=True, slots=True)
class _ExpansionSnapshot:
    expand_call_count: int
    cache_hit_count: int
    cache_miss_count: int
    transition_option_count: int


class _CountingMemoizedExpander:
    def __init__(self, expander: ContextSurvivalExpander) -> None:
        self._expander = expander
        self._cache: dict[str, tuple[Any, ...]] = {}
        self.expand_call_count = 0
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self.transition_option_count = 0

    @property
    def detector_access_observed(self) -> bool:
        return self._expander.detector_access_observed

    @property
    def secret_access_observed(self) -> bool:
        return self._expander.secret_access_observed

    def expand(self, state: SearchState) -> tuple[Any, ...]:
        self.expand_call_count += 1
        cached = self._cache.get(state.search_state_hash)
        if cached is not None:
            self.cache_hit_count += 1
            self.transition_option_count += len(cached)
            return cached
        transitions = tuple(self._expander.expand(state))
        self._cache[state.search_state_hash] = transitions
        self.cache_miss_count += 1
        self.transition_option_count += len(transitions)
        return transitions

    def snapshot(self) -> _ExpansionSnapshot:
        return _ExpansionSnapshot(
            self.expand_call_count,
            self.cache_hit_count,
            self.cache_miss_count,
            self.transition_option_count,
        )


def _snapshot_delta(
    before: _ExpansionSnapshot,
    after: _ExpansionSnapshot,
) -> tuple[int, int, int, int]:
    return (
        after.expand_call_count - before.expand_call_count,
        after.cache_hit_count - before.cache_hit_count,
        after.cache_miss_count - before.cache_miss_count,
        after.transition_option_count - before.transition_option_count,
    )


def _schedule_seed(
    sample_id: str,
    condition: MidDevCondition,
    budget: int,
    replicate: int,
) -> int:
    return derive_seed(
        MID_DEV_SEED_DERIVATION_BASE,
        MID_DEV_PLAN_BUILDER_VERSION,
        sample_id,
        condition.value,
        str(budget),
        str(replicate),
        bits=64,
    )


def _token_ids(tokenizer: Any, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    values = encoded["input_ids"] if isinstance(encoded, dict) else encoded
    if values and isinstance(values[0], list):
        if len(values) != 1:
            raise ValueError("unexpected batched tokenizer output")
        values = values[0]
    return tuple(int(value) for value in values)


def _trace_from_variant(
    *,
    source: Any,
    condition: MidDevCondition,
    budget: int,
    replicate: int,
    seed: int,
    candidate_pool_hash: str,
    variant: dict[str, object],
) -> MidDevSelectionTrace:
    transition_hashes = tuple(str(value) for value in variant.get("transition_hashes", ()))
    operation_hashes = tuple(str(value) for value in variant.get("operation_hashes", ()))
    return MidDevSelectionTrace.create(
        source_group_id=source.match_id,
        sample_id=source.sample_id,
        condition=condition,
        budget=budget,
        replicate=replicate,
        schedule_seed=seed,
        candidate_pool_hash=candidate_pool_hash,
        scheduler_input_hash=str(variant["scheduler_input_hash"]),
        schedule_result_hash=str(variant["schedule_result_hash"]),
        final_search_state_hash=(
            None
            if variant.get("search_state_hash") is None
            else str(variant["search_state_hash"])
        ),
        operation_hashes=operation_hashes,
        transition_hashes=transition_hashes,
        status=str(variant["status"]),
    )


def _quality_row(
    *,
    source: Any,
    tokenizer: Any,
    ngram_len: int,
    plan_row: MidDevPlanRow,
    variant: dict[str, object],
) -> MidDevQualityRow:
    transformed_text = str(variant["transformed_text"])
    transformed_tokens = _token_ids(tokenizer, transformed_text)
    if source.text_only_tokens is None:
        raise ValueError("MidDev source has no text-only token track")
    return MidDevQualityRow.create(
        plan_row_hash=plan_row.plan_row_hash,
        word_edit_rate=word_edit_rate(source.text, transformed_text),
        old_observation_replacement_ratio=old_observation_replacement_ratio(
            source.text_only_tokens.token_ids,
            transformed_tokens,
            ngram_len,
        ),
        exact_destruction_ratio=float(variant["exact_destruction_ratio"]),
        exact_survival_ratio=float(variant["exact_survival_ratio"]),
        token_edit_distance=int(variant["token_edit_distance"]),
        length_ratio=len(transformed_text) / max(1, len(source.text)),
        numbers_preserved_fraction=numbers_preserved_fraction(source.text, transformed_text),
        urls_preserved_fraction=urls_preserved_fraction(source.text, transformed_text),
        protected_span_violation_count=protected_span_violation_count(
            source.text,
            transformed_text,
        ),
        hard_invariant_status=str(variant["hard_invariant_status"]),
    )


def _plan_bundle(
    *,
    source: Any,
    tokenizer: Any,
    ngram_len: int,
    condition: MidDevCondition,
    budget: int,
    replicate: int,
    seed: int,
    candidate_pool_hash: str,
    variant: dict[str, object],
    compute: MidDevDeterministicComputeRow | None,
) -> tuple[MidDevPlanRow, MidDevQualityRow, MidDevSelectionTrace, MidDevDeterministicComputeRow]:
    trace = _trace_from_variant(
        source=source,
        condition=condition,
        budget=budget,
        replicate=replicate,
        seed=seed,
        candidate_pool_hash=candidate_pool_hash,
        variant=variant,
    )
    row = MidDevPlanRow.create(
        source_group_id=source.match_id,
        prompt_id=source.prompt_id,
        sample_id=source.sample_id,
        source_label=source.label,
        prompt_family_id=source.prompt_family_id,
        domain=source.domain,
        target_length=source.target_length,
        source_text_hash=source.text_sha256,
        condition=condition,
        budget=budget,
        replicate=replicate,
        transformed_text=str(variant["transformed_text"]),
        operation_count=int(variant["realized_edit_cost"]),
        status=str(variant["status"]),
        selection_trace_hash=trace.trace_hash,
    )
    quality = _quality_row(
        source=source,
        tokenizer=tokenizer,
        ngram_len=ngram_len,
        plan_row=row,
        variant=variant,
    )
    if compute is None:
        compute = MidDevDeterministicComputeRow.create(
            plan_row_hash=row.plan_row_hash,
            expanded_state_count=0,
            pruned_state_count=0,
            candidate_evaluation_count=0,
            expansion_cache_hit_count=0,
            expansion_cache_miss_count=0,
            geometry_cache_hit_count=0,
        )
    elif compute.plan_row_hash != row.plan_row_hash:
        compute = MidDevDeterministicComputeRow.create(
            plan_row_hash=row.plan_row_hash,
            expanded_state_count=compute.expanded_state_count,
            pruned_state_count=compute.pruned_state_count,
            candidate_evaluation_count=compute.candidate_evaluation_count,
            expansion_cache_hit_count=compute.expansion_cache_hit_count,
            expansion_cache_miss_count=compute.expansion_cache_miss_count,
            geometry_cache_hit_count=compute.geometry_cache_hit_count,
            selection_detector_query_count=compute.selection_detector_query_count,
            selection_secret_query_count=compute.selection_secret_query_count,
        )
    return row, quality, trace, compute


def _compute_row(
    *,
    placeholder_hash: str,
    before: _ExpansionSnapshot,
    after: _ExpansionSnapshot,
    geometry_hits_before: int,
    geometry_hits_after: int,
    search_result: SearchResult | None,
) -> MidDevDeterministicComputeRow:
    expand_calls, cache_hits, cache_misses, options = _snapshot_delta(before, after)
    return MidDevDeterministicComputeRow.create(
        plan_row_hash=placeholder_hash,
        expanded_state_count=(
            expand_calls if search_result is None else search_result.expanded_state_count
        ),
        pruned_state_count=(0 if search_result is None else search_result.pruned_state_count),
        candidate_evaluation_count=options,
        expansion_cache_hit_count=cache_hits,
        expansion_cache_miss_count=cache_misses,
        geometry_cache_hit_count=max(0, geometry_hits_after - geometry_hits_before),
    )


def _identity_variant(
    source: Any,
    root_state: SearchState,
    candidate_pool_hash: str,
) -> dict[str, object]:
    payload = {
        "algorithm_version": "mid-dev-no-op-v1",
        "source_sample_id": source.sample_id,
        "candidate_pool_hash": candidate_pool_hash,
        "root_state_hash": root_state.search_state_hash,
    }
    result_hash = sha256_json(payload)
    return {
        "scheduler_input_hash": root_state.search_state_hash,
        "schedule_result_hash": result_hash,
        "transition_hashes": (),
        "search_state_hash": root_state.search_state_hash,
        "operation_hashes": (),
        "status": SUCCESS,
        "hard_invariant_status": "pass",
        "realized_edit_cost": 0,
        "token_edit_distance": 0,
        "exact_survival_ratio": 1.0,
        "exact_destruction_ratio": 0.0,
        "transformed_text": source.text,
    }


def build_mid_dev_context_survival_plan(
    artifact: MidDevAttackArtifact,
    tokenizer: Any,
    *,
    ngram_len: int = 5,
    context_history_size: int = 1024,
    source_code_commit: str,
) -> tuple[MidDevDeterministicFrozenPlan, MidDevSelectionTraceArtifact]:
    validate_mid_dev_experiment_identity(artifact)
    if not isinstance(source_code_commit, str) or not source_code_commit:
        raise ValueError("source_code_commit must be non-empty")
    if ngram_len < 2:
        raise ValueError("ngram_len must be at least two")
    if context_history_size < 0:
        raise ValueError("context_history_size must be non-negative")

    config = MidDevSelectionConfig.frozen()
    registry = _context_registry()
    repetition = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    samples = tuple(sorted(artifact.manifest.samples, key=lambda value: value.sample_id))
    rows: list[MidDevPlanRow] = []
    quality_rows: list[MidDevQualityRow] = []
    compute_rows: list[MidDevDeterministicComputeRow] = []
    traces: list[MidDevSelectionTrace] = []
    expanders: list[_CountingMemoizedExpander] = []

    for source in samples:
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        geometry_config = GeometryConfig.create(
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=ngram_len,
            repetition_mask_policy_id=repetition.policy_id,
        )
        geometry_engine = CounterfactualGeometryEngine(
            tokenizer=tokenizer,
            config=geometry_config,
            eligibility_policy=repetition.eligibility_policy,
        )
        base_expander = ContextSurvivalExpander(
            registry=registry,
            geometry_engine=geometry_engine,
            source_sample_id=source.sample_id,
            source_text=source.text,
            max_risk_tier=config.max_risk_tier,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        expander = _CountingMemoizedExpander(base_expander)
        expanders.append(expander)
        root_state = base_expander.root_state
        root = geometry_engine.build_root(
            source_sample_id=source.sample_id,
            source_text=source.text,
        )
        if tuple(root.root_tokens) != token_ids:
            raise ValueError("MidDev geometry root does not replay frozen text-only tokens")
        enumeration = registry.enumerate(source.text)
        tokenizer_geometry = build_candidate_tokenizer_geometry(
            source.text,
            enumeration,
            token_ids,
            offsets,
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=ngram_len,
        )
        scheduler_input = KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=tokenizer_geometry.coverage_mapping(),
            budget_unit="operation",
            geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
        )
        candidate_pool_hash = sha256_json(
            {
                "builder_version": MID_DEV_PLAN_BUILDER_VERSION,
                "ruleset_hash": registry.ruleset_hash,
                "enumeration_hash": enumeration.enumeration_hash,
                "tokenizer_geometry_hash": tokenizer_geometry.geometry_hash,
                "geometry_config_hash": geometry_config.config_hash,
                "repetition_policy_hash": repetition.policy_hash,
            }
        )

        identity_variant = _identity_variant(source, root_state, candidate_pool_hash)
        row, quality, trace, compute = _plan_bundle(
            source=source,
            tokenizer=tokenizer,
            ngram_len=ngram_len,
            condition=MidDevCondition.NO_OP,
            budget=0,
            replicate=0,
            seed=0,
            candidate_pool_hash=candidate_pool_hash,
            variant=identity_variant,
            compute=None,
        )
        rows.append(row)
        quality_rows.append(quality)
        traces.append(trace)
        compute_rows.append(compute)

        for budget in MID_DEV_BUDGETS:
            for condition, policy in (
                (
                    MidDevCondition.CURRENT_STRONGEST_BASELINE,
                    SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
                ),
                (MidDevCondition.EVEN_SPACING, SchedulePolicy.EVEN_SPACING),
            ):
                seed = _schedule_seed(source.sample_id, condition, budget, 0)
                geometry_hits_before = geometry_engine.cache_hit_count
                variant = _baseline_variant(
                    registry=registry,
                    geometry_engine=geometry_engine,
                    root=root,
                    root_state=root_state,
                    enumeration=enumeration,
                    scheduler_input=scheduler_input,
                    candidate_pool_hash=candidate_pool_hash,
                    source=source,
                    policy=policy,
                    budget=budget,
                    seed=seed,
                )
                placeholder = MidDevDeterministicComputeRow.create(
                    plan_row_hash=sha256_text("placeholder"),
                    expanded_state_count=0,
                    pruned_state_count=0,
                    candidate_evaluation_count=len(enumeration.candidates),
                    expansion_cache_hit_count=0,
                    expansion_cache_miss_count=0,
                    geometry_cache_hit_count=max(
                        0,
                        geometry_engine.cache_hit_count - geometry_hits_before,
                    ),
                )
                row, quality, trace, compute = _plan_bundle(
                    source=source,
                    tokenizer=tokenizer,
                    ngram_len=ngram_len,
                    condition=condition,
                    budget=budget,
                    replicate=0,
                    seed=seed,
                    candidate_pool_hash=candidate_pool_hash,
                    variant=variant,
                    compute=placeholder,
                )
                rows.append(row)
                quality_rows.append(quality)
                traces.append(trace)
                compute_rows.append(compute)

            for replicate in range(MID_DEV_RANDOM_REPLICATES):
                condition = MidDevCondition.RANDOM_SAFE
                seed = _schedule_seed(source.sample_id, condition, budget, replicate)
                before = expander.snapshot()
                geometry_hits_before = geometry_engine.cache_hit_count
                state, transition_hashes, result_hash, status = _stateful_random(
                    expander,
                    root_state,
                    budget,
                    seed,
                )
                variant = _state_variant(
                    source=source,
                    root=root_state,
                    policy=condition.value,
                    budget=budget,
                    seed=seed,
                    state=state,
                    status=status,
                    schedule_result_hash=result_hash,
                    candidate_pool_hash=candidate_pool_hash,
                    transition_hashes=transition_hashes,
                )
                placeholder = _compute_row(
                    placeholder_hash=sha256_text("placeholder"),
                    before=before,
                    after=expander.snapshot(),
                    geometry_hits_before=geometry_hits_before,
                    geometry_hits_after=geometry_engine.cache_hit_count,
                    search_result=None,
                )
                row, quality, trace, compute = _plan_bundle(
                    source=source,
                    tokenizer=tokenizer,
                    ngram_len=ngram_len,
                    condition=condition,
                    budget=budget,
                    replicate=replicate,
                    seed=seed,
                    candidate_pool_hash=candidate_pool_hash,
                    variant=variant,
                    compute=placeholder,
                )
                rows.append(row)
                quality_rows.append(quality)
                traces.append(trace)
                compute_rows.append(compute)

            condition = MidDevCondition.CONTEXT_SURVIVAL_GREEDY
            seed = _schedule_seed(source.sample_id, condition, budget, 0)
            before = expander.snapshot()
            geometry_hits_before = geometry_engine.cache_hit_count
            result = greedy_search(expander, root_state, budget)
            state, status = _select_result_state(result, budget)
            variant = _state_variant(
                source=source,
                root=root_state,
                policy=condition.value,
                budget=budget,
                seed=seed,
                state=state,
                status=status,
                schedule_result_hash=result.result_hash,
                candidate_pool_hash=candidate_pool_hash,
            )
            placeholder = _compute_row(
                placeholder_hash=sha256_text("placeholder"),
                before=before,
                after=expander.snapshot(),
                geometry_hits_before=geometry_hits_before,
                geometry_hits_after=geometry_engine.cache_hit_count,
                search_result=result,
            )
            row, quality, trace, compute = _plan_bundle(
                source=source,
                tokenizer=tokenizer,
                ngram_len=ngram_len,
                condition=condition,
                budget=budget,
                replicate=0,
                seed=seed,
                candidate_pool_hash=candidate_pool_hash,
                variant=variant,
                compute=placeholder,
            )
            rows.append(row)
            quality_rows.append(quality)
            traces.append(trace)
            compute_rows.append(compute)

            if budget in MID_DEV_BEAM_BUDGETS:
                condition = MidDevCondition.CONTEXT_SURVIVAL_BEAM
                seed = _schedule_seed(source.sample_id, condition, budget, 0)
                before = expander.snapshot()
                geometry_hits_before = geometry_engine.cache_hit_count
                result = beam_search_v2(
                    expander,
                    root_state,
                    budget,
                    config.beam_width,
                )
                state, status = _select_result_state(result, budget)
                variant = _state_variant(
                    source=source,
                    root=root_state,
                    policy=condition.value,
                    budget=budget,
                    seed=seed,
                    state=state,
                    status=status,
                    schedule_result_hash=result.result_hash,
                    candidate_pool_hash=candidate_pool_hash,
                )
                placeholder = _compute_row(
                    placeholder_hash=sha256_text("placeholder"),
                    before=before,
                    after=expander.snapshot(),
                    geometry_hits_before=geometry_hits_before,
                    geometry_hits_after=geometry_engine.cache_hit_count,
                    search_result=result,
                )
                row, quality, trace, compute = _plan_bundle(
                    source=source,
                    tokenizer=tokenizer,
                    ngram_len=ngram_len,
                    condition=condition,
                    budget=budget,
                    replicate=0,
                    seed=seed,
                    candidate_pool_hash=candidate_pool_hash,
                    variant=variant,
                    compute=placeholder,
                )
                rows.append(row)
                quality_rows.append(quality)
                traces.append(trace)
                compute_rows.append(compute)

    detector_access = any(value.detector_access_observed for value in expanders)
    secret_access = any(value.secret_access_observed for value in expanders)
    attestation = MidDevSelectionAttestation.from_observed(
        attested_expander_count=len(expanders),
        detector_access_observed=detector_access,
        secret_access_observed=secret_access,
        detector_query_count=0,
        secret_query_count=0,
    )
    plan = MidDevDeterministicFrozenPlan.create(
        corpus_artifact_hash=artifact.artifact_hash,
        source_profile_hash=artifact.source_profile_hash,
        analysis_split_hash=artifact.analysis_split_hash,
        source_code_commit=source_code_commit,
        selection_config=config,
        selection_attestation=attestation,
        rows=rows,
        quality_rows=quality_rows,
        compute_rows=compute_rows,
    )
    trace_artifact = MidDevSelectionTraceArtifact.create(
        plan_hash=plan.plan_hash,
        traces=tuple(traces),
    )
    if {value.selection_trace_hash for value in plan.rows} != {
        value.trace_hash for value in trace_artifact.traces
    }:
        raise ValueError("MidDev plan rows do not bind the complete trace artifact")
    return plan, trace_artifact
