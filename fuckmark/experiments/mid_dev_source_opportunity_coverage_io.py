from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from ..hashing import sha256_json
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json
from .mid_dev_source_opportunity_coverage import (
    MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION,
    MID_DEV_SOURCE_OPPORTUNITY_ROW_VERSION,
    MID_DEV_SOURCE_REGIME_COUNT_VERSION,
    MidDevSourceOpportunityCoverageArtifact,
    MidDevSourceOpportunityCoverageRow,
    MidDevSourceRegimeCount,
)


MID_DEV_SOURCE_OPPORTUNITY_PROVENANCE_VERSION = "mid-dev-source-opportunity-provenance-v1"


def _canonical_check(text: str, value, label: str) -> None:
    canonical = canonical_json_text(value)
    if text not in (canonical, canonical + "\n"):
        raise MidDevPlanJsonError(f"{label} JSON is not canonical")


def _coverage_row(value: object) -> MidDevSourceOpportunityCoverageRow:
    data = _mapping(
        "source_opportunity_coverage_row",
        value,
        tuple(MidDevSourceOpportunityCoverageRow.__dataclass_fields__),
    )
    row = MidDevSourceOpportunityCoverageRow(**data)
    if row.algorithm_version != MID_DEV_SOURCE_OPPORTUNITY_ROW_VERSION:
        raise MidDevPlanJsonError("unsupported source opportunity row version")
    return row


def _regime_count(value: object) -> MidDevSourceRegimeCount:
    data = _mapping(
        "source_regime_count",
        value,
        tuple(MidDevSourceRegimeCount.__dataclass_fields__),
    )
    item = MidDevSourceRegimeCount(**data)
    if item.algorithm_version != MID_DEV_SOURCE_REGIME_COUNT_VERSION:
        raise MidDevPlanJsonError("unsupported source regime count version")
    return item


