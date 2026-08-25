from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

from .._validation import require_clean_string, require_int, require_sha256
from ..experiments.cover_greedy_v4 import schedule_cover_greedy_v4
from ..geometry.counterfactual import CounterfactualGeometryEngine, GeometryConfig
from ..geometry.repetition import PublicRepetitionGeometry
from ..geometry.tuple_closure import compute_tuple_closure
from ..hashing import sha256_json, sha256_text
from ..transforms.registry import TransformRegistry
from ..transforms.schema import CandidateRejectionReason
from .whitespace_collapse import collapse_horizontal_ascii_whitespace


CYCLE7_INSTRUMENTATION_VERSION = "cycle7-arm-instrumentation-v1"


@dataclass(frozen=True, slots=True)
class Cycle7ArmMeasurement:
    algorithm_version: str
    arm_id: str
    source_sample_id: str
    source_text_hash: str
    candidate_count: int
    selected_count: int
    selected_rule_ids: tuple[str, ...]
    budget: int
    budget_exhausted: bool
    candidate_exhausted: bool
    rejection_counts: dict[str, int]
    protected_blocked_count: int
    quote_blocked_count: int
    conflict_excluded_count: int
    unselected_count: int
    token_count_source: int
    token_count_transformed: int
    token_count_collapsed: int
    token_delta: int
    collapsed_token_delta: int
    changed_token_positions: int
    root_window_count: int
    intact_window_count: int
    tuple_leak_window_count: int
    closure_free: bool
    collapsed_intact_window_count: int
    collapsed_tuple_leak_window_count: int
    collapsed_closure_free: bool
    collapsed_equals_collapsed_source: bool
    reachable_unselected_static_cover: int
    failure_classes: tuple[str, ...]
    transformed_text: str
    collapsed_text: str
    measurement_hash: str

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "arm_id": self.arm_id,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "selected_rule_ids": self.selected_rule_ids,
            "budget": self.budget,
            "budget_exhausted": self.budget_exhausted,
            "candidate_exhausted": self.candidate_exhausted,
            "rejection_counts": self.rejection_counts,
            "protected_blocked_count": self.protected_blocked_count,
            "quote_blocked_count": self.quote_blocked_count,
            "conflict_excluded_count": self.conflict_excluded_count,
            "unselected_count": self.unselected_count,
            "token_count_source": self.token_count_source,
            "token_count_transformed": self.token_count_transformed,
            "token_count_collapsed": self.token_count_collapsed,
            "token_delta": self.token_delta,
            "collapsed_token_delta": self.collapsed_token_delta,
            "changed_token_positions": self.changed_token_positions,
            "root_window_count": self.root_window_count,
            "intact_window_count": self.intact_window_count,
            "tuple_leak_window_count": self.tuple_leak_window_count,
            "closure_free": self.closure_free,
            "collapsed_intact_window_count": self.collapsed_intact_window_count,
            "collapsed_tuple_leak_window_count": self.collapsed_tuple_leak_window_count,
            "collapsed_closure_free": self.collapsed_closure_free,
            "collapsed_equals_collapsed_source": self.collapsed_equals_collapsed_source,
            "reachable_unselected_static_cover": self.reachable_unselected_static_cover,
            "failure_classes": self.failure_classes,
            "transformed_text_hash": sha256_text(self.transformed_text),
            "collapsed_text_hash": sha256_text(self.collapsed_text),
        }


def _encode(tokenizer: Any, text: str) -> tuple[int, ...]:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return tuple(int(value) for value in ids)


def _changed_positions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    shared = min(len(left), len(right))
    changed = sum(left[index] != right[index] for index in range(shared))
    return changed + abs(len(left) - len(right))


def _rejection_counts(enumeration) -> dict[str, int]:
    counts: Counter[str] = Counter(rejection.reason.value for rejection in enumeration.rejections)
    return {reason.value: int(counts.get(reason.value, 0)) for reason in CandidateRejectionReason}


def _failure_classes(measurement_fields: dict[str, Any]) -> tuple[str, ...]:
    labels: list[str] = []
    if measurement_fields["candidate_count"] == 0:
        labels.append("insufficient_transform_density")
    elif measurement_fields["selected_count"] == 0:
        labels.append("insufficient_editable_reachability")
    if measurement_fields["budget_exhausted"]:
        labels.append("budget_exhaustion")
    if measurement_fields["candidate_exhausted"]:
        labels.append("candidate_exhaustion")
    if measurement_fields["protected_blocked_count"] > 0 and measurement_fields["selected_count"] == 0:
        labels.append("protected_spans")
    if measurement_fields["quote_blocked_count"] > 0 and measurement_fields["selected_count"] == 0:
        labels.append("quote_boundaries")
    if (
        measurement_fields["token_delta"] != 0
        and measurement_fields["tuple_leak_window_count"] > 0
        and measurement_fields["intact_window_count"] == 0
    ):
        labels.append("repeated_ngram_or_tuple_survival")
    if (
        measurement_fields["token_delta"] != 0
        and measurement_fields["intact_window_count"] > 0
        and measurement_fields["tuple_leak_window_count"] > 0
    ):
        labels.append("tokenizer_resynchronization_or_long_range_recovery")
    if (
        measurement_fields["collapsed_equals_collapsed_source"]
        and measurement_fields["token_delta"] != 0
    ):
        labels.append("whitespace_only_channel")
    if (
        measurement_fields["reachable_unselected_static_cover"] > 0
        and not measurement_fields["budget_exhausted"]
        and not measurement_fields["closure_free"]
    ):
        labels.append("possible_scheduler_headroom")
    if not labels and not measurement_fields["closure_free"]:
        labels.append("residual_geometry")
    return tuple(labels)


