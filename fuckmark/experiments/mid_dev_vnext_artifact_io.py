from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from ..detectors.calibration_types import ExactBinomialInterval
from .detector_opportunity_audit import (
    CALIBRATION_REGIME_DECISION_VERSION,
    DETECTOR_OPPORTUNITY_AUDIT_VERSION,
    CalibrationRegimeDecision,
    CalibrationRegimeMode,
    CountDistribution,
    DetectorOpportunityAuditArtifact,
    DetectorOpportunityAuditRow,
    OpportunityLengthSummary,
)
from .mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
    FrozenCalibrationThresholdRecord,
    FrozenCalibrationThresholdRegistry,
)
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json


def _canonical_check(text: str, value, label: str) -> None:
    canonical = canonical_json_text(value)
    if text not in (canonical, canonical + "\n"):
        raise MidDevPlanJsonError(f"{label} JSON is not canonical")


def _distribution(value: object) -> CountDistribution:
    data = _mapping(
        "count_distribution",
        value,
        (
            "count",
            "minimum",
            "q25",
            "median",
            "q75",
            "maximum",
            "mean",
            "coefficient_of_variation",
        ),
    )
    return CountDistribution(**data)


def _opportunity_row(value: object) -> DetectorOpportunityAuditRow:
    fields = tuple(DetectorOpportunityAuditRow.__dataclass_fields__)
    data = _mapping("opportunity_row", value, fields)
    return DetectorOpportunityAuditRow(**data)


def _opportunity_summary(value: object) -> OpportunityLengthSummary:
    data = _mapping(
        "opportunity_summary",
        value,
        (
            "nominal_target_length",
            "text_only_tokens",
            "candidate_observations",
            "eligible_observations",
            "repeated_context_masked",
            "eos_masked",
            "decoded_utf8_length",
            "tokenizer_round_trip_failures",
            "summary_hash",
        ),
    )
    return OpportunityLengthSummary(
        nominal_target_length=data["nominal_target_length"],
        text_only_tokens=_distribution(data["text_only_tokens"]),
        candidate_observations=_distribution(data["candidate_observations"]),
        eligible_observations=_distribution(data["eligible_observations"]),
        repeated_context_masked=_distribution(data["repeated_context_masked"]),
        eos_masked=_distribution(data["eos_masked"]),
        decoded_utf8_length=_distribution(data["decoded_utf8_length"]),
        tokenizer_round_trip_failures=data["tokenizer_round_trip_failures"],
        summary_hash=data["summary_hash"],
    )


def parse_detector_opportunity_audit_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> DetectorOpportunityAuditArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "detector_opportunity_audit",
            decoded,
            (
                "algorithm_version",
                "ngram_len",
                "context_history_size",
                "rows",
                "summaries",
                "model_tokenizer_identity_hash",
                "watermark_config_hash",
                "watermark_condition_hash",
                "artifact_hash",
            ),
        )
        artifact = DetectorOpportunityAuditArtifact(
            algorithm_version=data["algorithm_version"],
            ngram_len=data["ngram_len"],
            context_history_size=data["context_history_size"],
            rows=tuple(_opportunity_row(value) for value in _array("rows", data["rows"])),
            summaries=tuple(_opportunity_summary(value) for value in _array("summaries", data["summaries"])),
            model_tokenizer_identity_hash=data["model_tokenizer_identity_hash"],
            watermark_config_hash=data["watermark_config_hash"],
            watermark_condition_hash=data["watermark_condition_hash"],
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("detector opportunity audit failed validation") from error
    if artifact.algorithm_version != DETECTOR_OPPORTUNITY_AUDIT_VERSION:
        raise MidDevPlanJsonError("unsupported detector opportunity audit version")
    if require_canonical:
        _canonical_check(text, artifact, "detector opportunity audit")
    return artifact


def parse_calibration_regime_decision_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> CalibrationRegimeDecision:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "calibration_regime_decision",
            decoded,
            (
                "algorithm_version",
                "opportunity_audit_hash",
                "mode",
                "coefficient_of_variation_limit",
                "eligible_iqr_overlap_limit",
                "observed_eligible_iqr_overlap",
                "nominal_strata_pass",
                "eligible_bin_upper_bounds",
                "decision_hash",
            ),
        )
        bounds = data["eligible_bin_upper_bounds"]
        if not isinstance(bounds, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in bounds):
            raise TypeError("eligible_bin_upper_bounds must be a JSON array of integers")
        decision = CalibrationRegimeDecision(
            algorithm_version=data["algorithm_version"],
            opportunity_audit_hash=data["opportunity_audit_hash"],
            mode=CalibrationRegimeMode(data["mode"]),
            coefficient_of_variation_limit=data["coefficient_of_variation_limit"],
            eligible_iqr_overlap_limit=data["eligible_iqr_overlap_limit"],
            observed_eligible_iqr_overlap=data["observed_eligible_iqr_overlap"],
            nominal_strata_pass=data["nominal_strata_pass"],
            eligible_bin_upper_bounds=tuple(bounds),
            decision_hash=data["decision_hash"],
        )
    except Exception as error:
        raise MidDevPlanJsonError("calibration regime decision failed validation") from error
    if decision.algorithm_version != CALIBRATION_REGIME_DECISION_VERSION:
        raise MidDevPlanJsonError("unsupported calibration regime decision version")
    if require_canonical:
        _canonical_check(text, decision, "calibration regime decision")
    return decision


