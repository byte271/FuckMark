from __future__ import annotations

import json
from pathlib import Path

from .._validation import require_sha256
from ..config import canonical_json_text
from ..corpus.mid_dev import MID_DEV_SOURCE_COUNT
from ..corpus.schema import CorpusDomain, WatermarkLabel
from ..corpus.tiny_dev_io import _array, _mapping, _reject_constant, _unique_object
from .mid_dev_context_survival import (
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
    MidDevPlanRow,
    MidDevQualityRow,
    MidDevSelectionAttestation,
    MidDevSelectionConfig,
    _validate_plan_matrix,
)
from .mid_dev_freeze import (
    MidDevDeterministicComputeRow,
    MidDevDeterministicFrozenPlan,
)
from .mid_dev_plan_builder import (
    MidDevSelectionTrace,
    MidDevSelectionTraceArtifact,
    _schedule_seed,
)


MID_DEV_PLAN_JSON_MAX_BYTES = 512 * 1024 * 1024


class MidDevPlanJsonError(ValueError):
    pass


def _selection_config(value: object) -> MidDevSelectionConfig:
    data = _mapping(
        "selection_config",
        value,
        (
            "algorithm_version",
            "budgets",
            "beam_budgets",
            "random_replicates",
            "beam_width",
            "max_risk_tier",
            "beam_algorithm_version",
            "config_hash",
        ),
    )
    return MidDevSelectionConfig(
        algorithm_version=data["algorithm_version"],
        budgets=tuple(_array("selection_config.budgets", data["budgets"])),
        beam_budgets=tuple(_array("selection_config.beam_budgets", data["beam_budgets"])),
        random_replicates=data["random_replicates"],
        beam_width=data["beam_width"],
        max_risk_tier=data["max_risk_tier"],
        beam_algorithm_version=data["beam_algorithm_version"],
        config_hash=data["config_hash"],
    )


def _selection_attestation(value: object) -> MidDevSelectionAttestation:
    data = _mapping(
        "selection_attestation",
        value,
        (
            "algorithm_version",
            "attested_expander_count",
            "detector_access_observed",
            "secret_access_observed",
            "detector_query_count",
            "secret_query_count",
            "attestation_hash",
        ),
    )
    return MidDevSelectionAttestation(
        algorithm_version=data["algorithm_version"],
        attested_expander_count=data["attested_expander_count"],
        detector_access_observed=data["detector_access_observed"],
        secret_access_observed=data["secret_access_observed"],
        detector_query_count=data["detector_query_count"],
        secret_query_count=data["secret_query_count"],
        attestation_hash=data["attestation_hash"],
    )


def _plan_row(value: object) -> MidDevPlanRow:
    data = _mapping(
        "plan_row",
        value,
        (
            "source_group_id",
            "prompt_id",
            "sample_id",
            "source_label",
            "prompt_family_id",
            "domain",
            "target_length",
            "source_text_hash",
            "condition",
            "budget",
            "replicate",
            "transformed_text",
            "transformed_text_hash",
            "operation_count",
            "status",
            "selection_trace_hash",
            "plan_row_hash",
        ),
    )
    return MidDevPlanRow(
        source_group_id=data["source_group_id"],
        prompt_id=data["prompt_id"],
        sample_id=data["sample_id"],
        source_label=WatermarkLabel(data["source_label"]),
        prompt_family_id=data["prompt_family_id"],
        domain=CorpusDomain(data["domain"]),
        target_length=data["target_length"],
        source_text_hash=data["source_text_hash"],
        condition=MidDevCondition(data["condition"]),
        budget=data["budget"],
        replicate=data["replicate"],
        transformed_text=data["transformed_text"],
        transformed_text_hash=data["transformed_text_hash"],
        operation_count=data["operation_count"],
        status=data["status"],
        selection_trace_hash=data["selection_trace_hash"],
        plan_row_hash=data["plan_row_hash"],
    )


