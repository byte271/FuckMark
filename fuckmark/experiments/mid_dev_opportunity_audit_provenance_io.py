from __future__ import annotations

import json
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.mid_dev_calibration import (
    MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
    MID_DEV_CALIBRATION_SEED_BASE,
    MID_DEV_CALIBRATION_SOURCE_ID,
)
from ..corpus.tiny_dev_io import _mapping, _reject_constant, _unique_object
from ..hashing import sha256_json
from .detector_opportunity_audit import ELIGIBLE_IQR_OVERLAP_LIMIT, OPPORTUNITY_CV_LIMIT


MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION = "mid-dev-pristine-opportunity-audit-provenance-v1"
MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_MAX_BYTES = 2 * 1024 * 1024


class MidDevOpportunityAuditProvenanceError(ValueError):
    pass


def parse_mid_dev_opportunity_audit_provenance_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text.encode("utf-8")) > MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_MAX_BYTES:
        raise MidDevOpportunityAuditProvenanceError("opportunity audit provenance exceeds size limit")
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        data = _mapping(
            "opportunity_audit_provenance",
            decoded,
            (
                "algorithm_version",
                "model_tokenizer_identity_hash",
                "model_revision",
                "pristine_source_id",
                "pristine_seed_base",
                "pristine_negatives_per_length",
                "pristine_corpus_artifact_hash",
                "pristine_manifest_hash",
                "pristine_source_profile_hash",
                "sample_count",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "regime_mode",
                "opportunity_cv_limit",
                "eligible_iqr_overlap_limit",
                "tokenizer_round_trip_all_ok",
                "attack_transform_count",
                "attack_score_count",
                "detector_score_count",
                "calibration_threshold_constructed",
                "cal_select_or_audit_samples_consumed",
                "corpus_fsync_success",
                "opportunity_audit_fsync_success",
                "regime_decision_fsync_success",
                "github_run_id",
                "github_run_attempt",
                "github_event_name",
                "github_checkout_sha",
                "provenance_hash",
            ),
        )
    except Exception as error:
        raise MidDevOpportunityAuditProvenanceError("invalid opportunity audit provenance JSON") from error
    if data["algorithm_version"] != MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION:
        raise MidDevOpportunityAuditProvenanceError("unsupported opportunity audit provenance version")
    for name in (
        "model_tokenizer_identity_hash",
        "pristine_corpus_artifact_hash",
        "pristine_manifest_hash",
        "pristine_source_profile_hash",
        "opportunity_audit_hash",
        "regime_decision_hash",
        "provenance_hash",
    ):
        value = data[name]
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise MidDevOpportunityAuditProvenanceError(f"{name} must be a lowercase SHA-256 digest")
    if data["pristine_source_id"] != MID_DEV_CALIBRATION_SOURCE_ID:
        raise MidDevOpportunityAuditProvenanceError("pristine opportunity source ID drifted")
    if data["pristine_seed_base"] != MID_DEV_CALIBRATION_SEED_BASE:
        raise MidDevOpportunityAuditProvenanceError("pristine opportunity seed base drifted")
    if data["pristine_negatives_per_length"] != MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
        raise MidDevOpportunityAuditProvenanceError("pristine opportunity count per length drifted")
    if data["sample_count"] != 2 * MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH:
        raise MidDevOpportunityAuditProvenanceError("pristine opportunity total sample count drifted")
    if data["opportunity_cv_limit"] != OPPORTUNITY_CV_LIMIT:
        raise MidDevOpportunityAuditProvenanceError("opportunity CV limit drifted")
    if data["eligible_iqr_overlap_limit"] != ELIGIBLE_IQR_OVERLAP_LIMIT:
        raise MidDevOpportunityAuditProvenanceError("eligible IQR overlap limit drifted")
    if data["tokenizer_round_trip_all_ok"] is not True:
        raise MidDevOpportunityAuditProvenanceError("opportunity provenance reports tokenizer round-trip failure")
    for name in ("attack_transform_count", "attack_score_count", "detector_score_count"):
        if data[name] != 0:
            raise MidDevOpportunityAuditProvenanceError(f"{name} must remain zero")
    if data["calibration_threshold_constructed"] is not False:
        raise MidDevOpportunityAuditProvenanceError("opportunity workflow must not construct threshold")
    if data["cal_select_or_audit_samples_consumed"] is not False:
        raise MidDevOpportunityAuditProvenanceError("opportunity workflow must not consume CAL-SELECT/AUDIT samples")
    for name in ("corpus_fsync_success", "opportunity_audit_fsync_success", "regime_decision_fsync_success"):
        if data[name] is not True:
            raise MidDevOpportunityAuditProvenanceError(f"{name} must be true")
    payload = {key: value for key, value in data.items() if key != "provenance_hash"}
    if data["provenance_hash"] != sha256_json(payload):
        raise MidDevOpportunityAuditProvenanceError("opportunity audit provenance hash does not replay")
    if require_canonical:
        canonical = canonical_json_text(data)
        if text not in (canonical, canonical + "\n"):
            raise MidDevOpportunityAuditProvenanceError("opportunity audit provenance JSON is not canonical")
    return dict(data)


def load_mid_dev_opportunity_audit_provenance_json(
    path: str | Path,
    *,
    require_canonical: bool = True,
) -> dict[str, object]:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_MAX_BYTES:
        raise MidDevOpportunityAuditProvenanceError("opportunity audit provenance exceeds size limit")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MidDevOpportunityAuditProvenanceError("opportunity audit provenance must be UTF-8") from error
    return parse_mid_dev_opportunity_audit_provenance_json(text, require_canonical=require_canonical)