def parse_mid_dev_source_opportunity_coverage_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> MidDevSourceOpportunityCoverageArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_source_opportunity_coverage",
            decoded,
            (
                "algorithm_version",
                "calibration_opportunity_audit_hash",
                "regime_decision_hash",
                "source_corpus_artifact_hash",
                "source_manifest_hash",
                "source_profile_hash",
                "analysis_split_hash",
                "source_opportunity_audit_hash",
                "model_tokenizer_identity_hash",
                "source_count",
                "sample_count",
                "rows",
                "regime_counts",
                "required_regime_ids",
                "artifact_hash",
            ),
        )
        required = data["required_regime_ids"]
        if not isinstance(required, list) or any(not isinstance(value, str) for value in required):
            raise TypeError("required_regime_ids must be a JSON array of strings")
        artifact = MidDevSourceOpportunityCoverageArtifact(
            algorithm_version=data["algorithm_version"],
            calibration_opportunity_audit_hash=data["calibration_opportunity_audit_hash"],
            regime_decision_hash=data["regime_decision_hash"],
            source_corpus_artifact_hash=data["source_corpus_artifact_hash"],
            source_manifest_hash=data["source_manifest_hash"],
            source_profile_hash=data["source_profile_hash"],
            analysis_split_hash=data["analysis_split_hash"],
            source_opportunity_audit_hash=data["source_opportunity_audit_hash"],
            model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
            source_count=data["source_count"],
            sample_count=data["sample_count"],
            rows=tuple(_coverage_row(item) for item in _array("rows", data["rows"])),
            regime_counts=tuple(_regime_count(item) for item in _array("regime_counts", data["regime_counts"])),
            required_regime_ids=tuple(required),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("source opportunity coverage failed validation") from error
    if artifact.algorithm_version != MID_DEV_SOURCE_OPPORTUNITY_COVERAGE_VERSION:
        raise MidDevPlanJsonError("unsupported source opportunity coverage version")
    if require_canonical:
        _canonical_check(text, artifact, "source opportunity coverage")
    return artifact


def load_mid_dev_source_opportunity_coverage_json(
    path: str | Path,
) -> MidDevSourceOpportunityCoverageArtifact:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("source opportunity coverage JSON exceeds size limit")
    return parse_mid_dev_source_opportunity_coverage_json(
        file_path.read_text(encoding="utf-8")
    )


def parse_mid_dev_source_opportunity_provenance_json(text: str) -> dict[str, object]:
    decoded = _parse_json(text)
    fields = (
        "algorithm_version",
        "calibration_opportunity_audit_hash",
        "regime_decision_hash",
        "source_corpus_artifact_hash",
        "source_manifest_hash",
        "source_profile_hash",
        "analysis_split_hash",
        "source_opportunity_audit_hash",
        "coverage_artifact_hash",
        "model_tokenizer_identity_hash",
        "source_count",
        "sample_count",
        "required_regime_ids",
        "tokenizer_round_trip_all_ok",
        "attack_transform_count",
        "attack_score_count",
        "detector_score_count",
        "calibration_threshold_constructed",
        "cal_select_or_audit_samples_consumed",
        "source_corpus_fsync_success",
        "source_opportunity_audit_fsync_success",
        "coverage_fsync_success",
        "github_run_id",
        "github_run_attempt",
        "github_event_name",
        "github_checkout_sha",
        "provenance_hash",
    )
    data = _mapping("source_opportunity_provenance", decoded, fields)
    if data["algorithm_version"] != MID_DEV_SOURCE_OPPORTUNITY_PROVENANCE_VERSION:
        raise MidDevPlanJsonError("unsupported source opportunity provenance version")
    hash_fields = (
        "calibration_opportunity_audit_hash",
        "regime_decision_hash",
        "source_corpus_artifact_hash",
        "source_manifest_hash",
        "source_profile_hash",
        "analysis_split_hash",
        "source_opportunity_audit_hash",
        "coverage_artifact_hash",
        "model_tokenizer_identity_hash",
    )
    for name in hash_fields:
        value = data[name]
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise MidDevPlanJsonError(f"{name} must be lowercase SHA-256")
    if data["source_count"] != 36 or data["sample_count"] != 72:
        raise MidDevPlanJsonError("source opportunity provenance count drifted")
    required = data["required_regime_ids"]
    if not isinstance(required, list) or not required or required != sorted(set(required)):
        raise MidDevPlanJsonError("source opportunity provenance regimes are invalid")
    for name in (
        "tokenizer_round_trip_all_ok",
        "calibration_threshold_constructed",
        "cal_select_or_audit_samples_consumed",
        "source_corpus_fsync_success",
        "source_opportunity_audit_fsync_success",
        "coverage_fsync_success",
    ):
        if type(data[name]) is not bool:
            raise MidDevPlanJsonError(f"{name} must be bool")
    if not data["tokenizer_round_trip_all_ok"]:
        raise MidDevPlanJsonError("source opportunity tokenizer round-trip must pass")
    if data["calibration_threshold_constructed"] or data["cal_select_or_audit_samples_consumed"]:
        raise MidDevPlanJsonError("source opportunity stage consumed forbidden calibration state")
    for name in ("attack_transform_count", "attack_score_count", "detector_score_count"):
        if data[name] != 0:
            raise MidDevPlanJsonError(f"{name} must remain zero")
    for name in ("source_corpus_fsync_success", "source_opportunity_audit_fsync_success", "coverage_fsync_success"):
        if not data[name]:
            raise MidDevPlanJsonError(f"{name} must be true")
    payload = {name: data[name] for name in fields if name != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevPlanJsonError("source opportunity provenance hash mismatch")
    canonical = canonical_json_text(data)
    if text not in (canonical, canonical + "\n"):
        raise MidDevPlanJsonError("source opportunity provenance JSON is not canonical")
    return data


def load_mid_dev_source_opportunity_provenance_json(path: str | Path) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("source opportunity provenance JSON exceeds size limit")
    return parse_mid_dev_source_opportunity_provenance_json(
        file_path.read_text(encoding="utf-8")
    )