def _interval(value: object) -> ExactBinomialInterval:
    data = _mapping("exact_binomial_interval", value, ("method", "confidence_level", "lower", "upper"))
    return ExactBinomialInterval(**data)


def _threshold_record(value: object) -> FrozenCalibrationThresholdRecord:
    data = _mapping(
        "threshold_record",
        value,
        (
            "algorithm_version",
            "regime_id",
            "calibration_regime_hash",
            "regime_decision_hash",
            "select_manifest_hash",
            "select_count",
            "calibration_bundle_hash",
            "detector_identity_hash",
            "threshold_hash",
            "threshold_value",
            "target_fpr",
            "comparison_operator",
            "select_false_positive_count",
            "select_empirical_fpr",
            "select_fpr_interval",
            "length_policy_id",
            "record_hash",
        ),
    )
    return FrozenCalibrationThresholdRecord(
        algorithm_version=data["algorithm_version"],
        regime_id=data["regime_id"],
        calibration_regime_hash=data["calibration_regime_hash"],
        regime_decision_hash=data["regime_decision_hash"],
        select_manifest_hash=data["select_manifest_hash"],
        select_count=data["select_count"],
        calibration_bundle_hash=data["calibration_bundle_hash"],
        detector_identity_hash=data["detector_identity_hash"],
        threshold_hash=data["threshold_hash"],
        threshold_value=data["threshold_value"],
        target_fpr=data["target_fpr"],
        comparison_operator=data["comparison_operator"],
        select_false_positive_count=data["select_false_positive_count"],
        select_empirical_fpr=data["select_empirical_fpr"],
        select_fpr_interval=_interval(data["select_fpr_interval"]),
        length_policy_id=data["length_policy_id"],
        record_hash=data["record_hash"],
    )


def parse_frozen_calibration_threshold_registry_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> FrozenCalibrationThresholdRegistry:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "frozen_calibration_threshold_registry",
            decoded,
            (
                "algorithm_version",
                "regime_decision_hash",
                "opportunity_audit_hash",
                "select_manifest_hash",
                "detector_identity_hash",
                "records",
                "registry_hash",
            ),
        )
        registry = FrozenCalibrationThresholdRegistry(
            algorithm_version=data["algorithm_version"],
            regime_decision_hash=data["regime_decision_hash"],
            opportunity_audit_hash=data["opportunity_audit_hash"],
            select_manifest_hash=data["select_manifest_hash"],
            detector_identity_hash=data["detector_identity_hash"],
            records=tuple(_threshold_record(value) for value in _array("records", data["records"])),
            registry_hash=data["registry_hash"],
        )
    except Exception as error:
        raise MidDevPlanJsonError("frozen calibration threshold registry failed validation") from error
    if registry.algorithm_version != MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION:
        raise MidDevPlanJsonError("unsupported threshold registry version")
    if any(record.algorithm_version != MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION for record in registry.records):
        raise MidDevPlanJsonError("unsupported threshold record version")
    if require_canonical:
        _canonical_check(text, registry, "frozen calibration threshold registry")
    return registry


def _load(path: str | Path, parser):
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("vNext artifact JSON exceeds the size limit")
    return parser(file_path.read_text(encoding="utf-8"))


def load_detector_opportunity_audit_json(path: str | Path) -> DetectorOpportunityAuditArtifact:
    return _load(path, parse_detector_opportunity_audit_json)


def load_calibration_regime_decision_json(path: str | Path) -> CalibrationRegimeDecision:
    return _load(path, parse_calibration_regime_decision_json)


def load_frozen_calibration_threshold_registry_json(path: str | Path) -> FrozenCalibrationThresholdRegistry:
    return _load(path, parse_frozen_calibration_threshold_registry_json)
