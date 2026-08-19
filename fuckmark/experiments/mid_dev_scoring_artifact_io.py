from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.schema import WatermarkLabel
from ..corpus.tiny_dev_io import _array, _mapping, _reject_constant, _unique_object
from .mid_dev_scored_schema import MidDevScoredPlanRow, MidDevScoringArtifact
from .mid_dev_scoring_contracts import MidDevCondition, MidDevFrozenPlanView


MID_DEV_SCORING_ARTIFACT_JSON_MAX_BYTES = 512 * 1024 * 1024


class MidDevScoringArtifactJsonError(ValueError):
    pass


def _scored_row(value: object) -> MidDevScoredPlanRow:
    data = _mapping(
        "scored_row",
        value,
        (
            "plan_row_hash",
            "source_group_id",
            "sample_id",
            "source_label",
            "condition",
            "budget",
            "replicate",
            "status",
            "realized_edit_cost",
            "detector_identity_hash",
            "threshold_hash",
            "threshold_value",
            "pristine_score",
            "transformed_score",
            "pristine_detected",
            "transformed_detected",
            "scored_row_hash",
        ),
    )
    return MidDevScoredPlanRow(
        data["plan_row_hash"],
        data["source_group_id"],
        data["sample_id"],
        WatermarkLabel(data["source_label"]),
        MidDevCondition(data["condition"]),
        data["budget"],
        data["replicate"],
        data["status"],
        data["realized_edit_cost"],
        data["detector_identity_hash"],
        data["threshold_hash"],
        data["threshold_value"],
        data["pristine_score"],
        data["transformed_score"],
        data["pristine_detected"],
        data["transformed_detected"],
        data["scored_row_hash"],
    )


def _artifact(value: object) -> MidDevScoringArtifact:
    data = _mapping(
        "scoring_artifact",
        value,
        (
            "mid_dev_corpus_artifact_hash",
            "source_profile_hash",
            "analysis_split_hash",
            "plan_hash",
            "trace_artifact_hash",
            "calibration_corpus_artifact_hash",
            "calibration_bundle_hash",
            "detector_identity_hash",
            "threshold_hash",
            "threshold_value",
            "target_fpr",
            "independent_source_group_count",
            "independent_watermarked_source_count",
            "independent_control_source_count",
            "pristine_watermarked_detected_count",
            "pristine_control_detected_count",
            "rows",
            "artifact_hash",
        ),
    )
    return MidDevScoringArtifact(
        data["mid_dev_corpus_artifact_hash"],
        data["source_profile_hash"],
        data["analysis_split_hash"],
        data["plan_hash"],
        data["trace_artifact_hash"],
        data["calibration_corpus_artifact_hash"],
        data["calibration_bundle_hash"],
        data["detector_identity_hash"],
        data["threshold_hash"],
        data["threshold_value"],
        data["target_fpr"],
        data["independent_source_group_count"],
        data["independent_watermarked_source_count"],
        data["independent_control_source_count"],
        data["pristine_watermarked_detected_count"],
        data["pristine_control_detected_count"],
        tuple(_scored_row(row) for row in _array("scoring_artifact.rows", data["rows"])),
        data["artifact_hash"],
    )


def _decode(text: str) -> object:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_SCORING_ARTIFACT_JSON_MAX_BYTES:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact JSON exceeds the size limit")
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except Exception as error:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact is not valid JSON") from error


def parse_mid_dev_scoring_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevScoringArtifact:
    try:
        artifact = _artifact(_decode(text))
    except Exception as error:
        if isinstance(error, MidDevScoringArtifactJsonError):
            raise
        raise MidDevScoringArtifactJsonError(
            "MidDev scoring artifact failed scored-row or artifact validation"
        ) from error
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise MidDevScoringArtifactJsonError("MidDev scoring artifact JSON is not canonical")
    return artifact


def validate_mid_dev_scoring_artifact_binding(
    artifact: MidDevScoringArtifact,
    plan: MidDevFrozenPlanView,
) -> None:
    if artifact.plan_hash != plan.plan_hash:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact does not bind the frozen plan")
    if artifact.mid_dev_corpus_artifact_hash != plan.corpus_artifact_hash:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact does not bind the plan corpus")
    if artifact.source_profile_hash != plan.source_profile_hash:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact source profile does not match plan")
    if artifact.analysis_split_hash != plan.analysis_split_hash:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact analysis split does not match plan")
    scored_by_hash = {row.plan_row_hash: row for row in artifact.rows}
    plan_by_hash = {row.plan_row_hash: row for row in plan.rows}
    if set(scored_by_hash) != set(plan_by_hash):
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact does not score every frozen plan row exactly once")
    for plan_hash, plan_row in plan_by_hash.items():
        scored = scored_by_hash[plan_hash]
        if (
            scored.source_group_id != plan_row.source_group_id
            or scored.sample_id != plan_row.sample_id
            or scored.source_label is not plan_row.source_label
            or scored.condition is not plan_row.condition
            or scored.budget != plan_row.budget
            or scored.replicate != plan_row.replicate
            or scored.status != plan_row.status
            or scored.realized_edit_cost != plan_row.operation_count
        ):
            raise MidDevScoringArtifactJsonError("MidDev scored row metadata does not replay its frozen plan row")


def load_mid_dev_scoring_artifact_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> MidDevScoringArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_SCORING_ARTIFACT_JSON_MAX_BYTES:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact JSON exceeds the size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevScoringArtifactJsonError("MidDev scoring artifact JSON must be UTF-8") from error
    return parse_mid_dev_scoring_artifact_json(text, require_canonical=require_canonical)
