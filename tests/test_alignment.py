from fuckmark.alignment import AlignmentOp, align_tokens, conserved_runs


def test_identical_sequences_have_zero_distance() -> None:
    result = align_tokens([1, 2, 3], [1, 2, 3])
    assert result.distance == 0
    assert [step.op for step in result.steps] == [AlignmentOp.MATCH] * 3
    assert result.original_to_transformed == (0, 1, 2)
    assert result.transformed_to_original == (0, 1, 2)
    assert conserved_runs(result) == ((0, 3, 0, 3),)


def test_single_substitution_breaks_only_matching_run() -> None:
    result = align_tokens([1, 2, 3, 4, 5], [1, 2, 9, 4, 5])
    assert result.distance == 1
    assert result.original_to_transformed == (0, 1, None, 3, 4)
    assert conserved_runs(result) == ((0, 2, 0, 2), (3, 5, 3, 5))


def test_single_insertion_resynchronizes_suffix() -> None:
    result = align_tokens([1, 2, 3, 4], [1, 2, 9, 3, 4])
    assert result.distance == 1
    assert result.original_to_transformed == (0, 1, 3, 4)
    assert conserved_runs(result) == ((0, 2, 0, 2), (2, 4, 3, 5))


def test_single_deletion_resynchronizes_suffix() -> None:
    result = align_tokens([1, 2, 9, 3, 4], [1, 2, 3, 4])
    assert result.distance == 1
    assert result.original_to_transformed == (0, 1, None, 2, 3)
    assert conserved_runs(result) == ((0, 2, 0, 2), (3, 5, 2, 4))


def test_empty_original_is_all_insertions() -> None:
    result = align_tokens([], [4, 5])
    assert result.distance == 2
    assert [step.op for step in result.steps] == [AlignmentOp.INSERT, AlignmentOp.INSERT]
    assert result.original_to_transformed == ()
    assert result.transformed_to_original == (None, None)


def test_empty_transformed_is_all_deletions() -> None:
    result = align_tokens([4, 5], [])
    assert result.distance == 2
    assert [step.op for step in result.steps] == [AlignmentOp.DELETE, AlignmentOp.DELETE]
    assert result.original_to_transformed == (None, None)
    assert result.transformed_to_original == ()


def test_repeated_tokens_produce_deterministic_alignment() -> None:
    first = align_tokens([1, 1, 2], [1, 2])
    second = align_tokens([1, 1, 2], [1, 2])
    assert first == second
    assert first.distance == 1


def test_substitution_keeps_positional_alignment_map() -> None:
    result = align_tokens([1, 2, 3], [1, 9, 3])
    assert result.original_to_transformed == (0, None, 2)
    assert result.original_to_transformed_aligned == (0, 1, 2)
    assert result.transformed_to_original_aligned == (0, 1, 2)


def test_alignment_rejects_non_integer_tokens() -> None:
    import pytest

    with pytest.raises(TypeError):
        align_tokens([1, "2", 3], [1, 2, 3])


def test_alignment_cell_limit_prevents_unbounded_matrix_allocation() -> None:
    import pytest

    with pytest.raises(ValueError):
        align_tokens(list(range(100)), list(range(100)), max_cells=100)


def test_alignment_rejects_non_sequence_inputs() -> None:
    import pytest

    with pytest.raises(TypeError):
        align_tokens(123, [1, 2])
    with pytest.raises(TypeError):
        align_tokens([1, 2], "12")


def test_alignment_result_rejects_boolean_distance() -> None:
    import pytest
    from fuckmark.alignment import AlignmentResult

    with pytest.raises(TypeError):
        AlignmentResult(True, (), (), (), (), (), 0)


def test_alignment_step_rejects_string_operation() -> None:
    import pytest
    from fuckmark.alignment import AlignmentStep

    with pytest.raises(TypeError):
        AlignmentStep("match", 0, 0, 1, 1)


def test_alignment_rejects_negative_token_ids() -> None:
    import pytest

    with pytest.raises(ValueError):
        align_tokens([1, -1, 2], [1, 2])


def test_alignment_step_enforces_match_and_substitution_token_semantics() -> None:
    import pytest
    from fuckmark.alignment import AlignmentStep

    with pytest.raises(ValueError):
        AlignmentStep(AlignmentOp.MATCH, 0, 0, 1, 2)
    with pytest.raises(ValueError):
        AlignmentStep(AlignmentOp.SUBSTITUTE, 0, 0, 1, 1)


def test_alignment_result_rejects_inconsistent_maps_at_construction() -> None:
    import pytest
    from fuckmark.alignment import AlignmentResult, AlignmentStep

    steps = (AlignmentStep(AlignmentOp.MATCH, 0, 0, 1, 1),)
    with pytest.raises(ValueError):
        AlignmentResult(0, steps, (None,), (None,), (None,), (None,), 0)
