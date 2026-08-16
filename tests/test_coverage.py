import pytest

from fuckmark.coverage import Interval, merge_intervals, substitution_observation_interval, union_size


def test_middle_substitution_interval_for_ngram_five() -> None:
    interval = substitution_observation_interval(5, 20, 5)
    assert interval == Interval(1, 6)
    assert interval.size == 5


def test_boundary_substitution_interval_is_clipped() -> None:
    assert substitution_observation_interval(0, 20, 5) == Interval(0, 1)
    assert substitution_observation_interval(19, 20, 5) == Interval(15, 16)


def test_short_sequence_has_empty_observation_interval() -> None:
    assert substitution_observation_interval(1, 3, 5) == Interval(0, 0)


def test_merge_intervals_combines_overlap_and_touching_ranges() -> None:
    merged = merge_intervals([Interval(1, 4), Interval(3, 6), Interval(6, 8), Interval(10, 11)])
    assert merged == (Interval(1, 8), Interval(10, 11))


def test_union_size_does_not_double_count_overlap() -> None:
    assert union_size([Interval(1, 5), Interval(4, 8)]) == 7


def test_invalid_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        Interval(-1, 2)


def test_interval_rejects_non_integer_endpoints() -> None:
    with pytest.raises(TypeError):
        Interval(1.5, 2)
    with pytest.raises(TypeError):
        Interval(True, 2)


def test_substitution_interval_rejects_non_integer_inputs() -> None:
    with pytest.raises(TypeError):
        substitution_observation_interval(1, 20, 5.0)


def test_merge_intervals_rejects_wrong_value_type() -> None:
    with pytest.raises(TypeError):
        merge_intervals([Interval(0, 1), (1, 2)])
