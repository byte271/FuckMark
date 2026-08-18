from __future__ import annotations

from dataclasses import dataclass

import pytest

from fuckmark.hashing import sha256_text
from fuckmark.scheduling.state_search import (
    SearchState,
    SearchTransition,
    beam_search,
    exact_b1,
    exact_b2,
    greedy_search,
    pareto_frontier,
)


def _hash(value: str) -> str:
    return sha256_text(value)


def _state(
    text: str,
    *,
    depth: int = 0,
    operations: tuple[str, ...] = (),
    ancestors: tuple[str, ...] = (),
    surviving: int = 10,
    masked: int = 0,
    risk: int = 0,
    cost: int = 0,
    token_distance: int = 0,
) -> SearchState:
    return SearchState.create(
        root_source_hash=_hash("root-source"),
        text=text,
        depth=depth,
        operation_hashes=operations,
        ancestor_text_hashes=ancestors,
        root_tokenization_hash=_hash("root-tokens"),
        current_tokenization_hash=_hash("tokens:" + text),
        survival_report_hash=_hash(f"survival:{text}:{surviving}:{masked}"),
        enumeration_hash=_hash("enumeration:" + text),
        hard_invariant_report_hash=_hash("invariant:" + text),
        surviving_root_observations=surviving,
        newly_masked_count=masked,
        highest_risk_tier=risk,
        visible_cost=cost,
        token_edit_distance=token_distance,
    )


def _child(parent: SearchState, name: str, *, surviving: int, masked: int = 0, risk: int = 0, cost_delta: int = 1, token_distance: int = 1) -> SearchTransition:
    operation_hash = _hash("operation:" + parent.text + ":" + name)
    child = _state(
        name,
        depth=parent.depth + 1,
        operations=(*parent.operation_hashes, operation_hash),
        ancestors=(*parent.ancestor_text_hashes, parent.text_hash),
        surviving=surviving,
        masked=masked,
        risk=max(parent.highest_risk_tier, risk),
        cost=parent.visible_cost + cost_delta,
        token_distance=token_distance,
    )
    return SearchTransition.create(
        parent=parent,
        candidate_hash=_hash("candidate:" + parent.text + ":" + name),
        operation_hash=operation_hash,
        visible_cost_delta=cost_delta,
        child=child,
    )


@dataclass
class GraphExpander:
    graph: dict[str, tuple[dict[str, int | str], ...]]
    reverse: bool = False

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def secret_access_observed(self) -> bool:
        return False

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        rows = self.graph.get(state.text, ())
        values = tuple(
            _child(
                state,
                str(row["text"]),
                surviving=int(row["surviving"]),
                masked=int(row.get("masked", 0)),
                risk=int(row.get("risk", 0)),
                cost_delta=int(row.get("cost", 1)),
                token_distance=int(row.get("token_distance", 1)),
            )
            for row in rows
        )
        return tuple(reversed(values)) if self.reverse else values


def test_exact_b1_evaluates_every_single_edit_and_returns_frontier() -> None:
    root = _state("root")
    expander = GraphExpander(
        {
            "root": (
                {"text": "a", "surviving": 7, "cost": 1},
                {"text": "b", "surviving": 8, "cost": 2},
                {"text": "c", "surviving": 7, "cost": 3, "masked": 2},
            )
        }
    )
    result = exact_b1(expander, root)
    assert {state.text for state in result.states} == {"a", "b", "c"}
    assert {state.text for state in result.frontier} == {"a", "c"}
    assert result.expanded_state_count == 1
    assert result.detector_access_observed is False
    assert result.secret_access_observed is False


