from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .._validation import require_int
from ..corpus import CorpusSplit
from ..geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from ..hashing import derive_seed, sha256_json, sha256_text
from ..scheduling.context_survival import ContextSurvivalExpander
from ..scheduling.state_search import SearchResult, SearchState, beam_search, exact_b1, exact_b2, greedy_search
from ..transforms import (
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
    TransformRegistry,
    build_candidate_tokenizer_geometry,
)
from ..transforms.contractions import context_survival_contraction_rules, contraction_inverse_semantic_resolver
from ..transforms.surface_rules import development_surface_rules


TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION = "tiny-dev-context-survival-plan-v1"
STATEFUL_RANDOM_POLICY = "RANDOM_VALID"
COVERAGE_POLICY = "COVERAGE_GREEDY_KEY_BLIND"
EVEN_SPACING_POLICY = "EVEN_SPACING"
GREEDY_POLICY = "CONTEXT_SURVIVAL_GREEDY"
EXACT_B1_POLICY = "CONTEXT_SURVIVAL_EXACT_B1"
EXACT_B2_POLICY = "CONTEXT_SURVIVAL_EXACT_B2"
BEAM_B4_POLICY = "CONTEXT_SURVIVAL_BEAM_B4"
BEAM_B6_POLICY = "CONTEXT_SURVIVAL_BEAM_B6"
DEFAULT_BUDGETS = (1, 2, 4, 6)
DEFAULT_RANDOM_SEED_COUNT = 8
DEFAULT_BEAM_WIDTH = 32
DEFAULT_SCHEDULE_SEED_BASE = 73000
DEFAULT_MAX_RISK_TIER = 1
SUCCESS = "SUCCESS"
NO_CANDIDATES = "NO_CANDIDATES"
INSUFFICIENT_CANDIDATES = "INSUFFICIENT_NONCONFLICTING_CANDIDATES"


class TinyDevContextSurvivalPlanError(ValueError):
    pass


class _MemoizedExpander:
    def __init__(self, expander: ContextSurvivalExpander) -> None:
        self._expander = expander
        self._cache: dict[str, tuple[Any, ...]] = {}
        self.cache_hit_count = 0
        self.cache_miss_count = 0

    @property
    def detector_access_observed(self) -> bool:
        return self._expander.detector_access_observed

    @property
    def secret_access_observed(self) -> bool:
        return self._expander.secret_access_observed

    def expand(self, state: SearchState):
        cached = self._cache.get(state.search_state_hash)
        if cached is not None:
            self.cache_hit_count += 1
            return cached
        transitions = tuple(self._expander.expand(state))
        self._cache[state.search_state_hash] = transitions
        self.cache_miss_count += 1
        return transitions


def _attack_samples(corpus: Any) -> tuple[Any, ...]:
    values = tuple(
        sorted(
            (
                sample
                for sample in corpus.manifest.samples
                if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
            ),
            key=lambda value: value.sample_id,
        )
    )
    if len(values) != 8:
        raise TinyDevContextSurvivalPlanError("TinyDev context-survival plan requires all eight attack-development samples")
    return values


def _encode_with_offsets(tokenizer: Any, sample: Any) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    text_track = getattr(sample, "text_only_tokens", None)
    if text_track is None:
        raise TinyDevContextSurvivalPlanError(f"sample {sample.sample_id} has no text-only token track")
    encoded = tokenizer(sample.text, add_special_tokens=False, return_offsets_mapping=True)
    ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]
    if ids and isinstance(ids[0], list):
        if len(ids) != 1:
            raise TinyDevContextSurvivalPlanError("unexpected batched tokenizer output")
        ids = ids[0]
        offsets = offsets[0]
    token_ids = tuple(int(value) for value in ids)
    normalized_offsets = tuple((int(start), int(end)) for start, end in offsets)
    if token_ids != tuple(text_track.token_ids):
        raise TinyDevContextSurvivalPlanError(
            f"public tokenizer replay does not match recorded text-only track for {sample.sample_id}"
        )
    if len(token_ids) != len(normalized_offsets):
        raise TinyDevContextSurvivalPlanError("tokenizer IDs and offset mappings have different lengths")
    return token_ids, normalized_offsets


