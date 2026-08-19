from __future__ import annotations

from dataclasses import dataclass

import pytest

from fuckmark.hashing import sha256_text
from fuckmark.search.beam_v3 import BeamV3StateMetrics, beam_search_v3
from fuckmark.scheduling.beam_v2 import beam_search_v2
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


def _transition(
    root: SearchState,
    *,
    text: str,
    surviving: int,
    visible_cost: int = 1,
    token_distance: int = 1,
) -> SearchTransition:
    operation_hash = _hash("operation:" + text)
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
        surviving_root_observations=surviving,
        newly_masked_count=0,
        highest_risk_tier=1,
        visible_cost=visible_cost,
        token_edit_distance=token_distance,
    )
    return SearchTransition.create(
        parent=root,
        candidate_hash=_hash("candidate:" + text),
        operation_hash=operation_hash,
        visible_cost_delta=visible_cost,
        child=child,
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

    def expand(self, state: SearchState) -> tuple[SearchTransition, ...]:
        return self.transitions if state.depth == 0 else ()


class _Evaluator:
    def __init__(
        self,
        metrics: dict[str, BeamV3StateMetrics],
        *,
        detector: bool = False,
        secret: bool = False,
    ) -> None:
        self._metrics = metrics
        self._detector = detector
        self._secret = secret

    @property
    def detector_access_observed(self) -> bool:
        return self._detector

    @property
    def secret_access_observed(self) -> bool:
        return self._secret

    def evaluate(self, state: SearchState) -> BeamV3StateMetrics:
        return self._metrics[state.search_state_hash]


def _metrics(
    state: SearchState,
    *,
    root_valid: int = 10,
    final_valid: int = 10,
    preserved: int = 10,
    word_rate: float = 0.0,
    char_rate: float = 0.0,
    token_distance: int | None = None,
    eligible: bool = True,
) -> BeamV3StateMetrics:
    reasons = () if eligible else ("VISIBLE_FIDELITY_LIMIT_EXCEEDED",)
    return BeamV3StateMetrics.create(
        state_hash=state.search_state_hash,
        geometry_hash=_hash("geometry:" + state.text),
        root_valid_observation_count=root_valid,
        final_valid_observation_count=final_valid,
        preserved_root_valid_observation_count=preserved,
        repetition_mask_delta=0,
        word_edit_rate=word_rate,
        character_edit_rate=char_rate,
        token_edit_distance=state.token_edit_distance if token_distance is None else token_distance,
        length_ratio=1.0,
        protected_span_violation_count=0,
        hard_invariant_passed=True,
        reason_codes=reasons,
    )


def test_beam_v3_can_select_residual_winner_that_v2_rejects() -> None:
    root = _root()
    old = _transition(root, text="old", surviving=4)
    residual = _transition(root, text="residual", surviving=6)
    expander = _Expander((old, residual))
    v2 = beam_search_v2(expander, root, budget=1, beam_width=1)
    assert tuple(state.text for state in v2.states) == ("old",)
    mapping = {
        root.search_state_hash: _metrics(root),
        old.child.search_state_hash: _metrics(old.child, final_valid=10, preserved=7, word_rate=0.1, char_rate=0.05),
        residual.child.search_state_hash: _metrics(residual.child, final_valid=10, preserved=4, word_rate=0.1, char_rate=0.05),
    }
    v3 = beam_search_v3(expander, _Evaluator(mapping), root, budget=1, beam_width=1)
    assert tuple(value.state.text for value in v3.states) == ("residual",)


def test_beam_v3_prefers_higher_vdr_when_rif_is_exactly_equal() -> None:
    root = _root()
    low_vdr = _transition(root, text="low-vdr", surviving=5)
    high_vdr = _transition(root, text="high-vdr", surviving=5)
    mapping = {
        root.search_state_hash: _metrics(root),
        low_vdr.child.search_state_hash: _metrics(low_vdr.child, final_valid=5, preserved=2, word_rate=0.1, char_rate=0.05),
        high_vdr.child.search_state_hash: _metrics(high_vdr.child, final_valid=10, preserved=4, word_rate=0.1, char_rate=0.05),
    }
    result = beam_search_v3(_Expander((low_vdr, high_vdr)), _Evaluator(mapping), root, budget=1, beam_width=1)
    assert tuple(value.state.text for value in result.states) == ("high-vdr",)


def test_beam_v3_drops_ineligible_states_before_ranking() -> None:
    root = _root()
    forbidden = _transition(root, text="forbidden", surviving=1)
    allowed = _transition(root, text="allowed", surviving=8)
    mapping = {
        root.search_state_hash: _metrics(root),
        forbidden.child.search_state_hash: _metrics(forbidden.child, final_valid=10, preserved=1, eligible=False),
        allowed.child.search_state_hash: _metrics(allowed.child, final_valid=10, preserved=8),
    }
    result = beam_search_v3(_Expander((forbidden, allowed)), _Evaluator(mapping), root, budget=1, beam_width=1)
    assert tuple(value.state.text for value in result.states) == ("allowed",)
    assert result.ineligible_state_count == 1


def test_beam_v3_is_independent_of_enumeration_order() -> None:
    root = _root()
    first = _transition(root, text="first", surviving=6)
    second = _transition(root, text="second", surviving=6)
    mapping = {
        root.search_state_hash: _metrics(root),
        first.child.search_state_hash: _metrics(first.child, final_valid=10, preserved=5),
        second.child.search_state_hash: _metrics(second.child, final_valid=10, preserved=5),
    }
    evaluator = _Evaluator(mapping)
    forward = beam_search_v3(_Expander((first, second)), evaluator, root, budget=1, beam_width=2)
    reverse = beam_search_v3(_Expander((second, first)), evaluator, root, budget=1, beam_width=2)
    assert forward.result_hash == reverse.result_hash
    assert forward.states == reverse.states


@pytest.mark.parametrize(
    ("expander_detector", "expander_secret", "evaluator_detector", "evaluator_secret"),
    (
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, False, False, True),
    ),
)
def test_beam_v3_fails_closed_on_detector_or_secret_access(
    expander_detector: bool,
    expander_secret: bool,
    evaluator_detector: bool,
    evaluator_secret: bool,
) -> None:
    root = _root()
    evaluator = _Evaluator(
        {root.search_state_hash: _metrics(root)},
        detector=evaluator_detector,
        secret=evaluator_secret,
    )
    with pytest.raises(ValueError, match="contaminates"):
        beam_search_v3(
            _Expander((), detector=expander_detector, secret=expander_secret),
            evaluator,
            root,
            budget=0,
            beam_width=1,
        )
