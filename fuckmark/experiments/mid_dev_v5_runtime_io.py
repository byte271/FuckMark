from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from ..search.visible_cost_budget import VisibleCostTier
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json
from .mid_dev_plan_v5 import MidDevNormalizedPlanner
from .mid_dev_v5_builder import MidDevNormalizedSelectionTrace, MidDevNormalizedTraceArtifact


def _hash_tuple(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must be a JSON array of strings")
    return tuple(value)


def _trace(value: object) -> MidDevNormalizedSelectionTrace:
    data = _mapping(
        "mid_dev_normalized_selection_trace",
        value,
        (
            "source_group_id",
            "sample_id",
            "planner",
            "tier",
            "replicate",
            "seed",
            "policy_hash",
            "candidate_registry_hash",
            "reference_state_hash",
            "matched_cost_envelope_hash",
            "search_result_hash",
            "final_search_state_hash",
            "candidate_hashes",
            "operation_hashes",
            "rule_hashes",
            "status",
            "detector_access_observed",
            "secret_access_observed",
            "trace_hash",
        ),
    )
    return MidDevNormalizedSelectionTrace(
        source_group_id=data["source_group_id"],
        sample_id=data["sample_id"],
        planner=MidDevNormalizedPlanner(data["planner"]),
        tier=VisibleCostTier(data["tier"]),
        replicate=data["replicate"],
        seed=data["seed"],
        policy_hash=data["policy_hash"],
        candidate_registry_hash=data["candidate_registry_hash"],
        reference_state_hash=data["reference_state_hash"],
        matched_cost_envelope_hash=data["matched_cost_envelope_hash"],
        search_result_hash=data["search_result_hash"],
        final_search_state_hash=data["final_search_state_hash"],
        candidate_hashes=_hash_tuple("candidate_hashes", data["candidate_hashes"]),
        operation_hashes=_hash_tuple("operation_hashes", data["operation_hashes"]),
        rule_hashes=_hash_tuple("rule_hashes", data["rule_hashes"]),
        status=data["status"],
        detector_access_observed=data["detector_access_observed"],
        secret_access_observed=data["secret_access_observed"],
        trace_hash=data["trace_hash"],
    )


def parse_mid_dev_normalized_trace_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevNormalizedTraceArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_normalized_trace_artifact",
            decoded,
            (
                "development_plan_hash",
                "required_cell_registry_hash",
                "traces",
                "artifact_hash",
            ),
        )
        artifact = MidDevNormalizedTraceArtifact(
            development_plan_hash=data["development_plan_hash"],
            required_cell_registry_hash=data["required_cell_registry_hash"],
            traces=tuple(_trace(value) for value in _array("traces", data["traces"])),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev normalized trace artifact failed validation") from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise MidDevPlanJsonError("MidDev normalized trace artifact JSON is not canonical")
    return artifact


def load_mid_dev_normalized_trace_artifact_json(path: str | Path) -> MidDevNormalizedTraceArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("MidDev normalized trace artifact JSON exceeds the size limit")
    return parse_mid_dev_normalized_trace_artifact_json(file_path.read_text(encoding="utf-8"))
