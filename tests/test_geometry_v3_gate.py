from __future__ import annotations

from fuckmark.experiments.geometry_v3_gate import (
    GEOMETRY_V3_K1,
    GEOMETRY_V3_K2,
    GEOMETRY_V3_PASS,
    GeometryV3GateRow,
    MatchedVisibleCostEnvelope,
    PublicResidualStateEvaluator,
    classify_geometry_v3_gate,
)
from fuckmark.hashing import sha256_text
from fuckmark.scheduling.state_search import SearchState


def _hash(value: str) -> str:
    return sha256_text(value)


def _state(
    source_id: str,
    *,
    suffix: str,
    surviving: int,
    visible_cost: int = 4,
    token_distance: int = 4,
) -> SearchState:
    source_text = "root:" + source_id
    operation_hash = _hash(f"operation:{source_id}:{suffix}")
    return SearchState.create(
        root_source_hash=_hash(source_text),
        text=f"{source_text}:{suffix}",
        depth=1,
        operation_hashes=(operation_hash,),
        ancestor_text_hashes=(_hash(source_text),),
        root_tokenization_hash=_hash(f"root-tokens:{source_id}"),
        current_tokenization_hash=_hash(f"tokens:{source_id}:{suffix}"),
        survival_report_hash=_hash(f"survival:{source_id}:{suffix}"),
        enumeration_hash=_hash(f"enumeration:{source_id}:{suffix}"),
        hard_invariant_report_hash=_hash(f"invariant:{source_id}:{suffix}"),
        surviving_root_observations=surviving,
        newly_masked_count=0,
        highest_risk_tier=1,
        visible_cost=visible_cost,
        token_edit_distance=token_distance,
    )


def _metrics(
    state: SearchState,
    *,
    root_valid: int = 100,
    final_valid: int = 100,
    preserved: int,
    word_rate: float = 0.02,
    char_rate: float = 0.01,
    token_distance: int | None = None,
    eligible: bool = True,
):
    from fuckmark.search.beam_v3 import BeamV3StateMetrics

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
        reason_codes=() if eligible else ("VISIBLE_FIDELITY_LIMIT_EXCEEDED",),
    )


def _row(
    source_id: str,
    budget: int,
    *,
    v2_preserved: int,
    v3_preserved: int,
    v2_surviving: int = 50,
    v3_surviving: int = 50,
    v2_final: int = 100,
    v3_final: int = 100,
    v2_word: float = 0.02,
    v3_word: float = 0.02,
    v2_char: float = 0.01,
    v3_char: float = 0.01,
    v2_token: int = 4,
    v3_token: int = 4,
    v2_visible: int = 4,
    v3_visible: int = 4,
) -> GeometryV3GateRow:
    v2_state = _state(source_id, suffix=f"v2-b{budget}", surviving=v2_surviving, visible_cost=v2_visible, token_distance=v2_token)
    v3_state = _state(source_id, suffix=f"v3-b{budget}", surviving=v3_surviving, visible_cost=v3_visible, token_distance=v3_token)
    return GeometryV3GateRow.create(
        source_sample_id=source_id,
        budget=budget,
        v2_status="SUCCESS",
        v3_status="SUCCESS",
        v2_state=v2_state,
        v2_metrics=_metrics(v2_state, final_valid=v2_final, preserved=v2_preserved, word_rate=v2_word, char_rate=v2_char, token_distance=v2_token),
        v3_state=v3_state,
        v3_metrics=_metrics(v3_state, final_valid=v3_final, preserved=v3_preserved, word_rate=v3_word, char_rate=v3_char, token_distance=v3_token),
    )


def test_geometry_v3_gate_passes_matched_cost_residual_specific_gain() -> None:
    rows = (
        _row("s1", 4, v2_preserved=60, v3_preserved=50, v2_surviving=50, v3_surviving=50),
        _row("s1", 6, v2_preserved=55, v3_preserved=45, v2_surviving=45, v3_surviving=45),
        _row("s2", 4, v2_preserved=65, v3_preserved=60, v2_surviving=48, v3_surviving=50),
        _row("s2", 6, v2_preserved=58, v3_preserved=52, v2_surviving=43, v3_surviving=44),
    )
    assert classify_geometry_v3_gate(rows) == GEOMETRY_V3_PASS
    assert all(row.matched_cost_pass for row in rows)
    assert all(any(row.residual_specific_win for row in rows if row.budget == budget) for budget in (4, 6))


