from dataclasses import replace

import pytest

from fuckmark.corpus import KeySplit
from fuckmark.experiments.transform_provenance import (
    DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION,
    TransformProvenanceError,
    build_verified_transform_row,
    verify_transform_provenance,
)
from fuckmark.hashing import sha256_text
from fuckmark.transforms import CandidateScheduler, KeyBlindScheduleInput, SchedulePolicy, default_transform_registry


def _pipeline(text: str = "Do not panic. Will not break.", seed: int = 7, budget: int = 1):
    registry = default_transform_registry()
    enumeration = registry.enumerate(text)
    scheduler_input = KeyBlindScheduleInput.from_enumeration(enumeration)
    schedule = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=budget,
        seed=seed,
    )
    transformed = registry.apply(enumeration, schedule.selected_candidate_ids, seed=schedule.seed)
    return enumeration, scheduler_input, schedule, transformed


def test_verified_provenance_binds_enumeration_schedule_trace_and_output() -> None:
    text = "Do not panic. Will not break."
    enumeration, scheduler_input, schedule, transformed = _pipeline(text)
    provenance = verify_transform_provenance(
        "sample-1",
        "family-1",
        text,
        enumeration,
        scheduler_input,
        schedule,
        transformed,
    )
    assert provenance.algorithm_version == DEVELOPMENT_TRANSFORM_PROVENANCE_VERSION
    assert provenance.source_text_hash == sha256_text(text)
    assert provenance.transformed_text_hash == sha256_text(transformed.output_text)
    assert provenance.enumeration_hash == enumeration.enumeration_hash
    assert provenance.scheduler_input_hash == scheduler_input.input_artifact_hash
    assert provenance.schedule_result_hash == schedule.result_hash
    assert provenance.transform_result_hash == transformed.result_hash
    assert provenance.trace_hash == transformed.trace.trace_hash
    assert provenance.selected_candidate_ids == schedule.selected_candidate_ids
    assert provenance.eligible


def test_verified_row_derives_provenance_fields_instead_of_accepting_free_hashes() -> None:
    text = "Do not panic. Will not break."
    enumeration, scheduler_input, schedule, transformed = _pipeline(text)
    provenance = verify_transform_provenance(
        "sample-1",
        "family-1",
        text,
        enumeration,
        scheduler_input,
        schedule,
        transformed,
    )
    row = build_verified_transform_row(
        provenance,
        key_split=KeySplit.DEV,
        detector_identity_hash="a" * 64,
        threshold_hash="b" * 64,
        threshold_value=0.5,
        word_edit_count=1,
        word_count=20,
        observation_replacement_count=3,
        original_observation_count=18,
        pristine_score=0.9,
        transformed_score=0.7,
    )
    assert row.source_text_hash == provenance.source_text_hash
    assert row.transformed_text_hash == provenance.transformed_text_hash
    assert row.candidate_pool_hash == provenance.enumeration_hash
    assert row.scheduler_input_hash == provenance.scheduler_input_hash
    assert row.schedule_result_hash == provenance.schedule_result_hash
    assert row.schedule_policy is provenance.schedule_policy
    assert row.schedule_seed == provenance.schedule_seed
    assert row.realized_edit_cost == provenance.realized_edit_cost
    assert row.scheduler_covered_interval_size == provenance.scheduler_covered_interval_size


def test_provenance_rejects_schedule_from_different_seed_even_when_candidate_selection_matches() -> None:
    text = "Do not panic. Will not break."
    enumeration, scheduler_input, schedule, transformed = _pipeline(text, seed=7)
    other_schedule = CandidateScheduler().schedule(
        scheduler_input,
        SchedulePolicy.LEFT_TO_RIGHT,
        budget=schedule.budget,
        seed=8,
    )
    assert other_schedule.selected_candidate_ids == schedule.selected_candidate_ids
    with pytest.raises(TransformProvenanceError, match="seed"):
        verify_transform_provenance(
            "sample-1",
            "family-1",
            text,
            enumeration,
            scheduler_input,
            other_schedule,
            transformed,
        )


def test_provenance_rejects_source_text_mismatch() -> None:
    enumeration, scheduler_input, schedule, transformed = _pipeline()
    with pytest.raises(TransformProvenanceError, match="source text"):
        verify_transform_provenance(
            "sample-1",
            "family-1",
            "Different source text.",
            enumeration,
            scheduler_input,
            schedule,
            transformed,
        )


def test_ineligible_empty_selection_preserves_text_and_builds_zero_cost_policy_row() -> None:
    text = "Nothing eligible here."
    enumeration, scheduler_input, schedule, transformed = _pipeline(text, budget=3)
    assert schedule.selected_candidate_ids == ()
    assert transformed.output_text == text
    provenance = verify_transform_provenance(
        "sample-empty",
        "family-empty",
        text,
        enumeration,
        scheduler_input,
        schedule,
        transformed,
    )
    assert not provenance.eligible
    row = build_verified_transform_row(
        provenance,
        key_split=KeySplit.DEV,
        detector_identity_hash="a" * 64,
        threshold_hash="b" * 64,
        threshold_value=0.5,
        word_edit_count=0,
        word_count=10,
        observation_replacement_count=0,
        original_observation_count=8,
        pristine_score=0.4,
        transformed_score=0.4,
    )
    assert not row.eligible
    assert row.realized_edit_cost == 0
    assert row.source_text_hash == row.transformed_text_hash


def test_provenance_artifact_rejects_hash_tampering() -> None:
    text = "Do not panic."
    enumeration, scheduler_input, schedule, transformed = _pipeline(text)
    provenance = verify_transform_provenance(
        "sample-1",
        "family-1",
        text,
        enumeration,
        scheduler_input,
        schedule,
        transformed,
    )
    with pytest.raises(ValueError, match="provenance_hash"):
        replace(provenance, provenance_hash="f" * 64)