def _context_registry() -> TransformRegistry:
    return TransformRegistry((*context_survival_contraction_rules(), *development_surface_rules()))


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


def _select_result_state(result: SearchResult, budget: int) -> tuple[SearchState | None, str]:
    require_int("budget", budget)
    if budget <= 0:
        raise ValueError("budget must be positive")
    full_depth = tuple(state for state in result.frontier if state.depth == budget)
    if full_depth:
        return min(full_depth, key=_state_rank), SUCCESS
    candidates = tuple(result.frontier or result.states)
    if candidates:
        return min(candidates, key=_state_rank), INSUFFICIENT_CANDIDATES
    return None, NO_CANDIDATES


def _stateful_random(
    expander: ContextSurvivalExpander,
    root: SearchState,
    budget: int,
    seed: int,
) -> tuple[SearchState | None, tuple[str, ...], str, str]:
    require_int("budget", budget)
    require_int("seed", seed)
    if budget <= 0:
        raise ValueError("budget must be positive")
    if seed < 0 or seed >= 1 << 64:
        raise ValueError("seed must be between 0 and 2^64-1")
    state = root
    transition_hashes: list[str] = []
    for depth in range(budget):
        transitions = expander.expand(state)
        if not transitions:
            break
        choice = derive_seed(seed, state.search_state_hash, str(depth), bits=64) % len(transitions)
        transition = transitions[choice]
        transition_hashes.append(transition.transition_hash)
        state = transition.child
    status = SUCCESS if state.depth == budget else (NO_CANDIDATES if state.depth == 0 else INSUFFICIENT_CANDIDATES)
    payload = {
        "algorithm_version": "context-survival-random-valid-v1",
        "root_state_hash": root.search_state_hash,
        "budget": budget,
        "seed": seed,
        "transition_hashes": tuple(transition_hashes),
        "final_state_hash": state.search_state_hash if state is not root else None,
        "status": status,
    }
    return (None if state is root else state), tuple(transition_hashes), sha256_json(payload), status


def _geometry_fields(root: SearchState, state: SearchState | None) -> dict[str, object]:
    root_eligible = root.surviving_root_observations
    if state is None:
        surviving = root_eligible
        newly_masked = 0
        survival_hash = root.survival_report_hash
        current_token_hash = root.current_tokenization_hash
        state_hash = root.search_state_hash
        operation_hashes: tuple[str, ...] = ()
        depth = 0
        visible_cost = 0
        highest_risk_tier = 0
        token_edit_distance = 0
        transformed_text = root.text
        transformed_text_hash = root.text_hash
    else:
        surviving = state.surviving_root_observations
        newly_masked = state.newly_masked_count
        survival_hash = state.survival_report_hash
        current_token_hash = state.current_tokenization_hash
        state_hash = state.search_state_hash
        operation_hashes = state.operation_hashes
        depth = state.depth
        visible_cost = state.visible_cost
        highest_risk_tier = state.highest_risk_tier
        token_edit_distance = state.token_edit_distance
        transformed_text = state.text
        transformed_text_hash = state.text_hash
    destroyed = max(0, root_eligible - surviving)
    ratio = 1.0 if root_eligible == 0 else surviving / root_eligible
    return {
        "root_eligible_observation_count": root_eligible,
        "surviving_root_observation_count": surviving,
        "destroyed_root_observation_count": destroyed,
        "exact_survival_ratio": ratio,
        "exact_destruction_ratio": 1.0 - ratio,
        "newly_masked_count": newly_masked,
        "survival_report_hash": survival_hash,
        "current_tokenization_hash": current_token_hash,
        "search_state_hash": state_hash,
        "operation_hashes": operation_hashes,
        "realized_edit_cost": depth,
        "visible_cost": visible_cost,
        "highest_risk_tier": highest_risk_tier,
        "token_edit_distance": token_edit_distance,
        "transformed_text": transformed_text,
        "transformed_text_hash": transformed_text_hash,
    }


