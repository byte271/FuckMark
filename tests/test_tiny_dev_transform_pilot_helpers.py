import pytest

from fuckmark.tiny_dev_transform_hf import _schedule_seed, _word_edit_distance, _word_units


def test_word_units_ignore_spacing_only_changes() -> None:
    original = "This is a small test. It is useful."
    transformed = "This is  a small test.  It is  useful."
    assert _word_units(original) == _word_units(transformed)
    assert _word_edit_distance(original, transformed) == 0


def test_word_edit_distance_counts_contraction_geometry() -> None:
    assert _word_edit_distance("I do not agree", "I don't agree") == 2
    assert _word_edit_distance("alpha beta gamma", "alpha delta gamma") == 1


def test_schedule_seed_is_deterministic_and_coordinate_separated() -> None:
    assert _schedule_seed(0, 0, 0) == 61000
    values = {
        _schedule_seed(source, budget, replicate)
        for source in range(8)
        for budget in range(3)
        for replicate in range(9)
    }
    assert len(values) == 8 * 3 * 9
    assert _schedule_seed(3, 2, 7) == _schedule_seed(3, 2, 7)


def test_schedule_seed_rejects_negative_coordinates() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _schedule_seed(-1, 0, 0)
