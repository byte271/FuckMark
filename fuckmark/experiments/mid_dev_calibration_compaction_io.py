from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.mid_dev_calibration_shards import CalibrationRole
from ..corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from ..hashing import sha256_json
from .mid_dev_calibration_compaction import (
    MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
    MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
    CalibrationCompactionStatus,
    MidDevCalibrationCompactionRecord,
)


MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION = "mid-dev-calibration-compaction-provenance-v1"
MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_MAX_BYTES = 8 * 1024 * 1024


class MidDevCalibrationCompactionProvenanceError(ValueError):
    pass


def _sha(name: str, value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise MidDevCalibrationCompactionProvenanceError(f"{name} must be lowercase SHA-256")
    return value


def _record(value: object) -> MidDevCalibrationCompactionRecord:
    data = _mapping(
        "calibration_compaction_record",
        value,
        (
            "algorithm_version",
            "regime_id",
            "source_sample_count",
            "candidate_count",
            "selected_count",
            "status",
            "selected_sample_ids_hash",
            "selected_record_hashes_hash",
            "record_hash",
        ),
    )
    try:
        return MidDevCalibrationCompactionRecord(
            algorithm_version=data["algorithm_version"],
            regime_id=data["regime_id"],
            source_sample_count=data["source_sample_count"],
            candidate_count=data["candidate_count"],
            selected_count=data["selected_count"],
            status=CalibrationCompactionStatus(data["status"]),
            selected_sample_ids_hash=data["selected_sample_ids_hash"],
            selected_record_hashes_hash=data["selected_record_hashes_hash"],
            record_hash=data["record_hash"],
        )
    except Exception as error:
        raise MidDevCalibrationCompactionProvenanceError("invalid calibration compaction record") from error


def parse_mid_dev_calibration_compaction_provenance_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction provenance exceeds size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "calibration_compaction_provenance",
            decoded,
            (
                "algorithm_version",
                "role",
                "readiness_hash",
                "plan_hash",
                "candidate_pool_artifact_hash",
                "candidate_pool_manifest_hash",
                "candidate_merge_provenance_hash",
                "calibration_opportunity_audit_hash",
                "regime_decision_hash",
                "source_coverage_artifact_hash",
                "source_coverage_provenance_hash",
                "selection_rule",
                "preferred_n",
                "minimum_n",
                "candidate_count_total",
                "selected_count_total",
                "required_regime_ids",
                "serious_regime_ids",
                "descriptive_regime_ids",
                "records",
                "compacted_artifact_hash",
                "compacted_manifest_hash",
                "select_compaction_provenance_hash",
                "attack_transform_count",
                "attack_score_count",
                "detector_score_count",
                "calibration_threshold_constructed",
                "json_fsync_success",
                "github_run_id",
                "github_run_attempt",
                "github_event_name",
                "github_checkout_sha",
                "provenance_hash",
            ),
        )
    except Exception as error:
        if isinstance(error, MidDevCalibrationCompactionProvenanceError):
            raise
        raise MidDevCalibrationCompactionProvenanceError("invalid calibration compaction provenance JSON") from error
    if data["algorithm_version"] != MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION:
        raise MidDevCalibrationCompactionProvenanceError("unsupported calibration compaction provenance version")
    try:
        role = CalibrationRole(data["role"])
    except Exception as error:
        raise MidDevCalibrationCompactionProvenanceError("invalid calibration compaction role") from error
    if data["selection_rule"] != MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction selection rule drifted")
    if data["preferred_n"] != 2000 or data["minimum_n"] != 1000:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction N policy drifted")
    for name in (
        "readiness_hash",
        "plan_hash",
        "candidate_pool_artifact_hash",
        "candidate_pool_manifest_hash",
        "candidate_merge_provenance_hash",
        "calibration_opportunity_audit_hash",
        "regime_decision_hash",
        "source_coverage_artifact_hash",
        "source_coverage_provenance_hash",
        "compacted_artifact_hash",
        "compacted_manifest_hash",
        "provenance_hash",
    ):
        _sha(name, data[name])
    if role is CalibrationRole.SELECT:
        if data["select_compaction_provenance_hash"] is not None:
            raise MidDevCalibrationCompactionProvenanceError("CAL-SELECT cannot bind prior SELECT compaction")
    else:
        _sha("select_compaction_provenance_hash", data["select_compaction_provenance_hash"])
    for name in ("candidate_count_total", "selected_count_total"):
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MidDevCalibrationCompactionProvenanceError(f"{name} must be non-negative int")
    records_raw = data["records"]
    if not isinstance(records_raw, list) or not records_raw:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction records must be non-empty")
    records = tuple(_record(item) for item in records_raw)
    if tuple(sorted(records, key=lambda item: item.regime_id)) != records:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction records must be canonical")
    if len({item.regime_id for item in records}) != len(records):
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction regime IDs must be unique")
    required = data["required_regime_ids"]
    serious = data["serious_regime_ids"]
    descriptive = data["descriptive_regime_ids"]
    for name, values in (("required_regime_ids", required), ("serious_regime_ids", serious), ("descriptive_regime_ids", descriptive)):
        if not isinstance(values, list) or values != sorted(set(values)):
            raise MidDevCalibrationCompactionProvenanceError(f"{name} must be sorted unique strings")
        if any(not isinstance(value, str) or not value for value in values):
            raise MidDevCalibrationCompactionProvenanceError(f"{name} contains invalid regime id")
    if required != [item.regime_id for item in records]:
        raise MidDevCalibrationCompactionProvenanceError("required regime IDs do not bind records")
    expected_serious = [item.regime_id for item in records if item.status is CalibrationCompactionStatus.SERIOUS_THRESHOLD]
    expected_descriptive = [item.regime_id for item in records if item.status is CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE]
    if serious != expected_serious or descriptive != expected_descriptive:
        raise MidDevCalibrationCompactionProvenanceError("serious/descriptive regime sets do not replay")
    if set(serious) & set(descriptive) or sorted(serious + descriptive) != required:
        raise MidDevCalibrationCompactionProvenanceError("serious/descriptive regimes do not partition required regimes")
    if data["candidate_count_total"] < sum(item.candidate_count for item in records):
        raise MidDevCalibrationCompactionProvenanceError("required-regime candidate counts exceed candidate pool")
    if data["selected_count_total"] != sum(item.selected_count for item in records):
        raise MidDevCalibrationCompactionProvenanceError("selected calibration count does not replay")
    for name in ("attack_transform_count", "attack_score_count", "detector_score_count"):
        if data[name] != 0:
            raise MidDevCalibrationCompactionProvenanceError(f"{name} must remain zero")
    if data["calibration_threshold_constructed"] is not False:
        raise MidDevCalibrationCompactionProvenanceError("compaction must not construct a calibration threshold")
    if data["json_fsync_success"] is not True:
        raise MidDevCalibrationCompactionProvenanceError("compaction provenance does not attest fsync")
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction provenance hash does not replay")
    if require_canonical:
        canonical = canonical_json_text(data)
        if text not in (canonical, canonical + "\n"):
            raise MidDevCalibrationCompactionProvenanceError("calibration compaction provenance JSON is not canonical")
    return dict(data)


def load_mid_dev_calibration_compaction_provenance_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_MAX_BYTES:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction provenance exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevCalibrationCompactionProvenanceError("calibration compaction provenance must be UTF-8") from error
    return parse_mid_dev_calibration_compaction_provenance_json(text, require_canonical=require_canonical)


def compaction_records_from_provenance(data: dict[str, object]) -> tuple[MidDevCalibrationCompactionRecord, ...]:
    records = data.get("records")
    if not isinstance(records, list):
        raise MidDevCalibrationCompactionProvenanceError("compaction provenance records are unavailable")
    return tuple(_record(item) for item in records)
