from dataclasses import fields, replace

import pytest

from fuckmark.transforms.candidate_artifacts import CandidateEnumeration
from fuckmark.transforms.registry import TransformRegistry, default_transform_registry
from fuckmark.transforms.rules import LiteralTransformRule
from fuckmark.transforms.scheduler import (
    CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
    CandidateScheduler,
    KeyBlindScheduleInput,
    SchedulePolicy,
)
from fuckmark.transforms.schema import TransformFamily, TransformTier


def _enumeration():
    registry = default_transform_registry()
    enumeration = registry.enumerate("Do not panic. Will not break. Should not drift.")
    assert len(enumeration.candidates) == 3
    return registry, enumeration


def _costs(enumeration: CandidateEnumeration) -> dict[str, int]:
    by_source = {"Do not": 2, "Will not": 1, "Should not": 2}
    return {
        candidate.candidate_id: by_source[candidate.source_text]
        for candidate in enumeration.candidates
    }


def test_scheduler_input_is_explicitly_key_blind() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    names = {field.name for field in fields(KeyBlindScheduleInput)}
    assert names == {
        "algorithm_version",
        "input_hash",
        "enumeration_hash",
        "budget_unit",
        "candidates",
        "conflicts",
        "input_artifact_hash",
    }
    forbidden = {"key", "g_values", "detector_score", "detector_decision", "checkpoint"}
    assert names.isdisjoint(forbidden)
    assert scheduler_input.enumeration_hash == enumeration.enumeration_hash


def test_left_to_right_schedule_uses_geometry_and_exact_budget() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        _costs(enumeration),
        budget_unit="character-edit-cost",
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=3,
        seed=7,
    )
    by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    assert tuple(by_id[value].source_text for value in result.considered_candidate_ids) == (
        "Do not",
        "Will not",
        "Should not",
    )
    assert tuple(by_id[value].source_text for value in result.selected_candidate_ids) == (
        "Do not",
        "Will not",
    )
    assert tuple(by_id[value].source_text for value in result.budget_skipped_candidate_ids) == (
        "Should not",
    )
    assert result.total_cost == 3
    assert result.budget == 3


def test_budget_one_under_never_exceeds_budget_and_can_skip_to_cheaper_candidate() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(
        enumeration,
        _costs(enumeration),
        budget_unit="character-edit-cost",
    )
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=1,
    )
    by_id = {candidate.candidate_id: candidate for candidate in enumeration.candidates}
    assert tuple(by_id[value].source_text for value in result.selected_candidate_ids) == ("Will not",)
    assert result.total_cost == 1
    assert set(by_id[value].source_text for value in result.budget_skipped_candidate_ids) == {
        "Do not",
        "Should not",
    }


def test_random_valid_schedule_replays_byte_identically_for_same_seed() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    first = scheduler.schedule(scheduler_input, SchedulePolicy.RANDOM_VALID, budget=2, seed=12345)
    for _ in range(20):
        assert scheduler.schedule(scheduler_input, SchedulePolicy.RANDOM_VALID, budget=2, seed=12345) == first
    assert first.algorithm_version == CANDIDATE_SCHEDULER_ALGORITHM_VERSION
    assert first.total_cost == 2


def test_random_valid_seed_changes_deterministic_candidate_order() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    orders = {
        scheduler.schedule(scheduler_input, SchedulePolicy.RANDOM_VALID, budget=3, seed=seed).considered_candidate_ids
        for seed in range(12)
    }
    assert len(orders) > 1


def test_overlapping_candidates_are_never_selected_together() -> None:
    rules = (
        LiteralTransformRule.create(
            "long",
            "v1",
            TransformFamily.CONTRACTION,
            TransformTier.SURFACE,
            "do not",
            "don't",
        ),
        LiteralTransformRule.create(
            "short",
            "v1",
            TransformFamily.CONTRACTION,
            TransformTier.SURFACE,
            "not",
            "never",
        ),
    )
    enumeration = TransformRegistry(rules).enumerate("do not")
    assert len(enumeration.candidates) == 2
    assert len(enumeration.conflicts) == 1
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=2,
    )
    assert len(result.selected_candidate_ids) == 1
    assert len(result.conflict_skipped_candidate_ids) == 1
    conflict = enumeration.conflicts[0]
    assert not {
        conflict.first_candidate_id,
        conflict.second_candidate_id,
    } <= set(result.selected_candidate_ids)


def test_scheduler_plan_can_drive_existing_transform_apply_without_secret_feedback() -> None:
    registry, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    plan = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=2,
        seed=9,
    )
    result = registry.apply(enumeration, plan.selected_candidate_ids, seed=plan.seed)
    assert result.output_text == "Don't panic. Won't break. Should not drift."
    assert result.trace.selected_candidate_ids == plan.selected_candidate_ids


def test_scheduler_rejects_incomplete_cost_map_and_invalid_budget_seed() -> None:
    _, enumeration = _enumeration()
    first = enumeration.candidates[0]
    with pytest.raises(ValueError, match="exactly"):
        KeyBlindScheduleInput.from_enumeration(enumeration, {first.candidate_id: 1})
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    scheduler = CandidateScheduler()
    with pytest.raises(ValueError, match="non-negative"):
        scheduler.schedule(scheduler_input, SchedulePolicy.LEFT_TO_RIGHT, -1)
    with pytest.raises(ValueError, match="2\^64"):
        scheduler.schedule(scheduler_input, SchedulePolicy.LEFT_TO_RIGHT, 1, seed=1 << 64)


def test_schedule_result_and_input_hashes_reject_tampering() -> None:
    _, enumeration = _enumeration()
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    result = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=2,
    )
    with pytest.raises(ValueError, match="input_artifact_hash"):
        replace(scheduler_input, budget_unit="other")
    with pytest.raises(ValueError, match="result_hash"):
        replace(result, budget=3)
