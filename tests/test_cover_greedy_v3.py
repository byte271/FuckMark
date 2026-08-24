import pytest

from fuckmark.experiments.cover_greedy_v3 import (
    COVER_GREEDY_V3_ALGORITHM_VERSION,
    COVER_GREEDY_V3_POLICY_ID,
    schedule_cover_greedy_v3,
)
from fuckmark.transforms import content_region_coverage_transform_registry


class _OffsetTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode("utf-8"))

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        data = text.encode("utf-8")
        result = {"input_ids": list(data)}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(data))]
        return result


PROSE = (
    "Careful testing matters before any claim becomes knowledge. A single result "
    "cannot overturn a body of evidence. Repetition across labs makes findings durable."
)


def _run(budget, text=PROSE):
    registry = content_region_coverage_transform_registry()
    enumeration = registry.enumerate(text)
    return schedule_cover_greedy_v3(
        source_sample_id="cover-test",
        source_text=text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=_OffsetTokenizer(),
        tokenizer_identity_hash="0" * 64,
        ngram_len=5,
        budget=budget,
    )


def test_algorithm_identity_is_pinned():
    assert COVER_GREEDY_V3_ALGORITHM_VERSION == "cover-greedy-key-blind-v3"
    assert COVER_GREEDY_V3_POLICY_ID == "exact-zero-intact-root-windows-v1"


def test_result_is_deterministic_and_hash_bound():
    first = _run(16)
    second = _run(16)
    assert first.result_hash == second.result_hash
    assert first.selected_candidate_ids == second.selected_candidate_ids


def test_respects_budget_and_partition_invariants():
    result = _run(8)
    assert result.selected_candidate_count <= 8
    assert result.static_phase_selections + result.repair_phase_selections == result.selected_candidate_count
    assert not set(result.selected_candidate_ids) & set(result.unselected_candidate_ids)
    assert result.intact_window_count <= result.root_window_count
    assert result.intact_fraction == (
        result.intact_window_count / result.root_window_count if result.root_window_count else 0.0
    )


def test_achieved_zero_matches_counts():
    capped = _run(4)
    assert capped.achieved_zero == (capped.root_window_count > 0 and capped.intact_window_count == 0)
    generous = _run(64)
    assert generous.achieved_zero == (generous.intact_window_count == 0)


def test_stays_detector_blind_and_key_blind():
    result = _run(6)
    assert result.detector_access_observed is False
    assert result.secret_access_observed is False


def test_high_budget_reduces_or_preserves_intact_windows():
    low = _run(4)
    high = _run(32)
    assert high.intact_window_count <= low.intact_window_count


def test_empty_pool_returns_identity():
    text = "Untouched"
    registry = content_region_coverage_transform_registry()
    enumeration = registry.enumerate(text)
    assert enumeration.candidates == ()
    result = schedule_cover_greedy_v3(
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
    assert result.static_phase_selections == 0
    assert result.repair_phase_selections == 0
    assert result.achieved_zero is False
