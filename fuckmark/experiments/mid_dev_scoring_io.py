from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.schema import CorpusDomain, WatermarkLabel
from ..corpus.tiny_dev_io import _array, _mapping, _reject_constant, _unique_object
from .mid_dev_scoring_contracts import (
    MID_DEV_RANDOM_REPLICATES,
    MidDevCondition,
    MidDevDeterministicComputeRowView,
    MidDevFrozenPlanView,
    MidDevPlanRowView,
    MidDevQualityRowView,
    MidDevSelectionAttestationView,
    MidDevSelectionConfigView,
    validate_complete_mid_dev_matrix,
)
from .mid_dev_trace_schema import (
    MidDevSelectionTrace,
    MidDevSelectionTraceArtifact,
    mid_dev_schedule_seed,
)


MID_DEV_SCORING_IO_MAX_BYTES = 512 * 1024 * 1024
MID_DEV_FROZEN_NGRAM_LEN = 5
MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE = 1024


class MidDevScoringIoError(ValueError):
    pass


def _selection_config(value: object) -> MidDevSelectionConfigView:
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
    return MidDevSelectionConfigView(
        data["algorithm_version"],
        tuple(_array("selection_config.budgets", data["budgets"])),
        tuple(_array("selection_config.beam_budgets", data["beam_budgets"])),
        data["random_replicates"],
        data["beam_width"],
        data["max_risk_tier"],
        data["beam_algorithm_version"],
        data["config_hash"],
    )


def _selection_attestation(value: object) -> MidDevSelectionAttestationView:
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
    return MidDevSelectionAttestationView(
        data["algorithm_version"],
        data["attested_expander_count"],
        data["detector_access_observed"],
        data["secret_access_observed"],
        data["detector_query_count"],
        data["secret_query_count"],
        data["attestation_hash"],
    )


def _plan_row(value: object) -> MidDevPlanRowView:
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
    return MidDevPlanRowView(
        data["source_group_id"],
        data["prompt_id"],
        data["sample_id"],
        WatermarkLabel(data["source_label"]),
        data["prompt_family_id"],
        CorpusDomain(data["domain"]),
        data["target_length"],
        data["source_text_hash"],
        MidDevCondition(data["condition"]),
        data["budget"],
        data["replicate"],
        data["transformed_text"],
        data["transformed_text_hash"],
        data["operation_count"],
        data["status"],
        data["selection_trace_hash"],
        data["plan_row_hash"],
    )


def _quality_row(value: object) -> MidDevQualityRowView:
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
    return MidDevQualityRowView(
        data["plan_row_hash"],
        data["word_edit_rate"],
        data["old_observation_replacement_ratio"],
        data["exact_destruction_ratio"],
        data["exact_survival_ratio"],
        data["token_edit_distance"],
        data["length_ratio"],
        data["numbers_preserved_fraction"],
        data["urls_preserved_fraction"],
        data["protected_span_violation_count"],
        data["hard_invariant_status"],
        data["quality_hash"],
    )


def _compute_row(value: object) -> MidDevDeterministicComputeRowView:
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
    return MidDevDeterministicComputeRowView(
        data["plan_row_hash"],
        data["expanded_state_count"],
        data["pruned_state_count"],
        data["candidate_evaluation_count"],
        data["expansion_cache_hit_count"],
        data["expansion_cache_miss_count"],
        data["geometry_cache_hit_count"],
        data["selection_detector_query_count"],
        data["selection_secret_query_count"],
        data["compute_hash"],
    )


def _plan(value: object) -> MidDevFrozenPlanView:
    data = _mapping(
        "plan",
        value,
        (
            "algorithm_version",
            "corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "source_code_commit",
            "ngram_len",
            "context_history_size",
            "selection_config",
            "selection_attestation",
            "rows",
            "quality_rows",
            "compute_rows",
            "plan_hash",
        ),
    )
    plan = MidDevFrozenPlanView(
        data["algorithm_version"],
        data["corpus_artifact_hash"],
        data["source_profile_hash"],
        data["analysis_split_hash"],
        data["source_code_commit"],
        data["ngram_len"],
        data["context_history_size"],
        _selection_config(data["selection_config"]),
        _selection_attestation(data["selection_attestation"]),
        tuple(_plan_row(row) for row in _array("plan.rows", data["rows"])),
        tuple(_quality_row(row) for row in _array("plan.quality_rows", data["quality_rows"])),
        tuple(_compute_row(row) for row in _array("plan.compute_rows", data["compute_rows"])),
        data["plan_hash"],
    )
    validate_complete_mid_dev_matrix(plan.rows)
    if plan.ngram_len != MID_DEV_FROZEN_NGRAM_LEN:
        raise MidDevScoringIoError("frozen MidDev plan must use ngram_len=5")
    if plan.context_history_size != MID_DEV_FROZEN_CONTEXT_HISTORY_SIZE:
        raise MidDevScoringIoError("frozen MidDev plan must use context_history_size=1024")
    if plan.selection_attestation.attested_expander_count != 72:
        raise MidDevScoringIoError("frozen MidDev plan attestation does not cover 72 expanders")
    return plan


