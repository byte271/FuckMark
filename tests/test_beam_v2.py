from __future__ import annotations

from dataclasses import dataclass

from fuckmark.hashing import sha256_text
from fuckmark.scheduling.beam_v2 import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION, beam_search_v2
from fuckmark.scheduling.state_search import SearchState, SearchTransition


def _hash(value: str) -> str:
    return sha256_text(value)


def _root() -> SearchState:
    return SearchState.create(
        root_source_hash=_hash("root-source"),
        text="root",
        depth=0,
        operation_hashes=(),
        ancestor_text_hashes=(),
        root_tokenization_hash=_hash("root-tokens"),
        current_tokenization_hash=_hash("root-current"),
        survival_report_hash=_hash("root-survival"),
        enumeration_hash=_hash("root-enumeration"),
        hard_invariant_report_hash=_hash("root-invariant"),
        surviving_root_observations=10,
        newly_masked_count=0,
        highest_risk_tier=0,
        visible_cost=0,
        token_edit_distance=0,
    )


def _child(
    root: SearchState,
    *,
    text: str,
    operation_hash: str,
    token_distance: int,
) -> SearchTransition:
    child = SearchState.create(
        root_source_hash=root.root_source_hash,
        text=text,
        depth=1,
        operation_hashes=(operation_hash,),
        ancestor_text_hashes=(root.text_hash,),
        root_tokenization_hash=root.root_tokenization_hash,
        current_tokenization_hash=_hash("tokens:" + text),
        survival_report_hash=_hash("survival:" + text),
        enumeration_hash=_hash("enumeration:" + text),
        hard_invariant_report_hash=_hash("invariant:" + text),
        surviving_root_observations=7,
        newly_masked_count=2,
        highest_risk_tier=1,
        visible_cost=1,
        token_edit_distance=token_distance,
    )
    return SearchTransition.create(
        parent=root,
        candidate_hash=_hash("candidate:" + text),
        operation_hash=operation_hash,
        visible_cost_delta=1,
        child=child,
    )


@dataclass
class _Expander:
    transitions: tuple[SearchTransition, ...]

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def secret_access_observed(self) -> bool:
        return False

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        return self.transitions if state.depth == 0 else ()


def test_beam_v2_uses_canonical_operation_order_before_token_distance() -> None:
    root = _root()
    op_a = _hash("operation-a")
    op_b = _hash("operation-b")
    canonical_text, canonical_op, other_text, other_op = (
        ("a", op_a, "b", op_b) if op_a < op_b else ("b", op_b, "a", op_a)
    )
    canonical = _child(root, text=canonical_text, operation_hash=canonical_op, token_distance=9)
    other = _child(root, text=other_text, operation_hash=other_op, token_distance=1)
    result = beam_search_v2(_Expander((other, canonical)), root, budget=1, beam_width=1)
    assert result.algorithm_version == CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
    assert tuple(state.text for state in result.states) == (canonical_text,)


def test_beam_v2_is_independent_of_enumeration_order() -> None:
    root = _root()
    first = _child(root, text="a", operation_hash=_hash("operation-a"), token_distance=4)
    second = _child(root, text="b", operation_hash=_hash("operation-b"), token_distance=2)
    forward = beam_search_v2(_Expander((first, second)), root, budget=1, beam_width=1)
    reverse = beam_search_v2(_Expander((second, first)), root, budget=1, beam_width=1)
    assert forward.result_hash == reverse.result_hash
    assert forward.states == reverse.states