def _state_variant(
    *,
    source: Any,
    root: SearchState,
    policy: str,
    budget: int,
    seed: int,
    state: SearchState | None,
    status: str,
    schedule_result_hash: str,
    candidate_pool_hash: str,
    transition_hashes: Sequence[str] = (),
) -> dict[str, object]:
    geometry = _geometry_fields(root, state)
    payload = {
        "source_sample_id": source.sample_id,
        "source_label": source.label.value,
        "prompt_family_id": source.prompt_family_id,
        "domain": source.domain.value,
        "source_text_hash": source.text_sha256,
        "candidate_pool_hash": candidate_pool_hash,
        "scheduler_input_hash": root.search_state_hash,
        "schedule_policy": policy,
        "schedule_seed": seed,
        "budget": budget,
        "budget_unit": "operation",
        "schedule_result_hash": schedule_result_hash,
        "transition_hashes": tuple(transition_hashes),
        "status": status,
        "hard_invariant_status": "pass",
        **geometry,
    }
    return {**payload, "variant_hash": sha256_json(payload)}


def _baseline_variant(
    *,
    registry: TransformRegistry,
    geometry_engine: CounterfactualGeometryEngine,
    root: Any,
    root_state: SearchState,
    enumeration: Any,
    scheduler_input: KeyBlindScheduleInput,
    candidate_pool_hash: str,
    source: Any,
    policy: SchedulePolicy,
    budget: int,
    seed: int,
) -> dict[str, object]:
    schedule = CandidateScheduler().schedule(scheduler_input, policy, budget, seed)
    applied = registry.apply(enumeration, schedule.selected_candidate_ids, seed=seed)
    realized = schedule.total_cost
    if realized == budget:
        status = SUCCESS
    elif realized == 0:
        status = NO_CANDIDATES
    else:
        status = INSUFFICIENT_CANDIDATES
    counterfactual = geometry_engine.evaluate_output(
        root=root,
        current_text=source.text,
        output_text=applied.output_text,
        candidate_id=sha256_text(f"baseline:{policy.value}:{source.sample_id}:{budget}:{seed}"),
        rule_hash=registry.ruleset_hash,
        visible_cost_class=realized,
        family="baseline-scheduler",
        tier=DEFAULT_MAX_RISK_TIER,
        hard_invariant_status="PASS",
    )
    root_eligible = root_state.surviving_root_observations
    surviving = counterfactual.surviving_count
    destroyed = max(0, root_eligible - surviving)
    survival_ratio = 1.0 if root_eligible == 0 else surviving / root_eligible
    payload = {
        "source_sample_id": source.sample_id,
        "source_label": source.label.value,
        "prompt_family_id": source.prompt_family_id,
        "domain": source.domain.value,
        "source_text_hash": source.text_sha256,
        "candidate_pool_hash": candidate_pool_hash,
        "scheduler_input_hash": scheduler_input.input_artifact_hash,
        "schedule_policy": policy.value,
        "schedule_seed": seed,
        "budget": budget,
        "budget_unit": schedule.budget_unit,
        "schedule_result_hash": schedule.result_hash,
        "transition_hashes": (),
        "status": status,
        "hard_invariant_status": applied.trace.invariant_report.status.value,
        "root_eligible_observation_count": root_eligible,
        "surviving_root_observation_count": surviving,
        "destroyed_root_observation_count": destroyed,
        "exact_survival_ratio": survival_ratio,
        "exact_destruction_ratio": 1.0 - survival_ratio,
        "newly_masked_count": counterfactual.newly_masked_count,
        "survival_report_hash": counterfactual.survival_report.report_hash,
        "current_tokenization_hash": counterfactual.output_token_hash,
        "search_state_hash": None,
        "operation_hashes": tuple(operation.operation_hash for operation in applied.trace.operations),
        "realized_edit_cost": realized,
        "visible_cost": realized,
        "highest_risk_tier": DEFAULT_MAX_RISK_TIER if realized else 0,
        "token_edit_distance": counterfactual.token_edit_distance,
        "scheduler_covered_interval_size": schedule.covered_interval_size,
        "selected_candidate_ids": schedule.selected_candidate_ids,
        "transformed_text": applied.output_text,
        "transformed_text_hash": sha256_text(applied.output_text),
    }
    return {**payload, "variant_hash": sha256_json(payload)}


