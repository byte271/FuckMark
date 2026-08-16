from dataclasses import replace

import pytest

from fuckmark.coverage import Interval
from fuckmark.transforms.registry import default_transform_registry
from fuckmark.transforms.scheduler import (
    CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
    CandidateScheduler,
    KeyBlindScheduleInput,
    ScheduleGeometryMode,
    SchedulePolicy,
)


def _three_candidate_enumeration():
    enumeration = default_transform_registry().enumerate(
        "Do not panic. Will not break. Should not drift."
    )
    assert len(enumeration.candidates) == 3
    return enumeration


def _five_candidate_enumeration():
    enumeration = default_transform_registry().enumerate(
        "Do not xxxxxxxxxx. Will not yyyyyyyyyy. Should not zzzzzzzzzz. "
        "Cannot aaaaaaaaaa. Did not end."
    )
    assert len(enumeration.candidates) == 5
    assert not enumeration.conflicts
    return enumeration


def _candidate_by_source(enumeration):
    return {candidate.source_text: candidate for candidate in enumeration.candidates}


def test_clustered_and_even_spacing_share_anchor_but_freeze_opposite_topology() -> None:
    enumeration = _five_candidate_enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    clustered = scheduler.schedule(
        scheduler_input,
        SchedulePolicy.CLUSTERED,
        budget=3,
        seed=421,
    )
    even = scheduler.schedule(
        scheduler_input,
        SchedulePolicy.EVEN_SPACING,
        budget=3,
        seed=421,
    )
    by_id = {candidate.candidate_id: candidate for candidate in scheduler_input.candidates}
    assert clustered.selected_candidate_ids[0] == even.selected_candidate_ids[0]
    anchor = by_id[clustered.selected_candidate_ids[0]]
    remaining = tuple(
        candidate
        for candidate in scheduler_input.candidates
        if candidate.candidate_id != anchor.candidate_id
    )
    expected_cluster_second = min(
        remaining,
        key=lambda candidate: (
            abs(candidate.center_twice - anchor.center_twice),
            candidate.candidate_id,
        ),
    )
    expected_even_second = min(
        remaining,
        key=lambda candidate: (
            -abs(candidate.center_twice - anchor.center_twice),
            candidate.candidate_id,
        ),
    )
    assert clustered.selected_candidate_ids[1] == expected_cluster_second.candidate_id
    assert even.selected_candidate_ids[1] == expected_even_second.candidate_id
    assert clustered.total_cost == even.total_cost == 3


def test_even_spacing_uses_greedy_maximin_after_anchor() -> None:
    enumeration = _five_candidate_enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.EVEN_SPACING,
        budget=3,
        seed=17,
    )
    by_id = {candidate.candidate_id: candidate for candidate in scheduler_input.candidates}
    first = by_id[result.selected_candidate_ids[0]]
    second = by_id[result.selected_candidate_ids[1]]
    remaining = tuple(
        candidate
        for candidate in scheduler_input.candidates
        if candidate.candidate_id not in result.selected_candidate_ids[:2]
    )
    expected_third = min(
        remaining,
        key=lambda candidate: (
            -min(
                abs(candidate.center_twice - selected.center_twice)
                for selected in (first, second)
            ),
            candidate.candidate_id,
        ),
    )
    assert result.selected_candidate_ids[2] == expected_third.candidate_id


def test_spacing_schedules_replay_exactly() -> None:
    enumeration = _five_candidate_enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    for policy in (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING):
        expected = scheduler.schedule(scheduler_input, policy, budget=4, seed=999)
        for _ in range(20):
            assert scheduler.schedule(scheduler_input, policy, budget=4, seed=999) == expected


def test_coverage_greedy_uses_marginal_union_gain_per_cost() -> None:
    enumeration = _three_candidate_enumeration()
    by_source = _candidate_by_source(enumeration)
    costs = {
        by_source["Do not"].candidate_id: 2,
        by_source["Will not"].candidate_id: 1,
        by_source["Should not"].candidate_id: 1,
    }
    intervals = {
        by_source["Do not"].candidate_id: (Interval(0, 6),),
        by_source["Will not"].candidate_id: (Interval(0, 4),),
        by_source["Should not"].candidate_id: (Interval(4, 5),),
    }
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        costs,
        budget_unit="token-edit-cost",
        coverage_intervals=intervals,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        budget=2,
        seed=777,
    )
    assert result.selected_candidate_ids == (
        by_source["Will not"].candidate_id,
        by_source["Should not"].candidate_id,
    )
    assert result.budget_skipped_candidate_ids == (by_source["Do not"].candidate_id,)
    assert result.total_cost == 2
    assert result.covered_interval_size == 5
    assert result.policy_skipped_candidate_ids == ()


