from __future__ import annotations

from dataclasses import dataclass

import pytest

from fuckmark.experiments.candidate_density_audit import (
    STRICT_NO_REACHABILITY_SCARCITY,
    STRICT_SCARCITY_B4,
    STRICT_SCARCITY_B6,
    StrictCandidateDensityRow,
    StrictCostExpander,
    assess_strict_candidate,
    classify_strict_candidate_density,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.scheduling.state_search import SearchState, SearchTransition


def _hash(value: str) -> str:
    return sha256_text(value)


def _root(text: str = "alpha beta gamma delta epsilon") -> SearchState:
    return SearchState.create(
        root_source_hash=_hash(text),
        text=text,
        depth=0,
        operation_hashes=(),
        ancestor_text_hashes=(),
        root_tokenization_hash=_hash("root-tokens:" + text),
        current_tokenization_hash=_hash("current-tokens:" + text),
        survival_report_hash=_hash("survival:" + text),
        enumeration_hash=_hash("enumeration:" + text),
        hard_invariant_report_hash=_hash("hard:" + text),
        surviving_root_observations=10,
        newly_masked_count=0,
        highest_risk_tier=0,
        visible_cost=0,
        token_edit_distance=0,
    )


def _child(root: SearchState, text: str, *, suffix: str) -> SearchTransition:
    op_hash = _hash("op:" + suffix)
    state = SearchState.create(
        root_source_hash=root.root_source_hash,
        text=text,
        depth=1,
        operation_hashes=(op_hash,),
        ancestor_text_hashes=(root.text_hash,),
        root_tokenization_hash=root.root_tokenization_hash,
        current_tokenization_hash=_hash("tokens:" + suffix),
        survival_report_hash=_hash("survival:" + suffix),
        enumeration_hash=_hash("enumeration:" + suffix),
        hard_invariant_report_hash=_hash("hard:" + suffix),
        surviving_root_observations=8,
        newly_masked_count=0,
        highest_risk_tier=1,
        visible_cost=1,
        token_edit_distance=1,
    )
    return SearchTransition.create(
        parent=root,
        candidate_hash=_hash("candidate:" + suffix),
        operation_hash=op_hash,
        visible_cost_delta=1,
        child=state,
    )


@dataclass
class _Expander:
    transitions: tuple[SearchTransition, ...]
    detector: bool = False
    secret: bool = False

    @property
    def detector_access_observed(self) -> bool:
        return self.detector

    @property
    def secret_access_observed(self) -> bool:
        return self.secret

    def expand(self, state: SearchState):
        return self.transitions if state.depth == 0 else ()


def _row(sample: str, *, b4: bool, b6: bool) -> StrictCandidateDensityRow:
    payload = {
        "algorithm_version": "strict-candidate-density-row-v1",
        "source_sample_id": sample,
        "root_enumerated_candidate_count": 8,
        "root_planner_transition_count": 8,
        "root_strict_transition_count": 6,
        "strict_unique_transition_count": 20,
        "raw_unique_transition_count": 25,
        "strict_b4_reachable": b4,
        "strict_b6_reachable": b6,
        "strict_b4_final_depth": 4 if b4 else 3,
        "strict_b6_final_depth": 6 if b6 else (4 if b4 else 3),
        "root_family_counts": (("contraction", 4), ("surface", 4)),
        "root_strict_family_counts": (("contraction", 3), ("surface", 3)),
        "rejection_reason_counts": (("STRICT_CHARACTER_EDIT_RATE_EXCEEDED", 2),),
        "detector_access_observed": False,
        "secret_access_observed": False,
    }
    kwargs = {key: value for key, value in payload.items() if key != "algorithm_version"}
    return StrictCandidateDensityRow(**kwargs, row_hash=sha256_json(payload))


def test_assess_strict_candidate_accepts_small_visible_edit() -> None:
    source = " ".join(["ordinary"] * 40 + ["cat"])
    transformed = " ".join(["ordinary"] * 40 + ["bat"])
    root = _root(source)
    transition = _child(root, transformed, suffix="small")
    assessment = assess_strict_candidate(root.text, transition.child)
    assert assessment.strict_eligible
    assert assessment.word_edit_rate <= 0.03
    assert assessment.character_edit_rate <= 0.015
    assert assessment.reason_codes == ()


def test_assess_strict_candidate_rejects_large_visible_edit() -> None:
    source = " ".join(["ordinary"] * 40 + ["cat"])
    root = _root(source)
    transition = _child(root, "ordinary cat", suffix="large")
    assessment = assess_strict_candidate(root.text, transition.child)
    assert not assessment.strict_eligible
    assert "STRICT_LENGTH_RATIO_EXCEEDED" in assessment.reason_codes


def test_strict_cost_expander_filters_before_search_and_stays_blind() -> None:
    source = " ".join(["ordinary"] * 40 + ["cat"])
    root = _root(source)
    allowed = _child(root, " ".join(["ordinary"] * 40 + ["bat"]), suffix="allowed")
    rejected = _child(root, "ordinary cat", suffix="rejected")
    expander = StrictCostExpander(_Expander((allowed, rejected)), root.text)
    result = expander.expand(root)
    assert tuple(value.transition_hash for value in result) == (allowed.transition_hash,)
    assert expander.raw_unique_transition_count == 2
    assert expander.strict_unique_transition_count == 1
    assert expander.detector_access_observed is False
    assert expander.secret_access_observed is False


def test_strict_cost_expander_fails_closed_on_detector_access() -> None:
    root = _root()
    expander = StrictCostExpander(_Expander((), detector=True), root.text)
    with pytest.raises(ValueError, match="prohibited selection access"):
        expander.expand(root)


def test_candidate_density_classification_is_reachability_based() -> None:
    assert classify_strict_candidate_density((_row("a", b4=False, b6=False), _row("b", b4=True, b6=True))) == STRICT_SCARCITY_B4
    assert classify_strict_candidate_density((_row("a", b4=True, b6=False), _row("b", b4=True, b6=True))) == STRICT_SCARCITY_B6
    assert classify_strict_candidate_density((_row("a", b4=True, b6=True), _row("b", b4=True, b6=True))) == STRICT_NO_REACHABILITY_SCARCITY
