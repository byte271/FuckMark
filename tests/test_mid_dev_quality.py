from fuckmark.experiments.mid_dev_quality import protected_span_violation_count


def test_protected_span_violation_count_counts_removed_protected_content() -> None:
    assert protected_span_violation_count("call 555 now", "call five now") == 1


def test_protected_span_violation_count_counts_added_protected_content() -> None:
    assert protected_span_violation_count("alpha beta", "alpha 42 beta") == 1


def test_protected_span_violation_count_is_symmetric_under_exchange() -> None:
    source = "alpha beta"
    transformed = "alpha 42 beta"
    assert protected_span_violation_count(source, transformed) == protected_span_violation_count(
        transformed, source
    )


def test_protected_span_violation_count_counts_multiplicity_changes() -> None:
    assert protected_span_violation_count("row 7", "row 7 7") == 1
    assert protected_span_violation_count("row 7 7", "row 7") == 1


def test_protected_span_violation_count_is_zero_when_unchanged() -> None:
    assert protected_span_violation_count("call 555 now", "call 555 now") == 0
