from fuckmark.alignment import align_tokens
from fuckmark.observations import (
    StructuralObservationState,
    build_token_ngrams,
    structural_observation_diff,
    summarize_structural_observations,
)


def test_build_token_ngrams() -> None:
    ngrams = build_token_ngrams([1, 2, 3, 4], 3)
    assert [ngram.tokens for ngram in ngrams] == [(1, 2, 3), (2, 3, 4)]


def test_short_sequence_has_no_ngrams() -> None:
    assert build_token_ngrams([1, 2], 3) == ()


def test_single_substitution_replaces_only_overlapping_ngrams() -> None:
    original = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    transformed = [1, 2, 3, 4, 99, 6, 7, 8, 9]
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 5, alignment)
    assert len(diffs) == 5
    assert all(diff.state is StructuralObservationState.REPLACED for diff in diffs)


def test_substitution_does_not_create_global_suffix_damage() -> None:
    original = list(range(20))
    transformed = original.copy()
    transformed[5] = 999
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 5, alignment)
    replaced = [diff.original_index for diff in diffs if diff.state is StructuralObservationState.REPLACED]
    preserved = [diff.original_index for diff in diffs if diff.state is StructuralObservationState.PRESERVED]
    assert replaced == [1, 2, 3, 4, 5]
    assert 6 in preserved
    assert 15 in preserved


def test_insertion_resynchronizes_preserved_ngrams() -> None:
    original = list(range(12))
    transformed = original[:4] + [999] + original[4:]
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 3, alignment)
    preserved_pairs = [
        (diff.original_index, diff.transformed_index)
        for diff in diffs
        if diff.state is StructuralObservationState.PRESERVED
    ]
    assert (4, 5) in preserved_pairs
    assert (9, 10) in preserved_pairs


def test_summary_ratios_are_derived_from_realized_diff() -> None:
    original = list(range(10))
    transformed = original.copy()
    transformed[5] = 100
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 3, alignment)
    summary = summarize_structural_observations(original, transformed, 3, diffs)
    assert summary.original_count == 8
    assert summary.replaced_count == 3
    assert summary.preserved_count == 5
    assert summary.replacement_ratio == 3 / 8


def test_substitution_replacement_retains_aligned_transformed_index() -> None:
    original = [1, 2, 3, 4, 5, 6]
    transformed = [1, 2, 9, 4, 5, 6]
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 3, alignment)
    replaced_pairs = [
        (diff.original_index, diff.transformed_index)
        for diff in diffs
        if diff.state is StructuralObservationState.REPLACED
    ]
    assert replaced_pairs == [(0, 0), (1, 1), (2, 2)]


def test_summary_rejects_non_positive_ngram_length() -> None:
    import pytest

    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2], [1, 2], 0, ())


def test_summary_rejects_duplicate_or_out_of_order_diff_indices() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    diffs = (
        StructuralObservationDiff(0, 0, StructuralObservationState.PRESERVED),
        StructuralObservationDiff(0, 1, StructuralObservationState.PRESERVED),
    )
    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2, 3], [1, 2, 3], 2, diffs)


def test_structural_diff_rejects_alignment_from_other_sequences() -> None:
    import pytest

    alignment = align_tokens([1, 2, 3], [1, 2, 3])
    with pytest.raises(ValueError):
        structural_observation_diff([1, 9, 3], [1, 2, 3], 2, alignment)


def test_insertion_marks_only_non_corresponding_windows_unmapped() -> None:
    original = [1, 2, 3, 4, 5, 6]
    transformed = [1, 2, 99, 3, 4, 5, 6]
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 3, alignment)
    unmapped = [diff.original_index for diff in diffs if diff.state is StructuralObservationState.UNMAPPED]
    preserved = [diff.original_index for diff in diffs if diff.state is StructuralObservationState.PRESERVED]
    assert unmapped == [0, 1]
    assert preserved == [2, 3]


def test_deletion_marks_windows_containing_deleted_token_unmapped() -> None:
    original = [1, 2, 99, 3, 4, 5, 6]
    transformed = [1, 2, 3, 4, 5, 6]
    alignment = align_tokens(original, transformed)
    diffs = structural_observation_diff(original, transformed, 3, alignment)
    unmapped = [diff.original_index for diff in diffs if diff.state is StructuralObservationState.UNMAPPED]
    assert unmapped == [0, 1, 2]


def test_structural_diff_requires_transformed_index_for_replaced_state() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    with pytest.raises(ValueError):
        StructuralObservationDiff(0, None, StructuralObservationState.REPLACED)


def test_structural_diff_rejects_string_state() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    with pytest.raises(TypeError):
        StructuralObservationDiff(0, 0, "preserved")


def test_token_ngram_rejects_non_integer_indices() -> None:
    import pytest
    from fuckmark.observations import TokenNgram

    with pytest.raises(TypeError):
        TokenNgram(True, 0, 1, (1,))
    with pytest.raises(TypeError):
        TokenNgram(0, 0.0, 1, (1,))


def test_summary_rejects_invalid_token_sequences_and_diff_types() -> None:
    import pytest

    with pytest.raises(TypeError):
        summarize_structural_observations([1, "2"], [1, 2], 2, ())
    with pytest.raises(TypeError):
        summarize_structural_observations([1, 2], [1, 2], 2, ("bad",))


def test_summary_counts_reject_booleans_and_floats() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationSummary

    with pytest.raises(TypeError):
        StructuralObservationSummary(True, 1, 1, 0, 0)
    with pytest.raises(TypeError):
        StructuralObservationSummary(1, 1, 1.0, 0, 0)


def test_observations_reject_negative_token_ids() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_token_ngrams([1, -1, 2], 2)


def test_summary_rejects_duplicate_or_nonmonotonic_transformed_mappings() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    duplicate = (
        StructuralObservationDiff(0, 0, StructuralObservationState.PRESERVED),
        StructuralObservationDiff(1, 0, StructuralObservationState.REPLACED),
    )
    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2, 3], [1, 9, 3], 2, duplicate)

    nonmonotonic = (
        StructuralObservationDiff(0, 1, StructuralObservationState.REPLACED),
        StructuralObservationDiff(1, 0, StructuralObservationState.REPLACED),
    )
    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2, 3], [9, 2, 1], 2, nonmonotonic)


def test_summary_rejects_more_mapped_observations_than_transformed_observations() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationSummary

    with pytest.raises(ValueError):
        StructuralObservationSummary(2, 1, 1, 1, 0)


def test_summary_rejects_forged_preserved_state() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    diffs = (
        StructuralObservationDiff(0, 0, StructuralObservationState.PRESERVED),
        StructuralObservationDiff(1, 1, StructuralObservationState.REPLACED),
    )
    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2, 3], [1, 9, 3], 2, diffs)


def test_summary_rejects_forged_replaced_state() -> None:
    import pytest
    from fuckmark.observations import StructuralObservationDiff

    diffs = (
        StructuralObservationDiff(0, 0, StructuralObservationState.REPLACED),
        StructuralObservationDiff(1, 1, StructuralObservationState.PRESERVED),
    )
    with pytest.raises(ValueError):
        summarize_structural_observations([1, 2, 3], [1, 2, 3], 2, diffs)
