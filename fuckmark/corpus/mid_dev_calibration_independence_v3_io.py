from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import canonical_json_text
from .mid_dev_calibration_independence_v3 import (
    MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE,
    MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION,
    CalibrationCollisionKind,
    CalibrationIndependenceV3Exclusion,
    CalibrationIndependenceV3PairArtifact,
    CalibrationIndependenceV3RoleManifest,
)
from .mid_dev_calibration_shards import CalibrationRole
from .tiny_dev_io import _mapping, _reject_constant, _unique_object


MID_DEV_CALIBRATION_INDEPENDENCE_V3_JSON_MAX_BYTES = 8 * 1024 * 1024


class CalibrationIndependenceV3JsonError(ValueError):
    pass


def _parse(text: str) -> object:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_INDEPENDENCE_V3_JSON_MAX_BYTES:
        raise CalibrationIndependenceV3JsonError("calibration independence v3 JSON exceeds size limit")
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except Exception as error:
        if isinstance(error, CalibrationIndependenceV3JsonError):
            raise
        raise CalibrationIndependenceV3JsonError("calibration independence v3 JSON is invalid") from error


def _exclusion(value: object) -> CalibrationIndependenceV3Exclusion:
    data = _mapping(
        "calibration_independence_v3_exclusion",
        value,
        (
            "role",
            "ordinal",
            "prompt_id",
            "sample_id",
            "reason",
            "collision_kinds",
            "conflicting_role",
            "conflicting_ordinal",
            "conflicting_prompt_id",
            "conflicting_sample_id",
            "exclusion_hash",
        ),
    )
    try:
        kinds = tuple(CalibrationCollisionKind(item) for item in data["collision_kinds"])
        return CalibrationIndependenceV3Exclusion(
            role=CalibrationRole(data["role"]),
            ordinal=data["ordinal"],
            prompt_id=data["prompt_id"],
            sample_id=data["sample_id"],
            reason=data["reason"],
            collision_kinds=kinds,
            conflicting_role=CalibrationRole(data["conflicting_role"]),
            conflicting_ordinal=data["conflicting_ordinal"],
            conflicting_prompt_id=data["conflicting_prompt_id"],
            conflicting_sample_id=data["conflicting_sample_id"],
            exclusion_hash=data["exclusion_hash"],
        )
    except Exception as error:
        raise CalibrationIndependenceV3JsonError("invalid calibration independence v3 exclusion") from error


def _manifest(value: object) -> CalibrationIndependenceV3RoleManifest:
    data = _mapping(
        "calibration_independence_v3_role_manifest",
        value,
        (
            "role",
            "plan_hash",
            "raw_candidate_count",
            "independent_candidate_count",
            "selected_candidate_count",
            "candidate_order_hash",
            "independent_sample_ids_hash",
            "selected_sample_ids",
            "selected_record_hashes",
            "selected_text_sha256s",
            "selected_continuation_token_hashes",
            "excluded_sample_ids",
            "exclusion_hashes",
            "manifest_hash",
        ),
    )
    try:
        return CalibrationIndependenceV3RoleManifest(
            role=CalibrationRole(data["role"]),
            plan_hash=data["plan_hash"],
            raw_candidate_count=data["raw_candidate_count"],
            independent_candidate_count=data["independent_candidate_count"],
            selected_candidate_count=data["selected_candidate_count"],
            candidate_order_hash=data["candidate_order_hash"],
            independent_sample_ids_hash=data["independent_sample_ids_hash"],
            selected_sample_ids=tuple(data["selected_sample_ids"]),
            selected_record_hashes=tuple(data["selected_record_hashes"]),
            selected_text_sha256s=tuple(data["selected_text_sha256s"]),
            selected_continuation_token_hashes=tuple(data["selected_continuation_token_hashes"]),
            excluded_sample_ids=tuple(data["excluded_sample_ids"]),
            exclusion_hashes=tuple(data["exclusion_hashes"]),
            manifest_hash=data["manifest_hash"],
        )
    except Exception as error:
        raise CalibrationIndependenceV3JsonError("invalid calibration independence v3 role manifest") from error