def _quality_row(value: object) -> MidDevQualityRow:
    data = _mapping(
        "quality_row",
        value,
        (
            "plan_row_hash",
            "word_edit_rate",
            "old_observation_replacement_ratio",
            "exact_destruction_ratio",
            "exact_survival_ratio",
            "token_edit_distance",
            "length_ratio",
            "numbers_preserved_fraction",
            "urls_preserved_fraction",
            "protected_span_violation_count",
            "hard_invariant_status",
            "quality_hash",
        ),
    )
    return MidDevQualityRow(
        plan_row_hash=data["plan_row_hash"],
        word_edit_rate=data["word_edit_rate"],
        old_observation_replacement_ratio=data["old_observation_replacement_ratio"],
        exact_destruction_ratio=data["exact_destruction_ratio"],
        exact_survival_ratio=data["exact_survival_ratio"],
        token_edit_distance=data["token_edit_distance"],
        length_ratio=data["length_ratio"],
        numbers_preserved_fraction=data["numbers_preserved_fraction"],
        urls_preserved_fraction=data["urls_preserved_fraction"],
        protected_span_violation_count=data["protected_span_violation_count"],
        hard_invariant_status=data["hard_invariant_status"],
        quality_hash=data["quality_hash"],
    )


def _compute_row(value: object) -> MidDevDeterministicComputeRow:
    data = _mapping(
        "compute_row",
        value,
        (
            "plan_row_hash",
            "expanded_state_count",
            "pruned_state_count",
            "candidate_evaluation_count",
            "expansion_cache_hit_count",
            "expansion_cache_miss_count",
            "geometry_cache_hit_count",
            "selection_detector_query_count",
            "selection_secret_query_count",
            "compute_hash",
        ),
    )
    return MidDevDeterministicComputeRow(
        plan_row_hash=data["plan_row_hash"],
        expanded_state_count=data["expanded_state_count"],
        pruned_state_count=data["pruned_state_count"],
        candidate_evaluation_count=data["candidate_evaluation_count"],
        expansion_cache_hit_count=data["expansion_cache_hit_count"],
        expansion_cache_miss_count=data["expansion_cache_miss_count"],
        geometry_cache_hit_count=data["geometry_cache_hit_count"],
        selection_detector_query_count=data["selection_detector_query_count"],
        selection_secret_query_count=data["selection_secret_query_count"],
        compute_hash=data["compute_hash"],
    )


def _plan(value: object) -> MidDevDeterministicFrozenPlan:
    data = _mapping(
        "plan",
        value,
        (
            "algorithm_version",
            "corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "source_code_commit",
            "selection_config",
            "selection_attestation",
            "rows",
            "quality_rows",
            "compute_rows",
            "plan_hash",
        ),
    )
    plan = MidDevDeterministicFrozenPlan(
        algorithm_version=data["algorithm_version"],
        corpus_artifact_hash=data["corpus_artifact_hash"],
        source_profile_hash=data["source_profile_hash"],
        analysis_split_hash=data["analysis_split_hash"],
        source_code_commit=data["source_code_commit"],
        selection_config=_selection_config(data["selection_config"]),
        selection_attestation=_selection_attestation(data["selection_attestation"]),
        rows=tuple(_plan_row(row) for row in _array("plan.rows", data["rows"])),
        quality_rows=tuple(
            _quality_row(row) for row in _array("plan.quality_rows", data["quality_rows"])
        ),
        compute_rows=tuple(
            _compute_row(row) for row in _array("plan.compute_rows", data["compute_rows"])
        ),
        plan_hash=data["plan_hash"],
    )
    _validate_plan_matrix(plan.rows)
    source_groups = {row.source_group_id for row in plan.rows}
    sample_ids = {row.sample_id for row in plan.rows}
    expected_rows = MID_DEV_SOURCE_COUNT * 2 * (
        1 + 4 * (2 + MID_DEV_RANDOM_REPLICATES + 1) + 2
    )
    if len(source_groups) != MID_DEV_SOURCE_COUNT:
        raise MidDevPlanJsonError("frozen MidDev plan must contain exactly 36 source groups")
    if len(sample_ids) != MID_DEV_SOURCE_COUNT * 2:
        raise MidDevPlanJsonError("frozen MidDev plan must contain exactly 72 source samples")
    if len(plan.rows) != expected_rows:
        raise MidDevPlanJsonError("frozen MidDev plan does not contain the exact 5688-row matrix")
    if plan.selection_attestation.attested_expander_count != len(sample_ids):
        raise MidDevPlanJsonError("selection attestation does not cover every MidDev sample expander")
    return plan