def _trace(value: object) -> MidDevSelectionTrace:
    data = _mapping(
        "trace",
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
    return MidDevSelectionTrace(
        data["source_group_id"],
        data["sample_id"],
        MidDevCondition(data["condition"]),
        data["budget"],
        data["replicate"],
        data["schedule_seed"],
        data["candidate_pool_hash"],
        data["scheduler_input_hash"],
        data["schedule_result_hash"],
        data["final_search_state_hash"],
        tuple(_array("trace.operation_hashes", data["operation_hashes"])),
        tuple(_array("trace.transition_hashes", data["transition_hashes"])),
        data["status"],
        data["trace_hash"],
    )


def _trace_artifact(value: object) -> MidDevSelectionTraceArtifact:
    data = _mapping("trace_artifact", value, ("plan_hash", "traces", "artifact_hash"))
    return MidDevSelectionTraceArtifact(
        data["plan_hash"],
        tuple(_trace(row) for row in _array("trace_artifact.traces", data["traces"])),
        data["artifact_hash"],
    )


def _decode(text: str) -> object:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_SCORING_IO_MAX_BYTES:
        raise MidDevScoringIoError("MidDev scoring input exceeds the size limit")
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except Exception as error:
        raise MidDevScoringIoError("MidDev scoring input is not valid JSON") from error


def parse_mid_dev_scoring_plan_json(text: str) -> MidDevFrozenPlanView:
    try:
        plan = _plan(_decode(text))
    except Exception as error:
        if isinstance(error, MidDevScoringIoError):
            raise
        raise MidDevScoringIoError("MidDev frozen plan failed scoring-side validation") from error
    if text not in (canonical_json_text(plan), canonical_json_text(plan) + "\n"):
        raise MidDevScoringIoError("MidDev frozen plan is not canonical")
    return plan


def parse_mid_dev_scoring_trace_json(text: str) -> MidDevSelectionTraceArtifact:
    try:
        traces = _trace_artifact(_decode(text))
    except Exception as error:
        if isinstance(error, MidDevScoringIoError):
            raise
        raise MidDevScoringIoError("MidDev trace artifact failed scoring-side validation") from error
    if text not in (canonical_json_text(traces), canonical_json_text(traces) + "\n"):
        raise MidDevScoringIoError("MidDev trace artifact is not canonical")
    return traces


def validate_mid_dev_scoring_plan_trace_binding(
    plan: MidDevFrozenPlanView,
    traces: MidDevSelectionTraceArtifact,
) -> None:
    if traces.plan_hash != plan.plan_hash:
        raise MidDevScoringIoError("MidDev trace artifact does not bind the frozen plan")
    by_hash = {trace.trace_hash: trace for trace in traces.traces}
    if len(by_hash) != len(plan.rows) or set(by_hash) != {row.selection_trace_hash for row in plan.rows}:
        raise MidDevScoringIoError("MidDev trace artifact does not bind every plan row exactly once")
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
            raise MidDevScoringIoError("MidDev trace metadata does not match the bound plan row")
        expected_seed = 0 if row.condition is MidDevCondition.NO_OP else mid_dev_schedule_seed(
            row.sample_id,
            row.condition,
            row.budget,
            row.replicate,
        )
        if trace.schedule_seed != expected_seed:
            raise MidDevScoringIoError("MidDev trace schedule seed does not replay")


def load_mid_dev_scoring_plan_json(path: str | Path) -> MidDevFrozenPlanView:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_SCORING_IO_MAX_BYTES:
        raise MidDevScoringIoError("MidDev frozen plan exceeds the size limit")
    return parse_mid_dev_scoring_plan_json(file_path.read_text(encoding="utf-8"))


def load_mid_dev_scoring_trace_json(path: str | Path) -> MidDevSelectionTraceArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_SCORING_IO_MAX_BYTES:
        raise MidDevScoringIoError("MidDev trace artifact exceeds the size limit")
    return parse_mid_dev_scoring_trace_json(file_path.read_text(encoding="utf-8"))
