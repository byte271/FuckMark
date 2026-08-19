import pytest

from fuckmark.hashing import sha256_text
from fuckmark.scheduling.state_search import SearchState, SearchTransition
from fuckmark.search.visible_cost_budget import (
    RELAXED_VISIBLE_COST_POLICY,
    STRICT_VISIBLE_COST_POLICY,
    VisibleCostTier,
    assess_visible_cost,
    visible_cost_beam_search,
)


def _chain(root_text: str, depth: int):
    root_source_hash = sha256_text(root_text)
    states = []
    texts = [root_text + ("x" * index) for index in range(depth + 1)]
    for index, text in enumerate(texts):
        operations = tuple(sha256_text(f"op-{step}") for step in range(1, index + 1))
        ancestors = tuple(sha256_text(value) for value in texts[:index])
        states.append(
            SearchState.create(
                root_source_hash=root_source_hash,
                text=text,
                depth=index,
                operation_hashes=operations,
                ancestor_text_hashes=ancestors,
                root_tokenization_hash=sha256_text("root-tokens"),
                current_tokenization_hash=sha256_text(f"tokens-{text}"),
                survival_report_hash=sha256_text(f"survival-{text}"),
                enumeration_hash=sha256_text(f"enumeration-{text}"),
                hard_invariant_report_hash=sha256_text(f"hard-{text}"),
                surviving_root_observations=100 - index,
                newly_masked_count=0,
                highest_risk_tier=0,
                visible_cost=index,
                token_edit_distance=index,
            )
        )
    transitions = {}
    for index in range(depth):
        child = states[index + 1]
        transition = SearchTransition.create(
            parent=states[index],
            candidate_hash=sha256_text(f"candidate-{index + 1}"),
            operation_hash=child.operation_hashes[-1],
            visible_cost_delta=1,
            child=child,
        )
        transitions[states[index].search_state_hash] = (transition,)
    return states, transitions


class LinearExpander:
    def __init__(self, transitions, *, detector=False, secret=False):
        self._transitions = transitions
        self._detector = detector
        self._secret = secret

    @property
    def detector_access_observed(self):
        return self._detector

    @property
    def secret_access_observed(self):
        return self._secret

    def expand(self, state):
        return self._transitions.get(state.search_state_hash, ())


def test_strict_and_relaxed_stop_at_length_normalized_cost_frontiers():
    root_text = "alpha " * 50
    states, transitions = _chain(root_text, 12)
    expander = LinearExpander(transitions)
    strict = visible_cost_beam_search(
        expander,
        states[0],
        root_text=root_text,
        tier=VisibleCostTier.STRICT,
        beam_width=4,
        maximum_search_operations=12,
    )
    relaxed = visible_cost_beam_search(
        expander,
        states[0],
        root_text=root_text,
        tier=VisibleCostTier.RELAXED,
        beam_width=4,
        maximum_search_operations=12,
    )
    assert strict.reached_depth == 4
    assert relaxed.reached_depth == 9
    assert assess_visible_cost(root_text, strict.states[0], STRICT_VISIBLE_COST_POLICY).eligible
    assert assess_visible_cost(root_text, relaxed.states[0], RELAXED_VISIBLE_COST_POLICY).eligible
    assert not assess_visible_cost(root_text, states[5], STRICT_VISIBLE_COST_POLICY).eligible
    assert not assess_visible_cost(root_text, states[10], RELAXED_VISIBLE_COST_POLICY).eligible


def test_visible_cost_search_preserves_root_when_no_edit_is_eligible():
    root_text = "short text"
    states, transitions = _chain(root_text, 2)
    result = visible_cost_beam_search(
        LinearExpander(transitions),
        states[0],
        root_text=root_text,
        tier=VisibleCostTier.STRICT,
        maximum_search_operations=4,
    )
    assert result.reached_depth == 0
    assert result.states == (states[0],)
    assert result.rejected_transition_count == 1


def test_visible_cost_search_fails_closed_on_selection_access():
    root_text = "alpha " * 50
    states, transitions = _chain(root_text, 2)
    with pytest.raises(ValueError, match="prohibited selection access"):
        visible_cost_beam_search(
            LinearExpander(transitions, detector=True),
            states[0],
            root_text=root_text,
            tier=VisibleCostTier.STRICT,
        )


def test_policy_hashes_and_tiers_are_distinct():
    assert STRICT_VISIBLE_COST_POLICY.policy_hash != RELAXED_VISIBLE_COST_POLICY.policy_hash
    assert STRICT_VISIBLE_COST_POLICY.tier is VisibleCostTier.STRICT
    assert RELAXED_VISIBLE_COST_POLICY.tier is VisibleCostTier.RELAXED
