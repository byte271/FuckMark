from __future__ import annotations

from fuckmark.experiments.mid_dev_context_survival import MidDevCondition as BuilderCondition
from fuckmark.experiments.mid_dev_plan_builder import (
    MidDevSelectionTrace as BuilderTrace,
    MidDevSelectionTraceArtifact as BuilderTraceArtifact,
    _schedule_seed,
)
from fuckmark.experiments.mid_dev_scoring_contracts import MidDevCondition
from fuckmark.experiments.mid_dev_trace_schema import (
    MidDevSelectionTrace,
    MidDevSelectionTraceArtifact,
    mid_dev_schedule_seed,
)
from fuckmark.hashing import sha256_text


def test_middev_public_schedule_seed_replays_builder_derivation() -> None:
    sample_ids = tuple(f"sample-{index:03d}" for index in range(72))
    for sample_id in sample_ids:
        for condition in (
            BuilderCondition.CURRENT_STRONGEST_BASELINE,
            BuilderCondition.CONTEXT_SURVIVAL_GREEDY,
            BuilderCondition.CONTEXT_SURVIVAL_BEAM,
            BuilderCondition.EVEN_SPACING,
            BuilderCondition.RANDOM_SAFE,
        ):
            for budget in (1, 2, 4, 6):
                replicates = range(16) if condition is BuilderCondition.RANDOM_SAFE else (0,)
                neutral = MidDevCondition(condition.value)
                for replicate in replicates:
                    assert _schedule_seed(sample_id, condition, budget, replicate) == mid_dev_schedule_seed(
                        sample_id,
                        neutral,
                        budget,
                        replicate,
                    )


def test_middev_neutral_trace_schema_replays_builder_trace_hash() -> None:
    builder = BuilderTrace.create(
        source_group_id="match-middev-general-explanatory-000",
        sample_id="middev-general-explanatory-000-watermarked",
        condition=BuilderCondition.CONTEXT_SURVIVAL_BEAM,
        budget=4,
        replicate=0,
        schedule_seed=_schedule_seed(
            "middev-general-explanatory-000-watermarked",
            BuilderCondition.CONTEXT_SURVIVAL_BEAM,
            4,
            0,
        ),
        candidate_pool_hash=sha256_text("candidate-pool"),
        scheduler_input_hash=sha256_text("scheduler-input"),
        schedule_result_hash=sha256_text("schedule-result"),
        final_search_state_hash=sha256_text("search-state"),
        operation_hashes=(sha256_text("operation-1"), sha256_text("operation-2")),
        transition_hashes=(sha256_text("transition-1"), sha256_text("transition-2")),
        status="SUCCESS",
    )
    neutral = MidDevSelectionTrace(
        builder.source_group_id,
        builder.sample_id,
        MidDevCondition(builder.condition.value),
        builder.budget,
        builder.replicate,
        builder.schedule_seed,
        builder.candidate_pool_hash,
        builder.scheduler_input_hash,
        builder.schedule_result_hash,
        builder.final_search_state_hash,
        builder.operation_hashes,
        builder.transition_hashes,
        builder.status,
        builder.trace_hash,
    )
    assert neutral.payload() == builder.payload()
    assert neutral.trace_hash == builder.trace_hash

    plan_hash = sha256_text("plan")
    builder_artifact = BuilderTraceArtifact.create(plan_hash=plan_hash, traces=(builder,))
    neutral_artifact = MidDevSelectionTraceArtifact(
        builder_artifact.plan_hash,
        (neutral,),
        builder_artifact.artifact_hash,
    )
    assert neutral_artifact.payload() == builder_artifact.payload()
    assert neutral_artifact.artifact_hash == builder_artifact.artifact_hash
