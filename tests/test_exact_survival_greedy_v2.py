import pytest

from fuckmark.experiments.exact_survival_greedy_v2 import (
    EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION,
    EXACT_SURVIVAL_GREEDY_V2_POLICY_ID,
    schedule_exact_survival_greedy_v2,
)
from fuckmark.transforms import content_region_coverage_transform_registry


class _OffsetTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode("utf-8"))


def _plan(registry, source_text, budget, ngram_len=5):
    enumeration = registry.enumerate(source_text)
    if not enumeration.candidates:
        enumeration = None
    result = schedule_exact_survival_greedy_v2(
        source_sample_id="sample-v2",
        source_text=source_text,
        registry=registry,
        enumeration=enumeration if enumeration else registry.enumerate("fallback word text."),
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash="0" * 64,
        ngram_len=ngram_len,
        budget=budget,
    )
    return result


def test_algorithm_version_and_policy_are_pinned():
    assert EXACT_SURVIVAL_GREEDY_V2_ALGORITHM_VERSION == "exact-survival-greedy-key-blind-v2"
    assert EXACT_SURVIVAL_GREEDY_V2_POLICY_ID == "pairwise-completed-root-observation-survival-v1"


def test_v2_selection_is_deterministic_and_hash_bound():
    registry = content_region_coverage_transform_registry()
    text = "The first claim is here. A second claim follows the first. The third claim repeats the second."
    first = _plan(registry, text, 8)
    second = _plan(registry, text, 8)
    assert first.result_hash == second.result_hash
    assert first.selected_candidate_ids == second.selected_candidate_ids
    assert first.transformed_text_hash == second.transformed_text_hash


def test_v2_respects_budget_and_partition_invariants():
    registry = content_region_coverage_transform_registry()
    text = "One sentence states a fact. Another sentence states another fact. The final sentence closes it out."
    result = _plan(registry, text, 6)
    assert result.selected_candidate_count <= 6
    assert result.exact_destroyed_observation_count + result.exact_surviving_observation_count == result.root_observation_count
    assert not set(result.selected_candidate_ids) & set(result.unselected_candidate_ids)


def test_v2_stays_detector_blind_and_key_blind():
    registry = content_region_coverage_transform_registry()
    text = "A short opening line appears here. Then another line follows it closely."
    result = _plan(registry, text, 4)
    assert result.detector_access_observed is False
    assert result.secret_access_observed is False


def test_v2_empty_pool_returns_identity_without_steps():
    registry = content_region_coverage_transform_registry()
    text = "12345 protected numbers only"
    enumeration = registry.enumerate(text)
    if enumeration.candidates:
        import pytest

        pytest.skip("registry produced candidates for this fixture")
    result = schedule_exact_survival_greedy_v2(
        source_sample_id="empty",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash="0" * 64,
        ngram_len=5,
        budget=4,
    )
    assert result.selected_candidate_count == 0
    assert result.steps == ()
    assert result.exact_destroyed_observation_count == 0


def test_v2_pairwise_completion_flag_is_recorded():
    registry = content_region_coverage_transform_registry()
    text = "Words gather here. More words settle there. Words drift everywhere between sentences."
    result = _plan(registry, text, 16)
    assert isinstance(result.pairwise_completion_used, bool)
    for step in result.steps:
        assert step.marginal_exact_destruction >= 0


def test_v2_zero_budget_returns_empty_selection():
    from fuckmark.experiments.exact_survival_greedy_v2 import schedule_exact_survival_greedy_v2 as schedule

    registry = content_region_coverage_transform_registry()
    text = "Some sentence exists here. Another one follows right after."
    enumeration = registry.enumerate(text)
    result = schedule(
        source_sample_id="zero-budget",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash="0" * 64,
        ngram_len=5,
        budget=0,
    )
    assert result.selected_candidate_count == 0
    assert result.steps == ()
    assert result.exact_destroyed_observation_count == 0
    assert result.policy_saturated is False