def _artifact(value: object) -> CalibrationIndependenceV3PairArtifact:
    data = _mapping(
        "calibration_independence_v3_pair_artifact",
        value,
        (
            "algorithm_version",
            "selection_rule",
            "required_count_per_role",
            "select_plan_hash",
            "audit_plan_hash",
            "model_tokenizer_identity_hash",
            "watermark_config_hash",
            "watermark_condition_hash",
            "select_manifest_hash",
            "audit_manifest_hash",
            "exclusion_hashes",
            "cross_role_collision_count",
            "artifact_hash",
        ),
    )
    try:
        return CalibrationIndependenceV3PairArtifact(
            algorithm_version=data["algorithm_version"],
            selection_rule=data["selection_rule"],
            required_count_per_role=data["required_count_per_role"],
            select_plan_hash=data["select_plan_hash"],
            audit_plan_hash=data["audit_plan_hash"],
            model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
            watermark_config_hash=data["watermark_config_hash"],
            watermark_condition_hash=data["watermark_condition_hash"],
            select_manifest_hash=data["select_manifest_hash"],
            audit_manifest_hash=data["audit_manifest_hash"],
            exclusion_hashes=tuple(data["exclusion_hashes"]),
            cross_role_collision_count=data["cross_role_collision_count"],
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        raise CalibrationIndependenceV3JsonError("invalid calibration independence v3 pair artifact") from error


def parse_mid_dev_calibration_independence_v3_artifact_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3PairArtifact:
    decoded = _parse(text)
    try:
        artifact = _artifact(decoded)
    except CalibrationIndependenceV3JsonError:
        raise
    if artifact.algorithm_version != MID_DEV_CALIBRATION_INDEPENDENCE_V3_VERSION:
        raise CalibrationIndependenceV3JsonError("unsupported calibration independence v3 version")
    if artifact.selection_rule != MID_DEV_CALIBRATION_INDEPENDENCE_V3_SELECTION_RULE:
        raise CalibrationIndependenceV3JsonError("unsupported calibration independence v3 selection rule")
    if require_canonical:
        canonical = canonical_json_text(artifact)
        if text not in (canonical, canonical + "\n"):
            raise CalibrationIndependenceV3JsonError("calibration independence v3 artifact is not canonical")
    return artifact


def parse_mid_dev_calibration_independence_v3_manifest_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3RoleManifest:
    decoded = _parse(text)
    manifest = _manifest(decoded)
    if require_canonical:
        canonical = canonical_json_text(manifest)
        if text not in (canonical, canonical + "\n"):
            raise CalibrationIndependenceV3JsonError("calibration independence v3 manifest is not canonical")
    return manifest


def parse_mid_dev_calibration_independence_v3_exclusion_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3Exclusion:
    decoded = _parse(text)
    exclusion = _exclusion(decoded)
    if require_canonical:
        canonical = canonical_json_text(exclusion)
        if text not in (canonical, canonical + "\n"):
            raise CalibrationIndependenceV3JsonError("calibration independence v3 exclusion is not canonical")
    return exclusion


def _load(path: str | Path, parser: Any) -> object:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_INDEPENDENCE_V3_JSON_MAX_BYTES:
        raise CalibrationIndependenceV3JsonError("calibration independence v3 JSON exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise CalibrationIndependenceV3JsonError("calibration independence v3 JSON must be UTF-8") from error
    return parser(text)


def load_mid_dev_calibration_independence_v3_artifact_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3PairArtifact:
    return _load(
        path,
        lambda text: parse_mid_dev_calibration_independence_v3_artifact_json(text, require_canonical=require_canonical),
    )


def load_mid_dev_calibration_independence_v3_manifest_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3RoleManifest:
    return _load(
        path,
        lambda text: parse_mid_dev_calibration_independence_v3_manifest_json(text, require_canonical=require_canonical),
    )


def load_mid_dev_calibration_independence_v3_exclusion_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> CalibrationIndependenceV3Exclusion:
    return _load(
        path,
        lambda text: parse_mid_dev_calibration_independence_v3_exclusion_json(text, require_canonical=require_canonical),
    )
