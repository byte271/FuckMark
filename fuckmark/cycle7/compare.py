from __future__ import annotations

from typing import Any

from ..experiments.cycle6_confirmation import CYCLE6_BUDGET
from ..hashing import sha256_json, sha256_text
from ..transforms import quote_safe_zrd_transform_registry
from .fixtures import fixture_samples
from .instrumentation import Cycle7ArmMeasurement, measure_arm
from .registry import cycle7_combined_transform_registry, cycle7_durable_transform_registry


CYCLE7_STAGE_A_COMPARE_VERSION = "cycle7-stage-a-fixture-compare-v1"
CYCLE6_SPACING_ARM_ID = "cycle6_spacing_b14"
CYCLE7_DURABLE_ARM_ID = "cycle7_durable"
CYCLE7_COMBINED_ARM_ID = "cycle7_combined"


def _registries():
    return {
        CYCLE6_SPACING_ARM_ID: quote_safe_zrd_transform_registry(),
        CYCLE7_DURABLE_ARM_ID: cycle7_durable_transform_registry(),
        CYCLE7_COMBINED_ARM_ID: cycle7_combined_transform_registry(),
    }


def compare_arms_on_text(
    *,
    source_sample_id: str,
    source_text: str,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    budget: int = CYCLE6_BUDGET,
) -> dict[str, Cycle7ArmMeasurement]:
    return {
        arm_id: measure_arm(
            arm_id=arm_id,
            source_sample_id=source_sample_id,
            source_text=source_text,
            registry=registry,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
            budget=budget,
        )
        for arm_id, registry in _registries().items()
    }


def summarize_arm(measurement: Cycle7ArmMeasurement) -> dict[str, object]:
    return {
        "arm_id": measurement.arm_id,
        "candidate_count": measurement.candidate_count,
        "selected_count": measurement.selected_count,
        "selected_rule_ids": measurement.selected_rule_ids,
        "budget_exhausted": measurement.budget_exhausted,
        "candidate_exhausted": measurement.candidate_exhausted,
        "protected_blocked_count": measurement.protected_blocked_count,
        "quote_blocked_count": measurement.quote_blocked_count,
        "token_delta": measurement.token_delta,
        "collapsed_token_delta": measurement.collapsed_token_delta,
        "changed_token_positions": measurement.changed_token_positions,
        "root_window_count": measurement.root_window_count,
        "intact_window_count": measurement.intact_window_count,
        "tuple_leak_window_count": measurement.tuple_leak_window_count,
        "closure_free": measurement.closure_free,
        "collapsed_intact_window_count": measurement.collapsed_intact_window_count,
        "collapsed_tuple_leak_window_count": measurement.collapsed_tuple_leak_window_count,
        "collapsed_closure_free": measurement.collapsed_closure_free,
        "collapsed_equals_collapsed_source": measurement.collapsed_equals_collapsed_source,
        "reachable_unselected_static_cover": measurement.reachable_unselected_static_cover,
        "failure_classes": measurement.failure_classes,
        "measurement_hash": measurement.measurement_hash,
    }


def run_fixture_stage_a(
    tokenizer: Any,
    tokenizer_identity_hash: str | None = None,
) -> dict[str, object]:
    if tokenizer_identity_hash is None:
        tokenizer_identity_hash = sha256_text("cycle7-fixture-tokenizer")
    rows = []
    for sample_id, text in fixture_samples():
        arms = compare_arms_on_text(
            source_sample_id=sample_id,
            source_text=text,
            tokenizer=tokenizer,
            tokenizer_identity_hash=tokenizer_identity_hash,
        )
        rows.append(
            {
                "source_sample_id": sample_id,
                "source_text_hash": sha256_text(text),
                "arms": {arm_id: summarize_arm(measurement) for arm_id, measurement in arms.items()},
            }
        )
    payload = {
        "algorithm_version": CYCLE7_STAGE_A_COMPARE_VERSION,
        "budget": CYCLE6_BUDGET,
        "arm_ids": (CYCLE6_SPACING_ARM_ID, CYCLE7_DURABLE_ARM_ID, CYCLE7_COMBINED_ARM_ID),
        "rows": tuple(rows),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
