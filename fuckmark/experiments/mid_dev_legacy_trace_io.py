from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from .mid_dev_context_survival import MidDevCondition
from .mid_dev_plan_builder import MidDevSelectionTrace, MidDevSelectionTraceArtifact
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json


def _hash_tuple(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must be a JSON array of strings")
    return tuple(value)


def _trace(value: object) -> MidDevSelectionTrace:
    data = _mapping(
        "mid_dev_selection_trace",
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
        operation_hashes=_hash_tuple("operation_hashes", data["operation_hashes"]),
        transition_hashes=_hash_tuple("transition_hashes", data["transition_hashes"]),
        status=data["status"],
        trace_hash=data["trace_hash"],
    )


def parse_mid_dev_selection_trace_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevSelectionTraceArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_selection_trace_artifact",
            decoded,
            ("plan_hash", "traces", "artifact_hash"),
        )
        artifact = MidDevSelectionTraceArtifact(
            plan_hash=data["plan_hash"],
            traces=tuple(_trace(value) for value in _array("traces", data["traces"])),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev selection trace artifact failed validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise MidDevPlanJsonError("MidDev selection trace artifact JSON is not canonical")
    return artifact


def load_mid_dev_selection_trace_artifact_json(path: str | Path) -> MidDevSelectionTraceArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES * 4:
        raise MidDevPlanJsonError("MidDev selection trace artifact JSON exceeds the size limit")
    return parse_mid_dev_selection_trace_artifact_json(file_path.read_text(encoding="utf-8"))