def _trace(value: object) -> MidDevSelectionTrace:
    data = _mapping(
        "selection_trace",
        value,
        (
            "source_group_id",
            "sample_id",
            "condition",
            "budget",
            "replicate",
            "schedule_seed",
            "candidate_pool_hash",
            "scheduler_input_hash",
            "schedule_result_hash",
            "final_search_state_hash",
            "operation_hashes",
            "transition_hashes",
            "status",
            "trace_hash",
        ),
    )
    for field in ("candidate_pool_hash", "scheduler_input_hash", "schedule_result_hash", "trace_hash"):
        require_sha256(field, data[field])
    if data["final_search_state_hash"] is not None:
        require_sha256("final_search_state_hash", data["final_search_state_hash"])
    for index, value_hash in enumerate(_array("selection_trace.operation_hashes", data["operation_hashes"])):
        require_sha256(f"operation_hashes[{index}]", value_hash)
    for index, value_hash in enumerate(_array("selection_trace.transition_hashes", data["transition_hashes"])):
        require_sha256(f"transition_hashes[{index}]", value_hash)
    return MidDevSelectionTrace(
        source_group_id=data["source_group_id"],
        sample_id=data["sample_id"],
        condition=MidDevCondition(data["condition"]),
        budget=data["budget"],
        replicate=data["replicate"],
        schedule_seed=data["schedule_seed"],
        candidate_pool_hash=data["candidate_pool_hash"],
        scheduler_input_hash=data["scheduler_input_hash"],
        schedule_result_hash=data["schedule_result_hash"],
        final_search_state_hash=data["final_search_state_hash"],
        operation_hashes=tuple(data["operation_hashes"]),
        transition_hashes=tuple(data["transition_hashes"]),
        status=data["status"],
        trace_hash=data["trace_hash"],
    )


def _trace_artifact(value: object) -> MidDevSelectionTraceArtifact:
    data = _mapping(
        "trace_artifact",
        value,
        ("plan_hash", "traces", "artifact_hash"),
    )
    return MidDevSelectionTraceArtifact(
        plan_hash=data["plan_hash"],
        traces=tuple(_trace(row) for row in _array("trace_artifact.traces", data["traces"])),
        artifact_hash=data["artifact_hash"],
    )


def _parse_json(text: str) -> object:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("MidDev plan JSON exceeds the size limit")
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except Exception as error:
        raise MidDevPlanJsonError("MidDev plan JSON is not valid JSON") from error


def parse_mid_dev_plan_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevDeterministicFrozenPlan:
    decoded = _parse_json(text)
    try:
        plan = _plan(decoded)
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev plan JSON failed plan validation") from error
    if require_canonical and text not in (
        canonical_json_text(plan),
        canonical_json_text(plan) + "\n",
    ):
        raise MidDevPlanJsonError("MidDev plan JSON is not canonical")
    return plan


def parse_mid_dev_trace_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevSelectionTraceArtifact:
    decoded = _parse_json(text)
    try:
        artifact = _trace_artifact(decoded)
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev trace JSON failed artifact validation") from error
    if require_canonical and text not in (
        canonical_json_text(artifact),
        canonical_json_text(artifact) + "\n",
    ):
        raise MidDevPlanJsonError("MidDev trace JSON is not canonical")
    return artifact


def validate_mid_dev_plan_trace_binding(
    plan: MidDevDeterministicFrozenPlan,
    traces: MidDevSelectionTraceArtifact,
) -> None:
    if traces.plan_hash != plan.plan_hash:
        raise MidDevPlanJsonError("selection traces do not bind the frozen MidDev plan")
    by_hash = {trace.trace_hash: trace for trace in traces.traces}
    if len(by_hash) != len(plan.rows) or set(by_hash) != {
        row.selection_trace_hash for row in plan.rows
    }:
        raise MidDevPlanJsonError("selection traces do not bind every MidDev plan row exactly once")
    for row in plan.rows:
        trace = by_hash[row.selection_trace_hash]
        if (
            trace.source_group_id != row.source_group_id
            or trace.sample_id != row.sample_id
            or trace.condition is not row.condition
            or trace.budget != row.budget
            or trace.replicate != row.replicate
            or trace.status != row.status
        ):
            raise MidDevPlanJsonError("selection trace metadata does not match its MidDev plan row")
        expected_seed = (
            0
            if row.condition is MidDevCondition.NO_OP
            else _schedule_seed(row.sample_id, row.condition, row.budget, row.replicate)
        )
        if trace.schedule_seed != expected_seed:
            raise MidDevPlanJsonError("selection trace schedule seed does not replay")


def load_mid_dev_plan_json(path: str | Path) -> MidDevDeterministicFrozenPlan:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("MidDev plan JSON exceeds the size limit")
    return parse_mid_dev_plan_json(file_path.read_text(encoding="utf-8"))


def load_mid_dev_trace_json(path: str | Path) -> MidDevSelectionTraceArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("MidDev trace JSON exceeds the size limit")
    return parse_mid_dev_trace_json(file_path.read_text(encoding="utf-8"))
