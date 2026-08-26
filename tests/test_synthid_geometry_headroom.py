from dataclasses import replace

import pytest

from fuckmark.coverage import Interval
from fuckmark.experiments.synthid_geometry_headroom import (
    HeadroomBudgetStatus,
    analyze_geometry_headroom,
    build_public_eligibility_geometry_headroom,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import (
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    historical_visible_edit_transform_registry,
)


def _inputs():
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(
        "We do not panic. We should not drift. We cannot ignore evidence."
    )
    candidate_ids = tuple(sorted(candidate.candidate_id for candidate in enumeration.candidates))
    assert len(candidate_ids) == 3
    all_coverage = {
        candidate_ids[0]: (Interval(0, 5),),
        candidate_ids[1]: (Interval(5, 9),),
        candidate_ids[2]: (Interval(9, 12),),
    }
    eligible_coverage = {
        candidate_ids[0]: (Interval(0, 1),),
        candidate_ids[1]: (Interval(5, 9),),
        candidate_ids[2]: (),
    }
    all_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=all_coverage,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    eligible_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=eligible_coverage,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    return all_input, eligible_input


def test_headroom_detects_rank_and_greedy_disagreement() -> None:
    all_input, eligible_input = _inputs()
    report = analyze_geometry_headroom(
        all_input,
        eligible_input,
        budgets=(1, 2),
        seed=17,
    )
    assert report.summary.candidate_count == 3
    assert report.summary.all_positive_candidate_count == 3
    assert report.summary.eligible_positive_candidate_count == 2
    assert report.summary.positive_all_zero_eligible_candidate_count == 1
    assert report.summary.top_positive_candidate_same is False
    assert report.summary.spearman_rank_correlation is not None
    assert report.summary.mean_absolute_rank_displacement > 0.0
    assert report.summary.scheduled_budget_count == 2
    assert report.summary.greedy_selection_disagreement_count >= 1
    assert report.summary.exact_budget_count == 2
    assert report.summary.exact_selection_disagreement_count >= 1
    budget_one = report.budget_rows[0]
    assert budget_one.status is HeadroomBudgetStatus.SCHEDULED
    assert budget_one.greedy_same_selection is False
    assert budget_one.exact_diagnostic_available is True
    assert budget_one.exact_same_selection is False
    assert budget_one.all_greedy_regret == 0
    assert budget_one.eligible_greedy_regret == 0


def test_headroom_marks_empty_eligible_geometry_without_forcing_schedule() -> None:
    all_input, eligible_input = _inputs()
    empty = KeyBlindScheduleInput.from_enumeration(
        historical_visible_edit_transform_registry().enumerate(
            "We do not panic. We should not drift. We cannot ignore evidence."
        ),
        coverage_intervals={candidate.candidate_id: () for candidate in eligible_input.candidates},
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    report = analyze_geometry_headroom(all_input, empty, budgets=(1,))
    row = report.budget_rows[0]
    assert row.status is HeadroomBudgetStatus.ELIGIBLE_EMPTY
    assert row.greedy_same_selection is None
    assert row.exact_diagnostic_available is False
    assert report.summary.eligible_positive_candidate_count == 0


def test_headroom_report_is_content_addressed() -> None:
    all_input, eligible_input = _inputs()
    report = analyze_geometry_headroom(all_input, eligible_input, budgets=(1,))
    with pytest.raises(ValueError, match="report_hash"):
        replace(report, eligible_input_hash=sha256_text("tampered"))
    with pytest.raises(ValueError, match="row_hash"):
        replace(report.rank_rows[0], eligible_coverage=0)


def test_source_builder_uses_public_eligibility_geometry() -> None:
    registry = historical_visible_edit_transform_registry()
    vocabulary = {}

    def tokenize(text: str):
        output = []
        for piece in text.replace(".", " .").split():
            if piece not in vocabulary:
                vocabulary[piece] = len(vocabulary) + 1
            output.append(vocabulary[piece])
        return tuple(output)

    report = build_public_eligibility_geometry_headroom(
        "We do not panic. We should not drift. We cannot ignore evidence.",
        tokenize,
        9999,
        3,
        8,
        registry,
        budgets=(1,),
    )
    assert report.summary.candidate_count == 3
    assert report.summary.budget_count == 1


def test_headroom_rejects_mismatched_candidate_geometry() -> None:
    all_input, _ = _inputs()
    registry = historical_visible_edit_transform_registry()
    other_enumeration = registry.enumerate(
        "We do not stop. We should not wait. We cannot ignore facts."
    )
    other_coverage = {
        candidate.candidate_id: (Interval(index, index + 1),)
        for index, candidate in enumerate(other_enumeration.candidates)
    }
    other_input = KeyBlindScheduleInput.from_enumeration(
        other_enumeration,
        coverage_intervals=other_coverage,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    with pytest.raises(ValueError, match="candidate enumeration"):
        analyze_geometry_headroom(all_input, other_input, budgets=(1,))