def build_context_survival_plan(
    corpus: Any,
    tokenizer: Any,
    *,
    ngram_len: int,
    context_history_size: int,
    budgets: Sequence[int] = DEFAULT_BUDGETS,
    random_seed_count: int = DEFAULT_RANDOM_SEED_COUNT,
    beam_width: int = DEFAULT_BEAM_WIDTH,
    max_risk_tier: int = DEFAULT_MAX_RISK_TIER,
    source_code_commit: str = "UNKNOWN",
) -> dict[str, object]:
    require_int("ngram_len", ngram_len)
    require_int("context_history_size", context_history_size)
    require_int("random_seed_count", random_seed_count)
    require_int("beam_width", beam_width)
    require_int("max_risk_tier", max_risk_tier)
    if ngram_len < 2:
        raise ValueError("ngram_len must be at least 2")
    if context_history_size < 0:
        raise ValueError("context_history_size must be non-negative")
    if random_seed_count <= 0:
        raise ValueError("random_seed_count must be positive")
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    if not 0 <= max_risk_tier <= 4:
        raise ValueError("max_risk_tier must be between 0 and 4")
    budget_tuple = tuple(int(value) for value in budgets)
    if not budget_tuple or any(value <= 0 for value in budget_tuple) or len(set(budget_tuple)) != len(budget_tuple):
        raise ValueError("budgets must be unique positive integers")
    if not isinstance(source_code_commit, str) or not source_code_commit:
        raise ValueError("source_code_commit must be non-empty")

    registry = _context_registry()
    repetition = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    config = GeometryConfig.create(
        tokenizer_identity_hash=corpus.model_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=repetition.policy_id,
    )
    sources = _attack_samples(corpus)
    variants: list[dict[str, object]] = []
    source_diagnostics: list[dict[str, object]] = []

    for source_index, source in enumerate(sources):
        token_ids, offsets = _encode_with_offsets(tokenizer, source)
        geometry_engine = CounterfactualGeometryEngine(
            tokenizer=tokenizer,
            config=config,
            eligibility_policy=repetition.eligibility_policy,
        )
        base_expander = ContextSurvivalExpander(
            registry=registry,
            geometry_engine=geometry_engine,
            source_sample_id=source.sample_id,
            source_text=source.text,
            max_risk_tier=max_risk_tier,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        expander = _MemoizedExpander(base_expander)
        root_state = base_expander.root_state
        root = geometry_engine.build_root(source_sample_id=source.sample_id, source_text=source.text)
        if tuple(root.root_tokens) != token_ids:
            raise TinyDevContextSurvivalPlanError(
                f"geometry root tokenization does not match frozen text-only track for {source.sample_id}"
            )
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
        repetition_report = repetition.evaluate(token_ids)
        candidate_pool_hash = sha256_json(
            {
                "ruleset_hash": registry.ruleset_hash,
                "enumeration_hash": enumeration.enumeration_hash,
                "tokenizer_geometry_hash": tokenizer_geometry.geometry_hash,
                "geometry_config_hash": config.config_hash,
                "repetition_policy_hash": repetition.policy_hash,
            }
        )
        root_transitions = expander.expand(root_state)
        source_diagnostic = {
            "sample_id": source.sample_id,
            "label": source.label.value,
            "domain": source.domain.value,
            "candidate_count": len(enumeration.candidates),
            "stateful_root_transition_count": len(root_transitions),
            "enumeration_hash": enumeration.enumeration_hash,
            "tokenizer_geometry_hash": tokenizer_geometry.geometry_hash,
            "scheduler_input_hash": scheduler_input.input_artifact_hash,
            "candidate_pool_hash": candidate_pool_hash,
            "root_state_hash": root_state.search_state_hash,
            "root_eligible_observation_count": root_state.surviving_root_observations,
            "root_repeated_context_count": repetition_report.repeated_count,
            "root_repetition_report_hash": repetition_report.report_hash,
        }

        for budget_index, budget in enumerate(budget_tuple):
            deterministic_seed = DEFAULT_SCHEDULE_SEED_BASE + source_index * 1000 + budget_index * 100
            for replicate in range(random_seed_count):
                seed = deterministic_seed + replicate + 1
                state, transitions, result_hash, status = _stateful_random(expander, root_state, budget, seed)
                variants.append(
                    _state_variant(
                        source=source,
                        root=root_state,
                        policy=STATEFUL_RANDOM_POLICY,
                        budget=budget,
                        seed=seed,
                        state=state,
                        status=status,
                        schedule_result_hash=result_hash,
                        candidate_pool_hash=candidate_pool_hash,
                        transition_hashes=transitions,
                    )
                )

            for baseline_policy in (SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND, SchedulePolicy.EVEN_SPACING):
                variants.append(
                    _baseline_variant(
                        registry=registry,
                        geometry_engine=geometry_engine,
                        root=root,
                        root_state=root_state,
                        enumeration=enumeration,
                        scheduler_input=scheduler_input,
                        candidate_pool_hash=candidate_pool_hash,
                        source=source,
                        policy=baseline_policy,
                        budget=budget,
                        seed=deterministic_seed,
                    )
                )

            greedy = greedy_search(expander, root_state, budget)
            greedy_state, greedy_status = _select_result_state(greedy, budget)
            variants.append(
                _state_variant(
                    source=source,
                    root=root_state,
                    policy=GREEDY_POLICY,
                    budget=budget,
                    seed=deterministic_seed,
                    state=greedy_state,
                    status=greedy_status,
                    schedule_result_hash=greedy.result_hash,
                    candidate_pool_hash=candidate_pool_hash,
                )
            )

            if budget == 1:
                exact = exact_b1(expander, root_state)
                exact_state, exact_status = _select_result_state(exact, budget)
                variants.append(
                    _state_variant(
                        source=source,
                        root=root_state,
                        policy=EXACT_B1_POLICY,
                        budget=budget,
                        seed=deterministic_seed,
                        state=exact_state,
                        status=exact_status,
                        schedule_result_hash=exact.result_hash,
                        candidate_pool_hash=candidate_pool_hash,
                    )
                )
            if budget == 2:
                exact = exact_b2(expander, root_state)
                exact_state, exact_status = _select_result_state(exact, budget)
                variants.append(
                    _state_variant(
                        source=source,
                        root=root_state,
                        policy=EXACT_B2_POLICY,
                        budget=budget,
                        seed=deterministic_seed,
                        state=exact_state,
                        status=exact_status,
                        schedule_result_hash=exact.result_hash,
                        candidate_pool_hash=candidate_pool_hash,
                    )
                )
            if budget in (4, 6):
                beam = beam_search(expander, root_state, budget, beam_width)
                beam_state, beam_status = _select_result_state(beam, budget)
                variants.append(
                    _state_variant(
                        source=source,
                        root=root_state,
                        policy=BEAM_B4_POLICY if budget == 4 else BEAM_B6_POLICY,
                        budget=budget,
                        seed=deterministic_seed,
                        state=beam_state,
                        status=beam_status,
                        schedule_result_hash=beam.result_hash,
                        candidate_pool_hash=candidate_pool_hash,
                    )
                )

        source_diagnostic["expansion_cache_hit_count"] = expander.cache_hit_count
        source_diagnostic["expansion_cache_miss_count"] = expander.cache_miss_count
        source_diagnostic["geometry_cache_hit_count"] = geometry_engine.cache_hit_count
        source_diagnostics.append(source_diagnostic)

    payload = {
        "algorithm_version": TINY_DEV_CONTEXT_SURVIVAL_PLAN_VERSION,
        "scientific_scope": "DEV_KEYS TinyDev detector-blind context-survival mechanism plan; engineering pilot only",
        "source_code_commit": source_code_commit,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "tokenizer_identity_hash": corpus.model_identity_hash,
        "ruleset_hash": registry.ruleset_hash,
        "geometry_config_hash": config.config_hash,
        "public_repetition_policy_hash": repetition.policy_hash,
        "public_repetition_policy_id": repetition.policy_id,
        "ngram_len": ngram_len,
        "context_history_size": context_history_size,
        "max_risk_tier": max_risk_tier,
        "budgets": budget_tuple,
        "random_seed_count": random_seed_count,
        "beam_width": beam_width,
        "schedule_seed_base": DEFAULT_SCHEDULE_SEED_BASE,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "source_diagnostics": tuple(source_diagnostics),
        "variants": tuple(variants),
    }
    return {**payload, "plan_hash": sha256_json(payload)}