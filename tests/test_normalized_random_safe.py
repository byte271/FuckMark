from fuckmark.hashing import sha256_text
from fuckmark.scheduling.state_search import SearchState, SearchTransition
from fuckmark.search.normalized_random_safe import (
    MATCHED_COST_INSUFFICIENT,
    MATCHED_COST_SUCCESS,
    MatchedVisibleCostEnvelope,
    derive_matched_cost_random_seed,
    matched_cost_random_safe_search,
)
from fuckmark.search.visible_cost_budget import VisibleCostTier


def _make_state(root_hash, text, operation_hashes, ancestor_texts):
    depth = len(operation_hashes)
    return SearchState.create(
        root_source_hash=root_hash,
        text=text,
        depth=depth,
        operation_hashes=tuple(operation_hashes),
        ancestor_text_hashes=tuple(sha256_text(value) for value in ancestor_texts),
        root_tokenization_hash=sha256_text("root-tokens"),
        current_tokenization_hash=sha256_text(f"tokens-{text}"),
        survival_report_hash=sha256_text(f"survival-{text}"),
        enumeration_hash=sha256_text(f"enum-{text}"),
        hard_invariant_report_hash=sha256_text(f"hard-{text}"),
        surviving_root_observations=100 - depth,
        newly_masked_count=0,
        highest_risk_tier=0,
        visible_cost=depth,
        token_edit_distance=depth,
    )


class Expander:
    detector_access_observed = False
    secret_access_observed = False

    def __init__(self, mapping):
        self.mapping = mapping

    def expand(self, state):
        return self.mapping.get(state.search_state_hash, ())


def _replace_word(text, index, value):
    words = text.split(" ")
    words[index] = value
    return " ".join(words)


def _fixture():
    root_text = " ".join(["aaaa"] * 100)
    root_hash = sha256_text(root_text)
    op1 = sha256_text("op-1")
    op2 = sha256_text("op-2")
    op3 = sha256_text("op-3")
    root = _make_state(root_hash, root_text, (), ())
    first_text = _replace_word(root_text, 0, "baaa")
    first = _make_state(root_hash, first_text, (op1,), (root_text,))
    second_text = _replace_word(first_text, 1, "baaa")
    second = _make_state(root_hash, second_text, (op1, op2), (root_text, first_text))
    third_text = _replace_word(second_text, 2, "baaa")
    third = _make_state(root_hash, third_text, (op1, op2, op3), (root_text, first_text, second_text))
    t1 = SearchTransition.create(
        parent=root,
        candidate_hash=sha256_text("candidate-1"),
        operation_hash=op1,
        visible_cost_delta=1,
        child=first,
    )
    t2 = SearchTransition.create(
        parent=first,
        candidate_hash=sha256_text("candidate-2"),
        operation_hash=op2,
        visible_cost_delta=1,
        child=second,
    )
    t3 = SearchTransition.create(
        parent=second,
        candidate_hash=sha256_text("candidate-3"),
        operation_hash=op3,
        visible_cost_delta=1,
        child=third,
    )
    return root_text, root, second, Expander(
        {
            root.search_state_hash: (t1,),
            first.search_state_hash: (t2,),
            second.search_state_hash: (t3,),
        }
    )


def test_matched_random_never_exceeds_beam_realized_envelope():
    root_text, root, reference, expander = _fixture()
    envelope = MatchedVisibleCostEnvelope.from_reference(
        root_text=root_text,
        tier=VisibleCostTier.STRICT,
        reference_state=reference,
    )
    seed = derive_matched_cost_random_seed("sample", VisibleCostTier.STRICT, 0)
    result = matched_cost_random_safe_search(
        expander,
        root,
        root_text=root_text,
        envelope=envelope,
        seed=seed,
    )
    assert result.status == MATCHED_COST_SUCCESS
    assert result.final_state.search_state_hash == reference.search_state_hash
    assert result.final_state.token_edit_distance <= envelope.max_token_edit_distance
    assert result.final_state.visible_cost <= envelope.max_visible_cost
    assert envelope.allows(root_text=root_text, state=result.final_state)


def test_matched_random_records_insufficient_without_relaxing_cost():
    root_text, root, reference, _ = _fixture()
    envelope = MatchedVisibleCostEnvelope.from_reference(
        root_text=root_text,
        tier=VisibleCostTier.STRICT,
        reference_state=reference,
    )
    result = matched_cost_random_safe_search(
        Expander({}),
        root,
        root_text=root_text,
        envelope=envelope,
        seed=derive_matched_cost_random_seed("sample", VisibleCostTier.STRICT, 1),
    )
    assert result.status == MATCHED_COST_INSUFFICIENT
    assert result.final_state == root
    assert result.transition_hashes == ()
    assert result.candidate_hashes == ()


def test_matched_random_seed_is_stable_and_stratified():
    a = derive_matched_cost_random_seed("sample", VisibleCostTier.STRICT, 0)
    assert a == derive_matched_cost_random_seed("sample", VisibleCostTier.STRICT, 0)
    assert a != derive_matched_cost_random_seed("sample", VisibleCostTier.RELAXED, 0)
    assert a != derive_matched_cost_random_seed("sample", VisibleCostTier.STRICT, 1)
