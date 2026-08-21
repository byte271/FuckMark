from __future__ import annotations

from collections.abc import Sequence

from .._validation import require_int
from ..hashing import sha256_json
from .algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from .state_search import SearchResult, SearchState, StateExpander


def _beam_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.surviving_root_observations,
        -state.newly_masked_count,
        state.highest_risk_tier,
        state.visible_cost,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _duplicate_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.highest_risk_tier,
        state.visible_cost,
        state.depth,
        state.operation_hashes,
        state.text_hash,
    )


def _deduplicate(states: Sequence[SearchState]) -> tuple[SearchState, ...]:
    by_text_hash: dict[str, SearchState] = {}
    for state in states:
        if not isinstance(state, SearchState):
            raise TypeError("states must contain SearchState values")
        existing = by_text_hash.get(state.text_hash)
        if existing is None or _duplicate_rank(state) < _duplicate_rank(existing):
            by_text_hash[state.text_hash] = state
    return tuple(sorted(by_text_hash.values(), key=_beam_rank))


def _branch_key(state: SearchState) -> str:
    if state.operation_hashes:
        return state.operation_hashes[0]
    return state.text_hash


def _prune_diverse(states: Sequence[SearchState], beam_width: int) -> tuple[SearchState, ...]:
    ranked = tuple(sorted(_deduplicate(states), key=_beam_rank))
    if len(ranked) <= beam_width:
        return ranked
    elite_count = max(1, beam_width // 2)
    selected = list(ranked[:elite_count])
    selected_hashes = {state.search_state_hash for state in selected}
    branch_keys = {_branch_key(state) for state in selected}
    for state in ranked[elite_count:]:
        if len(selected) >= beam_width:
            break
        branch_key = _branch_key(state)
        if branch_key in branch_keys:
            continue
        selected.append(state)
        selected_hashes.add(state.search_state_hash)
        branch_keys.add(branch_key)
    if len(selected) < beam_width:
        for state in ranked:
            if len(selected) >= beam_width:
                break
            if state.search_state_hash in selected_hashes:
                continue
            selected.append(state)
            selected_hashes.add(state.search_state_hash)
    return tuple(sorted(selected, key=_beam_rank))


def _dominates(left: SearchState, right: SearchState) -> bool:
    left_values = (
        left.surviving_root_observations,
        -left.newly_masked_count,
        left.depth,
        left.visible_cost,
        left.highest_risk_tier,
        left.token_edit_distance,
    )
    right_values = (
        right.surviving_root_observations,
        -right.newly_masked_count,
        right.depth,
        right.visible_cost,
        right.highest_risk_tier,
        right.token_edit_distance,
    )
    return all(a <= b for a, b in zip(left_values, right_values)) and any(
        a < b for a, b in zip(left_values, right_values)
    )


def _frontier(states: Sequence[SearchState]) -> tuple[SearchState, ...]:
    materialized = _deduplicate(states)
    output = tuple(
        state
        for state in materialized
        if not any(
            other.search_state_hash != state.search_state_hash and _dominates(other, state)
            for other in materialized
        )
    )
    return tuple(sorted(output, key=_beam_rank))


def beam_search_v2(
    expander: StateExpander,
    root: SearchState,
    budget: int,
    beam_width: int,
) -> SearchResult:
    require_int("budget", budget)
    require_int("beam_width", beam_width)
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if beam_width <= 0:
        raise ValueError("beam_width must be positive")
    beam = (root,)
    expanded = 0
    pruned = 0
    for _ in range(budget):
        children: list[SearchState] = []
        for state in beam:
            children.extend(value.child for value in expander.expand(state))
            expanded += 1
        unique = _deduplicate(children)
        if not unique:
            beam = ()
            break
        pruned += max(0, len(unique) - beam_width)
        beam = _prune_diverse(unique, beam_width)
    states = _deduplicate(beam)
    frontier = _frontier(states)
    payload = {
        "algorithm_version": CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        "root_state_hash": root.search_state_hash,
        "budget": budget,
        "state_hashes": tuple(value.search_state_hash for value in states),
        "frontier_hashes": tuple(value.search_state_hash for value in frontier),
        "expanded_state_count": expanded,
        "pruned_state_count": pruned,
        "detector_access_observed": expander.detector_access_observed,
        "secret_access_observed": expander.secret_access_observed,
    }
    return SearchResult(
        algorithm_version=CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION,
        root_state_hash=root.search_state_hash,
        budget=budget,
        states=states,
        frontier=frontier,
        expanded_state_count=expanded,
        pruned_state_count=pruned,
        detector_access_observed=expander.detector_access_observed,
        secret_access_observed=expander.secret_access_observed,
        result_hash=sha256_json(payload),
    )
