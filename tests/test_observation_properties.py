from itertools import combinations, product

from fuckmark.adapters import DeepMindReferenceAdapter, DeepMindReferenceConfig
from fuckmark.alignment import AlignmentOp, align_tokens, conserved_runs
from fuckmark.coverage import merge_intervals, substitution_observation_interval, union_size
from fuckmark.observations import StructuralObservationState, structural_observation_diff, summarize_structural_observations


def _reference_distance(original: tuple[int, ...], transformed: tuple[int, ...]) -> int:
    previous = list(range(len(transformed) + 1))
    for i, original_token in enumerate(original, start=1):
        current = [i]
        for j, transformed_token in enumerate(transformed, start=1):
            current.append(
                min(
                    previous[j - 1] + (original_token != transformed_token),
                    previous[j] + 1,
                    current[j - 1] + 1,
                )
            )
        previous = current
    return previous[-1]


def _replay_steps(original: tuple[int, ...], transformed: tuple[int, ...]):
    result = align_tokens(original, transformed)
    rebuilt_original: list[int] = []
    rebuilt_transformed: list[int] = []
    for step in result.steps:
        if step.op is AlignmentOp.MATCH:
            rebuilt_original.append(step.original_token)
            rebuilt_transformed.append(step.transformed_token)
        elif step.op is AlignmentOp.SUBSTITUTE:
            rebuilt_original.append(step.original_token)
            rebuilt_transformed.append(step.transformed_token)
        elif step.op is AlignmentOp.DELETE:
            rebuilt_original.append(step.original_token)
        else:
            rebuilt_transformed.append(step.transformed_token)
    return result, tuple(rebuilt_original), tuple(rebuilt_transformed)


def _brute_changed_starts(original: tuple[int, ...], transformed: tuple[int, ...], ngram_len: int) -> set[int]:
    count = max(0, len(original) - ngram_len + 1)
    return {
        start
        for start in range(count)
        if original[start : start + ngram_len] != transformed[start : start + ngram_len]
    }


def _interval_starts(token_count: int, ngram_len: int, edited_positions: tuple[int, ...]) -> set[int]:
    intervals = tuple(
        substitution_observation_interval(position, token_count, ngram_len)
        for position in edited_positions
    )
    output: set[int] = set()
    for interval in merge_intervals(intervals):
        output.update(range(interval.start, interval.end_exclusive))
    return output


def test_small_binary_alignments_match_independent_edit_distance_and_replay() -> None:
    sequences = [
        tuple(values)
        for length in range(5)
        for values in product((0, 1), repeat=length)
    ]
    for original in sequences:
        for transformed in sequences:
            result, rebuilt_original, rebuilt_transformed = _replay_steps(original, transformed)
            assert result.distance == _reference_distance(original, transformed)
            assert rebuilt_original == original
            assert rebuilt_transformed == transformed
            assert len(result.steps) <= len(original) + len(transformed)


def test_conserved_runs_are_maximal_contiguous_exact_matches_exhaustively() -> None:
    sequences = [
        tuple(values)
        for length in range(5)
        for values in product((0, 1), repeat=length)
    ]
    for original in sequences:
        for transformed in sequences:
            result = align_tokens(original, transformed)
            runs = conserved_runs(result)
            covered_pairs: list[tuple[int, int]] = []
            for original_start, original_end, transformed_start, transformed_end in runs:
                assert original_end - original_start == transformed_end - transformed_start
                assert original[original_start:original_end] == transformed[transformed_start:transformed_end]
                covered_pairs.extend(
                    (original_start + offset, transformed_start + offset)
                    for offset in range(original_end - original_start)
                )
            expected_pairs = [
                (step.original_index, step.transformed_index)
                for step in result.steps
                if step.op is AlignmentOp.MATCH
            ]
            assert covered_pairs == expected_pairs
            for left, right in zip(runs, runs[1:]):
                assert left[1] != right[0] or left[3] != right[2]


def test_unchanged_token_sequences_have_zero_observation_replacement() -> None:
    for length in range(1, 8):
        for values in product((0, 1), repeat=min(length, 4)):
            tokens = tuple(values) if length <= 4 else tuple(range(length))
            for ngram_len in range(2, 6):
                alignment = align_tokens(tokens, tokens)
                diffs = structural_observation_diff(tokens, tokens, ngram_len, alignment)
                summary = summarize_structural_observations(tokens, tokens, ngram_len, diffs)
                assert summary.replaced_count == 0
                assert summary.unmapped_count == 0
                assert summary.preserved_count == summary.original_count
                assert summary.replacement_ratio == 0.0


def test_substitution_interval_union_equals_brute_force_changed_ngrams() -> None:
    for token_count in range(1, 9):
        original = tuple(range(token_count))
        for ngram_len in range(2, 6):
            for edit_count in range(min(4, token_count) + 1):
                for edited_positions in combinations(range(token_count), edit_count):
                    transformed = list(original)
                    for position in edited_positions:
                        transformed[position] = original[position] + token_count + 11
                    transformed_tuple = tuple(transformed)
                    expected = _brute_changed_starts(original, transformed_tuple, ngram_len)
                    actual = _interval_starts(token_count, ngram_len, edited_positions)
                    assert actual == expected
                    assert union_size(
                        substitution_observation_interval(position, token_count, ngram_len)
                        for position in edited_positions
                    ) == len(expected)


def test_pure_substitution_preserved_ngrams_keep_identical_g_vectors() -> None:
    adapter = DeepMindReferenceAdapter(
        DeepMindReferenceConfig(ngram_len=3, keys=(7, 11, 13), context_history_size=32)
    )
    for token_count in range(3, 9):
        original = tuple(range(10, 10 + token_count))
        original_g = adapter.compute_g_values(original)
        for position in range(token_count):
            transformed = list(original)
            transformed[position] += 1000
            transformed_tuple = tuple(transformed)
            transformed_g = adapter.compute_g_values(transformed_tuple)
            alignment = align_tokens(original, transformed_tuple)
            diffs = structural_observation_diff(original, transformed_tuple, 3, alignment)
            for diff in diffs:
                if diff.state is StructuralObservationState.PRESERVED:
                    assert diff.transformed_index is not None
                    assert original_g[diff.original_index] == transformed_g[diff.transformed_index]


def test_substitution_coverage_union_is_monotonic_for_all_small_edit_sets() -> None:
    for token_count in range(1, 9):
        for ngram_len in range(2, 6):
            positions = tuple(range(token_count))
            for count in range(token_count + 1):
                for selected in combinations(positions, count):
                    selected_size = union_size(
                        substitution_observation_interval(position, token_count, ngram_len)
                        for position in selected
                    )
                    for extra in positions:
                        if extra in selected:
                            continue
                        expanded_size = union_size(
                            substitution_observation_interval(position, token_count, ngram_len)
                            for position in (*selected, extra)
                        )
                        assert expanded_size >= selected_size