def test_exact_b2_reenumerates_each_first_state_and_deduplicates_final_text() -> None:
    root = _state("root")
    expander = GraphExpander(
        {
            "root": (
                {"text": "a", "surviving": 8},
                {"text": "b", "surviving": 8},
            ),
            "a": (
                {"text": "z", "surviving": 5, "cost": 1},
                {"text": "x", "surviving": 6, "cost": 1},
            ),
            "b": (
                {"text": "z", "surviving": 4, "cost": 2},
                {"text": "y", "surviving": 7, "cost": 1},
            ),
        }
    )
    result = exact_b2(expander, root)
    assert {state.text for state in result.states} == {"x", "y", "z"}
    z = next(state for state in result.states if state.text == "z")
    assert z.surviving_root_observations == 4
    assert result.expanded_state_count == 3


def test_greedy_uses_marginal_destruction_then_required_ties() -> None:
    root = _state("root")
    expander = GraphExpander(
        {
            "root": (
                {"text": "higher-risk", "surviving": 7, "risk": 2, "cost": 1, "token_distance": 1},
                {"text": "lower-risk", "surviving": 7, "risk": 1, "cost": 3, "token_distance": 5},
                {"text": "less-damage", "surviving": 8, "risk": 0, "cost": 1},
            )
        }
    )
    result = greedy_search(expander, root, 1)
    assert tuple(state.text for state in result.states) == ("lower-risk",)


def test_greedy_prefers_lower_visible_cost_then_token_distance_then_mask() -> None:
    root = _state("root")
    expander = GraphExpander(
        {
            "root": (
                {"text": "costly", "surviving": 7, "risk": 1, "cost": 3, "token_distance": 1, "masked": 9},
                {"text": "far", "surviving": 7, "risk": 1, "cost": 2, "token_distance": 4, "masked": 9},
                {"text": "near", "surviving": 7, "risk": 1, "cost": 2, "token_distance": 2, "masked": 1},
            )
        }
    )
    result = greedy_search(expander, root, 1)
    assert tuple(state.text for state in result.states) == ("near",)


def test_pareto_frontier_keeps_tradeoffs() -> None:
    states = (
        _state("a", depth=1, operations=(_hash("oa"),), ancestors=(_hash("ancestor-a"),), surviving=5, cost=2, risk=1),
        _state("b", depth=1, operations=(_hash("ob"),), ancestors=(_hash("ancestor-b"),), surviving=6, cost=1, risk=1),
        _state("c", depth=1, operations=(_hash("oc"),), ancestors=(_hash("ancestor-c"),), surviving=7, cost=3, risk=2),
    )
    frontier = pareto_frontier(states)
    assert {state.text for state in frontier} == {"a", "b"}


def test_beam_is_deterministic_when_enumeration_order_changes() -> None:
    root = _state("root")
    graph = {
        "root": (
            {"text": "a", "surviving": 7},
            {"text": "b", "surviving": 6},
            {"text": "c", "surviving": 8},
        ),
        "a": ({"text": "aa", "surviving": 5},),
        "b": ({"text": "bb", "surviving": 4},),
        "c": ({"text": "cc", "surviving": 3},),
    }
    forward = beam_search(GraphExpander(graph, reverse=False), root, 2, 2)
    reverse = beam_search(GraphExpander(graph, reverse=True), root, 2, 2)
    assert forward.result_hash == reverse.result_hash
    assert tuple(state.text for state in forward.states) == tuple(state.text for state in reverse.states)


def test_search_state_rejects_ancestor_cycle() -> None:
    root = _state("root")
    operation = _hash("cycle-operation")
    with pytest.raises(ValueError, match="cannot appear in its ancestry"):
        _state(
            "root",
            depth=1,
            operations=(operation,),
            ancestors=(root.text_hash,),
            surviving=9,
        )


def test_scheduling_modules_have_no_scoring_or_secret_imports() -> None:
    import ast
    from pathlib import Path

    package = Path(__file__).parents[1] / "fuckmark" / "scheduling"
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            forbidden = ("detector", "g_value", "gvalue", "bayesian", "secret_key", "watermark_key")
            assert all(all(value not in name.lower() for value in forbidden) for name in names), (path, names)