def test_geometry_v3_gate_k1_when_gain_only_tracks_more_root_destruction() -> None:
    rows = (
        _row("s1", 4, v2_preserved=60, v3_preserved=50, v2_surviving=50, v3_surviving=40),
        _row("s1", 6, v2_preserved=55, v3_preserved=45, v2_surviving=45, v3_surviving=35),
        _row("s2", 4, v2_preserved=65, v3_preserved=55, v2_surviving=55, v3_surviving=45),
        _row("s2", 6, v2_preserved=58, v3_preserved=48, v2_surviving=48, v3_surviving=38),
    )
    assert classify_geometry_v3_gate(rows) == GEOMETRY_V3_K1
    assert not any(row.residual_specific_win for row in rows)


def test_geometry_v3_gate_k2_when_one_budget_has_no_median_gain() -> None:
    rows = (
        _row("s1", 4, v2_preserved=60, v3_preserved=50),
        _row("s1", 6, v2_preserved=55, v3_preserved=55),
        _row("s2", 4, v2_preserved=65, v3_preserved=60),
        _row("s2", 6, v2_preserved=58, v3_preserved=58),
    )
    assert classify_geometry_v3_gate(rows) == GEOMETRY_V3_K2


def test_geometry_v3_row_rejects_more_expensive_v3_as_matched_cost() -> None:
    row = _row("s1", 4, v2_preserved=60, v3_preserved=50, v2_word=0.02, v3_word=0.03)
    assert row.matched_cost_pass is False
    assert row.residual_specific_win is False
    companion = _row("s1", 6, v2_preserved=55, v3_preserved=45)
    assert classify_geometry_v3_gate((row, companion)) == GEOMETRY_V3_K2


def _synthetic_state(source_text: str, transformed_text: str) -> SearchState:
    operation_hash = _hash("synthetic-operation")
    return SearchState.create(
        root_source_hash=_hash(source_text),
        text=transformed_text,
        depth=1,
        operation_hashes=(operation_hash,),
        ancestor_text_hashes=(_hash(source_text),),
        root_tokenization_hash=_hash("synthetic-root-tokens"),
        current_tokenization_hash=_hash("synthetic-current-tokens"),
        survival_report_hash=_hash("synthetic-survival"),
        enumeration_hash=_hash("synthetic-enumeration"),
        hard_invariant_report_hash=_hash("synthetic-invariant"),
        surviving_root_observations=4,
        newly_masked_count=0,
        highest_risk_tier=1,
        visible_cost=1,
        token_edit_distance=1,
    )


def test_public_residual_evaluator_enforces_frozen_matched_cost_envelope() -> None:
    source = "alpha beta gamma delta epsilon zeta"
    transformed = "alpha beta gamma delta epsilon eta"
    token_map = {
        source: (1, 2, 3, 4, 5, 6, 7, 8),
        transformed: (1, 2, 3, 4, 5, 9, 7, 8),
    }

    def retokenize(text: str):
        return token_map[text]

    state = _synthetic_state(source, transformed)
    audit = PublicResidualStateEvaluator(
        root_text=source,
        retokenize=retokenize,
        eos_token_id=99,
        ngram_len=2,
        context_history_size=1024,
        hard_invariant_validator=lambda _: True,
    )
    audit_metrics = audit.evaluate(state)
    assert audit_metrics.eligible
    permissive = MatchedVisibleCostEnvelope.create(
        max_word_edit_rate=audit_metrics.word_edit_rate,
        max_character_edit_rate=audit_metrics.character_edit_rate,
        max_token_edit_distance=audit_metrics.token_edit_distance,
        max_visible_cost=state.visible_cost,
    )
    permitted = PublicResidualStateEvaluator(
        root_text=source,
        retokenize=retokenize,
        eos_token_id=99,
        ngram_len=2,
        context_history_size=1024,
        hard_invariant_validator=lambda _: True,
        cost_envelope=permissive,
    ).evaluate(state)
    assert permitted.eligible

    tighter = MatchedVisibleCostEnvelope.create(
        max_word_edit_rate=max(0.0, audit_metrics.word_edit_rate - 1e-6),
        max_character_edit_rate=audit_metrics.character_edit_rate,
        max_token_edit_distance=audit_metrics.token_edit_distance,
        max_visible_cost=state.visible_cost,
    )
    rejected = PublicResidualStateEvaluator(
        root_text=source,
        retokenize=retokenize,
        eos_token_id=99,
        ngram_len=2,
        context_history_size=1024,
        hard_invariant_validator=lambda _: True,
        cost_envelope=tighter,
    ).evaluate(state)
    assert rejected.eligible is False
    assert "VISIBLE_FIDELITY_LIMIT_EXCEEDED" in rejected.reason_codes
