import pytest

from fuckmark.experiments.cover_greedy_v4 import (
    COVER_GREEDY_V4_ALGORITHM_VERSION,
    COVER_GREEDY_V4_POLICY_ID,
    schedule_cover_greedy_v4,
)
from fuckmark.geometry.observations import (
    GeometryConfig,
    build_root_observations,
)
from fuckmark.geometry.tuple_closure import (
    TUPLE_CLOSURE_ALGORITHM_VERSION,
    TupleClosureReport,
    compute_tuple_closure,
)


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
    from fuckmark.transforms import content_region_coverage_transform_registry

    registry = content_region_coverage_transform_registry()
    enumeration = registry.enumerate(text)
    return schedule_cover_greedy_v4(
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
    assert COVER_GREEDY_V4_ALGORITHM_VERSION == "cover-greedy-key-blind-v4"
    assert COVER_GREEDY_V4_POLICY_ID == "closure-free-root-evidence-v1"
    assert TUPLE_CLOSURE_ALGORITHM_VERSION == "root-tuple-recreation-closure-v1"


def test_result_is_deterministic_and_hash_bound():
    first = _run(16)
    second = _run(16)
    assert first.result_hash == second.result_hash
    assert first.selected_candidate_ids == second.selected_candidate_ids


def test_respects_budget_and_partition_invariants():
    result = _run(8)
    assert result.selected_candidate_count <= 8
    assert result.static_phase_selections + result.repair_phase_selections == (
        result.selected_candidate_count
    )
    assert not set(result.selected_candidate_ids) & set(result.unselected_candidate_ids)
    assert result.intact_window_count <= result.root_window_count
    assert result.tuple_leak_window_count <= result.root_window_count


def test_achieved_zero_requires_positional_and_closure_destruction():
    capped = _run(4)
    expected_zero = (
        capped.root_window_count > 0
        and capped.intact_window_count == 0
        and capped.tuple_leak_window_count == 0
    )
    assert capped.achieved_zero == expected_zero
    generous = _run(64)
    expected_zero = (
        generous.root_window_count > 0
        and generous.intact_window_count == 0
        and generous.tuple_leak_window_count == 0
    )
    assert generous.achieved_zero == expected_zero


def test_stays_detector_blind_and_key_blind():
    result = _run(6)
    assert result.detector_access_observed is False
    assert result.secret_access_observed is False


def test_high_budget_reduces_or_preserves_intact_windows():
    low = _run(4)
    high = _run(32)
    assert high.intact_window_count <= low.intact_window_count
    assert high.tuple_leak_window_count <= low.tuple_leak_window_count


def _root_set(ngram_len=3):
    config = GeometryConfig.create(
        tokenizer_identity_hash="0" * 64,
        ngram_len=ngram_len,
        repetition_mask_policy_id="public-context-repetition-v1",
    )
    tokens = (10, 11, 12, 13, 14, 15, 16, 17)
    return build_root_observations(
        source_sample_id="closure-test",
        source_text="abcdefgh",
        root_tokens=tokens,
        config=config,
        eligible_windows=(True,) * (len(tokens) - ngram_len + 1),
    )


def test_closure_counts_verbatim_recurrence_at_new_positions():
    root = _root_set()
    report = compute_tuple_closure(root=root, transformed_tokens=(99, 10, 11, 12, 13))
    assert isinstance(report, TupleClosureReport)
    assert report.leaked_window_count > 0
    assert report.closure_free is False


def test_closure_free_when_all_tuples_destroyed():
    root = _root_set()
    report = compute_tuple_closure(root=root, transformed_tokens=(90, 91, 92, 93, 94, 95, 96, 97))
    assert report.leaked_window_count == 0
    assert report.leaked_distinct_tuple_count == 0
    assert report.closure_free is True


def test_closure_counts_repeated_occurrences_of_one_tuple():
    root = _root_set()
    report = compute_tuple_closure(root=root, transformed_tokens=(10, 11, 12, 10, 11, 12))
    assert report.leaked_distinct_tuple_count == 1
    assert report.leaked_occurrence_count >= 2


def test_closure_rejects_mismatched_root_types():
    with pytest.raises(TypeError):
        compute_tuple_closure(root="not-a-root", transformed_tokens=(1, 2, 3))


def test_closure_binding_rejects_foreign_tokenization():
    root = _root_set()
    with pytest.raises(ValueError, match="tokenizer path inconsistency"):
        compute_tuple_closure(
            root=root,
            transformed_tokens=(1, 2, 3),
            expected_output_token_hash="a" * 64,
        )


def test_closure_binding_accepts_matching_hash():
    root = _root_set()
    from fuckmark.hashing import sha256_json

    tokens = (99, 10, 11, 12, 13)
    report = compute_tuple_closure(
        root=root,
        transformed_tokens=tokens,
        expected_output_token_hash=sha256_json(tokens),
    )
    assert report.leaked_window_count > 0
    assert report.closure_free is False