def test_coverage_greedy_ties_are_broken_only_by_candidate_id() -> None:
    enumeration = _three_candidate_enumeration()
    intervals = {
        candidate.candidate_id: (Interval(index * 2, index * 2 + 2),)
        for index, candidate in enumerate(enumeration.candidates)
    }
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=intervals,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        budget=1,
        seed=(1 << 64) - 1,
    )
    assert result.selected_candidate_ids == (
        min(candidate.candidate_id for candidate in enumeration.candidates),
    )


def test_coverage_greedy_stops_when_only_zero_marginal_gain_remains() -> None:
    enumeration = _three_candidate_enumeration()
    by_source = _candidate_by_source(enumeration)
    intervals = {
        by_source["Do not"].candidate_id: (Interval(0, 8),),
        by_source["Will not"].candidate_id: (Interval(0, 4),),
        by_source["Should not"].candidate_id: (Interval(4, 8),),
    }
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=intervals,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
        budget=3,
    )
    assert result.selected_candidate_ids == (by_source["Do not"].candidate_id,)
    assert set(result.policy_skipped_candidate_ids) == {
        by_source["Will not"].candidate_id,
        by_source["Should not"].candidate_id,
    }
    assert result.covered_interval_size == 8


def test_exact_coverage_diagnostic_quantifies_greedy_regret() -> None:
    enumeration = _three_candidate_enumeration()
    by_source = _candidate_by_source(enumeration)
    costs = {
        by_source["Do not"].candidate_id: 2,
        by_source["Will not"].candidate_id: 1,
        by_source["Should not"].candidate_id: 1,
    }
    intervals = {
        by_source["Do not"].candidate_id: (Interval(0, 6),),
        by_source["Will not"].candidate_id: (Interval(0, 4),),
        by_source["Should not"].candidate_id: (Interval(4, 5),),
    }
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        costs,
        coverage_intervals=intervals,
        geometry_mode=ScheduleGeometryMode.TOKENIZER_AWARE_PUBLIC,
    )
    diagnostic = CandidateScheduler().exact_coverage_diagnostic(
        scheduler_input,
        budget=2,
        seed=22,
    )
    assert diagnostic.algorithm_version == CANDIDATE_SCHEDULER_ALGORITHM_VERSION
    assert diagnostic.greedy_coverage == 5
    assert diagnostic.optimal_selected_candidate_ids == (by_source["Do not"].candidate_id,)
    assert diagnostic.optimal_cost == 2
    assert diagnostic.optimal_coverage == 6
    assert diagnostic.coverage_regret == 1
    with pytest.raises(ValueError, match="diagnostic_hash"):
        replace(diagnostic, optimal_coverage=7, coverage_regret=2)


def test_coverage_geometry_is_canonical_and_complete() -> None:
    enumeration = _three_candidate_enumeration()
    first = enumeration.candidates[0]
    with pytest.raises(ValueError, match="exactly"):
        KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals={first.candidate_id: (Interval(0, 1),)},
        )
    intervals = {
        candidate.candidate_id: (Interval(2, 4), Interval(0, 1))
        for candidate in enumeration.candidates
    }
    with pytest.raises(ValueError, match="canonical"):
        KeyBlindScheduleInput.from_enumeration(
            enumeration,
            coverage_intervals=intervals,
        )


def test_coverage_greedy_fails_closed_without_geometry() -> None:
    enumeration = _three_candidate_enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    with pytest.raises(ValueError, match="explicit key-blind coverage geometry"):
        CandidateScheduler().schedule(
            scheduler_input,
            SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
            budget=2,
        )


def test_empty_candidate_pool_is_valid_for_every_task25_policy() -> None:
    enumeration = default_transform_registry().enumerate("Nothing eligible is present.")
    assert not enumeration.candidates
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    for policy in (
        SchedulePolicy.CLUSTERED,
        SchedulePolicy.EVEN_SPACING,
        SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND,
    ):
        result = scheduler.schedule(scheduler_input, policy, budget=3, seed=4)
        assert result.considered_candidate_ids == ()
        assert result.selected_candidate_ids == ()
        assert result.total_cost == 0
        assert result.covered_interval_size == 0
    diagnostic = scheduler.exact_coverage_diagnostic(scheduler_input, budget=3)
    assert diagnostic.candidate_count == 0
    assert diagnostic.optimal_coverage == 0
    assert diagnostic.coverage_regret == 0


def test_exact_diagnostic_enforces_small_candidate_resource_limit() -> None:
    enumeration = _three_candidate_enumeration()
    intervals = {
        candidate.candidate_id: (Interval(index, index + 1),)
        for index, candidate in enumerate(enumeration.candidates)
    }
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        coverage_intervals=intervals,
    )
    with pytest.raises(ValueError, match="resource limit"):
        CandidateScheduler().exact_coverage_diagnostic(
            scheduler_input,
            budget=3,
            max_candidates=2,
        )