def measure_arm(
    *,
    arm_id: str,
    source_sample_id: str,
    source_text: str,
    registry: TransformRegistry,
    tokenizer: Any,
    tokenizer_identity_hash: str,
    ngram_len: int = 5,
    budget: int = 14,
) -> Cycle7ArmMeasurement:
    require_clean_string("arm_id", arm_id)
    require_clean_string("source_sample_id", source_sample_id)
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    require_int("ngram_len", ngram_len)
    require_int("budget", budget)
    enumeration = registry.enumerate(source_text)
    scheduled = schedule_cover_greedy_v4(
        source_sample_id=source_sample_id,
        source_text=source_text,
        registry=registry,
        enumeration=enumeration,
        tokenizer=tokenizer,
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        budget=budget,
    )
    transformed = registry.apply(enumeration, scheduled.selected_candidate_ids)
    collapsed = collapse_horizontal_ascii_whitespace(transformed.output_text)
    collapsed_source = collapse_horizontal_ascii_whitespace(source_text)
    source_tokens = _encode(tokenizer, source_text)
    transformed_tokens = _encode(tokenizer, transformed.output_text)
    collapsed_tokens = _encode(tokenizer, collapsed)
    selected_rules = tuple(
        candidate.rule_id
        for candidate in enumeration.candidates
        if candidate.candidate_id in set(scheduled.selected_candidate_ids)
    )
    rejections = _rejection_counts(enumeration)
    remaining_unselected = set(scheduled.unselected_candidate_ids) - set(
        scheduled.conflict_excluded_candidate_ids
    )
    candidate_exhausted = (
        scheduled.selected_candidate_count < budget
        and not scheduled.closure_free
        and not remaining_unselected
    )
    repetition = PublicRepetitionGeometry.create(ngram_len=ngram_len, context_history_size=1024)
    config = GeometryConfig.create(
        tokenizer_identity_hash=tokenizer_identity_hash,
        ngram_len=ngram_len,
        repetition_mask_policy_id=repetition.policy_id,
    )
    engine = CounterfactualGeometryEngine(
        tokenizer=tokenizer,
        config=config,
        eligibility_policy=repetition.eligibility_policy,
    )
    root = engine.build_root(source_sample_id=source_sample_id, source_text=source_text)
    collapsed_eval = engine.evaluate_output(
        root=root,
        current_text=source_text,
        output_text=collapsed,
        candidate_id=sha256_json(("cycle7-collapse", source_sample_id, arm_id)),
        rule_hash=registry.ruleset_hash,
        visible_cost_class=0,
        family="cycle7-collapse",
        tier=0,
    )
    collapsed_closure = compute_tuple_closure(
        root=root.observations,
        transformed_tokens=collapsed_tokens,
        expected_output_token_hash=collapsed_eval.output_token_hash,
    )
    reachable = 0
    if remaining_unselected and not scheduled.closure_free:
        reachable = len(remaining_unselected)
    fields = {
        "candidate_count": scheduled.candidate_count,
        "selected_count": scheduled.selected_candidate_count,
        "budget_exhausted": scheduled.budget_exhausted,
        "candidate_exhausted": candidate_exhausted,
        "protected_blocked_count": rejections[CandidateRejectionReason.PROTECTED_OVERLAP.value],
        "quote_blocked_count": rejections[CandidateRejectionReason.QUOTE_POLICY_BLOCKED.value],
        "token_delta": len(transformed_tokens) - len(source_tokens),
        "tuple_leak_window_count": scheduled.tuple_leak_window_count,
        "intact_window_count": scheduled.intact_window_count,
        "closure_free": scheduled.closure_free,
        "collapsed_equals_collapsed_source": collapsed == collapsed_source,
        "reachable_unselected_static_cover": reachable,
    }
    measurement = Cycle7ArmMeasurement(
        algorithm_version=CYCLE7_INSTRUMENTATION_VERSION,
        arm_id=arm_id,
        source_sample_id=source_sample_id,
        source_text_hash=sha256_text(source_text),
        candidate_count=scheduled.candidate_count,
        selected_count=scheduled.selected_candidate_count,
        selected_rule_ids=selected_rules,
        budget=budget,
        budget_exhausted=scheduled.budget_exhausted,
        candidate_exhausted=candidate_exhausted,
        rejection_counts=rejections,
        protected_blocked_count=fields["protected_blocked_count"],
        quote_blocked_count=fields["quote_blocked_count"],
        conflict_excluded_count=len(scheduled.conflict_excluded_candidate_ids),
        unselected_count=len(scheduled.unselected_candidate_ids),
        token_count_source=len(source_tokens),
        token_count_transformed=len(transformed_tokens),
        token_count_collapsed=len(collapsed_tokens),
        token_delta=fields["token_delta"],
        collapsed_token_delta=len(collapsed_tokens) - len(source_tokens),
        changed_token_positions=_changed_positions(source_tokens, transformed_tokens),
        root_window_count=scheduled.root_window_count,
        intact_window_count=scheduled.intact_window_count,
        tuple_leak_window_count=scheduled.tuple_leak_window_count,
        closure_free=scheduled.closure_free,
        collapsed_intact_window_count=collapsed_eval.surviving_count,
        collapsed_tuple_leak_window_count=collapsed_closure.leaked_window_count,
        collapsed_closure_free=collapsed_closure.closure_free,
        collapsed_equals_collapsed_source=fields["collapsed_equals_collapsed_source"],
        reachable_unselected_static_cover=reachable,
        failure_classes=_failure_classes(fields),
        transformed_text=transformed.output_text,
        collapsed_text=collapsed,
        measurement_hash="0" * 64,
    )
    return replace(measurement, measurement_hash=sha256_json(measurement.payload()))
