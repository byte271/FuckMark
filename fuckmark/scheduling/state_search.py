from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text


CONTEXT_SURVIVAL_EXACT_ALGORITHM_VERSION = "context-survival-exact-v1"
CONTEXT_SURVIVAL_GREEDY_ALGORITHM_VERSION = "context-survival-greedy-v1"
CONTEXT_SURVIVAL_BEAM_ALGORITHM_VERSION = "context-survival-beam-v1"
SEARCH_STATE_ALGORITHM_VERSION = "context-survival-search-state-v1"
SEARCH_TRANSITION_ALGORITHM_VERSION = "context-survival-transition-v1"


@dataclass(frozen=True, slots=True)
class SearchState:
    root_source_hash: str
    text: str
    text_hash: str
    depth: int
    operation_hashes: tuple[str, ...]
    ancestor_text_hashes: tuple[str, ...]
    inverse_semantic_history: tuple[tuple[str, str, str], ...]
    root_tokenization_hash: str
    current_tokenization_hash: str
    survival_report_hash: str
    enumeration_hash: str
    hard_invariant_report_hash: str
    surviving_root_observations: int
    newly_masked_count: int
    highest_risk_tier: int
    visible_cost: int
    token_edit_distance: int
    search_state_hash: str

    def __post_init__(self) -> None:
        for name in (
            "root_source_hash",
            "text_hash",
            "root_tokenization_hash",
            "current_tokenization_hash",
            "survival_report_hash",
            "enumeration_hash",
            "hard_invariant_report_hash",
            "search_state_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if self.text_hash != sha256_text(self.text):
            raise ValueError("text_hash does not match text")
        for name in (
            "depth",
            "surviving_root_observations",
            "newly_masked_count",
            "highest_risk_tier",
            "visible_cost",
            "token_edit_distance",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.operation_hashes, tuple):
            raise TypeError("operation_hashes must be a tuple")
        if len(self.operation_hashes) != self.depth:
            raise ValueError("operation_hashes length must equal depth")
        for value in self.operation_hashes:
            require_sha256("operation_hash", value)
        if not isinstance(self.ancestor_text_hashes, tuple):
            raise TypeError("ancestor_text_hashes must be a tuple")
        if len(self.ancestor_text_hashes) != self.depth:
            raise ValueError("ancestor_text_hashes length must equal depth")
        if len(set(self.ancestor_text_hashes)) != len(self.ancestor_text_hashes):
            raise ValueError("ancestor_text_hashes must not contain cycles")
        for value in self.ancestor_text_hashes:
            require_sha256("ancestor_text_hash", value)
        if self.text_hash in self.ancestor_text_hashes:
            raise ValueError("current text hash cannot appear in its ancestry")
        if not isinstance(self.inverse_semantic_history, tuple):
            raise TypeError("inverse_semantic_history must be a tuple")
        if len(self.inverse_semantic_history) > self.depth:
            raise ValueError("inverse_semantic_history cannot exceed depth")
        for value in self.inverse_semantic_history:
            if not isinstance(value, tuple) or len(value) != 3:
                raise TypeError("inverse semantic history entries must be three-item tuples")
            for item in value:
                require_clean_string("inverse semantic history value", item)
        if self.search_state_hash != sha256_json(self.payload()):
            raise ValueError("search_state_hash does not match SearchState payload")

    @classmethod
    def create(
        cls,
        *,
        root_source_hash: str,
        text: str,
        depth: int,
        operation_hashes: Sequence[str],
        ancestor_text_hashes: Sequence[str],
        inverse_semantic_history: Sequence[tuple[str, str, str]] = (),
        root_tokenization_hash: str,
        current_tokenization_hash: str,
        survival_report_hash: str,
        enumeration_hash: str,
        hard_invariant_report_hash: str,
        surviving_root_observations: int,
        newly_masked_count: int,
        highest_risk_tier: int,
        visible_cost: int,
        token_edit_distance: int,
    ) -> SearchState:
        text_hash = sha256_text(text)
        operations = tuple(operation_hashes)
        ancestors = tuple(ancestor_text_hashes)
        inverse_history = tuple(inverse_semantic_history)
        payload = {
            "algorithm_version": SEARCH_STATE_ALGORITHM_VERSION,
            "root_source_hash": root_source_hash,
            "text_hash": text_hash,
            "depth": depth,
            "operation_hashes": operations,
            "ancestor_text_hashes": ancestors,
            "inverse_semantic_history": inverse_history,
            "root_tokenization_hash": root_tokenization_hash,
            "current_tokenization_hash": current_tokenization_hash,
            "survival_report_hash": survival_report_hash,
            "enumeration_hash": enumeration_hash,
            "hard_invariant_report_hash": hard_invariant_report_hash,
            "surviving_root_observations": surviving_root_observations,
            "newly_masked_count": newly_masked_count,
            "highest_risk_tier": highest_risk_tier,
            "visible_cost": visible_cost,
            "token_edit_distance": token_edit_distance,
        }
        return cls(
            root_source_hash=root_source_hash,
            text=text,
            text_hash=text_hash,
            depth=depth,
            operation_hashes=operations,
            ancestor_text_hashes=ancestors,
            inverse_semantic_history=inverse_history,
            root_tokenization_hash=root_tokenization_hash,
            current_tokenization_hash=current_tokenization_hash,
            survival_report_hash=survival_report_hash,
            enumeration_hash=enumeration_hash,
            hard_invariant_report_hash=hard_invariant_report_hash,
            surviving_root_observations=surviving_root_observations,
            newly_masked_count=newly_masked_count,
            highest_risk_tier=highest_risk_tier,
            visible_cost=visible_cost,
            token_edit_distance=token_edit_distance,
            search_state_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SEARCH_STATE_ALGORITHM_VERSION,
            "root_source_hash": self.root_source_hash,
            "text_hash": self.text_hash,
            "depth": self.depth,
            "operation_hashes": self.operation_hashes,
            "ancestor_text_hashes": self.ancestor_text_hashes,
            "inverse_semantic_history": self.inverse_semantic_history,
            "root_tokenization_hash": self.root_tokenization_hash,
            "current_tokenization_hash": self.current_tokenization_hash,
            "survival_report_hash": self.survival_report_hash,
            "enumeration_hash": self.enumeration_hash,
            "hard_invariant_report_hash": self.hard_invariant_report_hash,
            "surviving_root_observations": self.surviving_root_observations,
            "newly_masked_count": self.newly_masked_count,
            "highest_risk_tier": self.highest_risk_tier,
            "visible_cost": self.visible_cost,
            "token_edit_distance": self.token_edit_distance,
        }


@dataclass(frozen=True, slots=True)
class SearchTransition:
    parent_state_hash: str
    candidate_hash: str
    operation_hash: str
    marginal_root_observation_destruction: int
    visible_cost_delta: int
    child: SearchState
    transition_hash: str

    def __post_init__(self) -> None:
        for name in ("parent_state_hash", "candidate_hash", "operation_hash", "transition_hash"):
            require_sha256(name, getattr(self, name))
        for name in ("marginal_root_observation_destruction", "visible_cost_delta"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.child, SearchState):
            raise TypeError("child must be a SearchState")
        if self.transition_hash != sha256_json(self.payload()):
            raise ValueError("transition_hash does not match SearchTransition payload")

    @classmethod
    def create(
        cls,
        *,
        parent: SearchState,
        candidate_hash: str,
        operation_hash: str,
        visible_cost_delta: int,
        child: SearchState,
    ) -> SearchTransition:
        require_sha256("candidate_hash", candidate_hash)
        require_sha256("operation_hash", operation_hash)
        require_int("visible_cost_delta", visible_cost_delta)
        if child.depth != parent.depth + 1:
            raise ValueError("child depth must be parent depth plus one")
        if child.root_source_hash != parent.root_source_hash:
            raise ValueError("child root source must match parent root source")
        if child.ancestor_text_hashes != (*parent.ancestor_text_hashes, parent.text_hash):
            raise ValueError("child ancestry must append the parent text hash")
        if child.operation_hashes != (*parent.operation_hashes, operation_hash):
            raise ValueError("child operation history must append the transition operation")
        if child.inverse_semantic_history != parent.inverse_semantic_history and (
            len(child.inverse_semantic_history) != len(parent.inverse_semantic_history) + 1
            or child.inverse_semantic_history[:-1] != parent.inverse_semantic_history
        ):
            raise ValueError("child inverse semantic history must preserve or append parent history")
        marginal = max(0, parent.surviving_root_observations - child.surviving_root_observations)
        payload = {
            "algorithm_version": SEARCH_TRANSITION_ALGORITHM_VERSION,
            "parent_state_hash": parent.search_state_hash,
            "candidate_hash": candidate_hash,
            "operation_hash": operation_hash,
            "marginal_root_observation_destruction": marginal,
            "visible_cost_delta": visible_cost_delta,
            "child_state_hash": child.search_state_hash,
        }
        return cls(
            parent_state_hash=parent.search_state_hash,
            candidate_hash=candidate_hash,
            operation_hash=operation_hash,
            marginal_root_observation_destruction=marginal,
            visible_cost_delta=visible_cost_delta,
            child=child,
            transition_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": SEARCH_TRANSITION_ALGORITHM_VERSION,
            "parent_state_hash": self.parent_state_hash,
            "candidate_hash": self.candidate_hash,
            "operation_hash": self.operation_hash,
            "marginal_root_observation_destruction": self.marginal_root_observation_destruction,
            "visible_cost_delta": self.visible_cost_delta,
            "child_state_hash": self.child.search_state_hash,
        }


class StateExpander(Protocol):
    @property
    def detector_access_observed(self) -> bool: ...

    @property
    def secret_access_observed(self) -> bool: ...

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]: ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    algorithm_version: str
    root_state_hash: str
    budget: int
    states: tuple[SearchState, ...]
    frontier: tuple[SearchState, ...]
    expanded_state_count: int
    pruned_state_count: int
    detector_access_observed: bool
    secret_access_observed: bool
    result_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_sha256("root_state_hash", self.root_state_hash)
        for name in ("budget", "expanded_state_count", "pruned_state_count"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if not isinstance(self.states, tuple) or any(not isinstance(value, SearchState) for value in self.states):
            raise TypeError("states must be a tuple of SearchState values")
        if not isinstance(self.frontier, tuple) or any(not isinstance(value, SearchState) for value in self.frontier):
            raise TypeError("frontier must be a tuple of SearchState values")
        if len({value.text_hash for value in self.states}) != len(self.states):
            raise ValueError("states must be deduplicated by final text hash")
        if any(value.text_hash not in {state.text_hash for state in self.states} for value in self.frontier):
            raise ValueError("frontier must be a subset of states")
        if not isinstance(self.detector_access_observed, bool):
            raise TypeError("detector_access_observed must be a boolean")
        if self.detector_access_observed:
            raise ValueError("detector access contaminates structural search")
        if not isinstance(self.secret_access_observed, bool):
            raise TypeError("secret_access_observed must be a boolean")
        if self.secret_access_observed:
            raise ValueError("secret access contaminates structural search")
        require_sha256("result_hash", self.result_hash)
        if self.result_hash != sha256_json(self.payload()):
            raise ValueError("result_hash does not match SearchResult payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "root_state_hash": self.root_state_hash,
            "budget": self.budget,
            "state_hashes": tuple(value.search_state_hash for value in self.states),
            "frontier_hashes": tuple(value.search_state_hash for value in self.frontier),
            "expanded_state_count": self.expanded_state_count,
            "pruned_state_count": self.pruned_state_count,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


def _state_rank(state: SearchState) -> tuple[object, ...]:
    return (
        state.surviving_root_observations,
        -state.newly_masked_count,
        state.highest_risk_tier,
        state.visible_cost,
        state.token_edit_distance,
        state.search_state_hash,
    )


def _transition_rank(transition: SearchTransition) -> tuple[object, ...]:
    return (
        -transition.marginal_root_observation_destruction,
        transition.child.highest_risk_tier,
        transition.visible_cost_delta,
        transition.child.token_edit_distance,
        -transition.child.newly_masked_count,
        transition.candidate_hash,
    )


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


def pareto_frontier(states: Sequence[SearchState]) -> tuple[SearchState, ...]:
    materialized = _deduplicate_states(states)
    output = tuple(
        state
        for state in materialized
        if not any(other.search_state_hash != state.search_state_hash and _dominates(other, state) for other in materialized)
    )
    return tuple(sorted(output, key=_state_rank))


def _deduplicate_states(states: Sequence[SearchState]) -> tuple[SearchState, ...]:
    by_text_hash: dict[str, SearchState] = {}
    for state in states:
        if not isinstance(state, SearchState):
            raise TypeError("states must contain SearchState values")
        existing = by_text_hash.get(state.text_hash)
        if existing is None or _state_rank(state) < _state_rank(existing):
            by_text_hash[state.text_hash] = state
    return tuple(sorted(by_text_hash.values(), key=_state_rank))


def _result(
    *,
    algorithm_version: str,
    root: SearchState,
    budget: int,
    states: Sequence[SearchState],
    expanded_state_count: int,
    pruned_state_count: int,
    detector_access_observed: bool,
    secret_access_observed: bool,
) -> SearchResult:
    materialized = _deduplicate_states(states)
    frontier = pareto_frontier(materialized)
    payload = {
        "algorithm_version": algorithm_version,
        "root_state_hash": root.search_state_hash,
        "budget": budget,
        "state_hashes": tuple(value.search_state_hash for value in materialized),
        "frontier_hashes": tuple(value.search_state_hash for value in frontier),
        "expanded_state_count": expanded_state_count,
        "pruned_state_count": pruned_state_count,
        "detector_access_observed": detector_access_observed,
        "secret_access_observed": secret_access_observed,
    }
    return SearchResult(
        algorithm_version=algorithm_version,
        root_state_hash=root.search_state_hash,
        budget=budget,
        states=materialized,
        frontier=frontier,
        expanded_state_count=expanded_state_count,
        pruned_state_count=pruned_state_count,
        detector_access_observed=detector_access_observed,
        secret_access_observed=secret_access_observed,
        result_hash=sha256_json(payload),
    )


def exact_b1(expander: StateExpander, root: SearchState) -> SearchResult:
    transitions = expander.expand(root)
    return _result(
        algorithm_version=CONTEXT_SURVIVAL_EXACT_ALGORITHM_VERSION,
        root=root,
        budget=1,
        states=tuple(value.child for value in transitions),
        expanded_state_count=1,
        pruned_state_count=0,
        detector_access_observed=expander.detector_access_observed,
        secret_access_observed=expander.secret_access_observed,
    )


def exact_b2(expander: StateExpander, root: SearchState) -> SearchResult:
    first = expander.expand(root)
    second_states: list[SearchState] = []
    for transition in first:
        second_states.extend(value.child for value in expander.expand(transition.child))
    return _result(
        algorithm_version=CONTEXT_SURVIVAL_EXACT_ALGORITHM_VERSION,
        root=root,
        budget=2,
        states=second_states,
        expanded_state_count=1 + len(first),
        pruned_state_count=0,
        detector_access_observed=expander.detector_access_observed,
        secret_access_observed=expander.secret_access_observed,
    )


def greedy_search(expander: StateExpander, root: SearchState, budget: int) -> SearchResult:
    require_int("budget", budget)
    if budget < 0:
        raise ValueError("budget must be non-negative")
    state = root
    expanded = 0
    for _ in range(budget):
        transitions = expander.expand(state)
        expanded += 1
        if not transitions:
            break
        state = min(transitions, key=_transition_rank).child
    states = () if state is root else (state,)
    return _result(
        algorithm_version=CONTEXT_SURVIVAL_GREEDY_ALGORITHM_VERSION,
        root=root,
        budget=budget,
        states=states,
        expanded_state_count=expanded,
        pruned_state_count=0,
        detector_access_observed=expander.detector_access_observed,
        secret_access_observed=expander.secret_access_observed,
    )


def beam_search(expander: StateExpander, root: SearchState, budget: int, beam_width: int) -> SearchResult:
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
        unique = _deduplicate_states(children)
        if not unique:
            beam = ()
            break
        ranked = tuple(sorted(unique, key=_state_rank))
        pruned += max(0, len(ranked) - beam_width)
        beam = ranked[:beam_width]
    return _result(
        algorithm_version=CONTEXT_SURVIVAL_BEAM_ALGORITHM_VERSION,
        root=root,
        budget=budget,
        states=beam,
        expanded_state_count=expanded,
        pruned_state_count=pruned,
        detector_access_observed=expander.detector_access_observed,
        secret_access_observed=expander.secret_access_observed,
    )
