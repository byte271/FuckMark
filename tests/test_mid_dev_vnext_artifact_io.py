import pytest

from fuckmark.config import canonical_json_text
from fuckmark.detector_calibration import PRIMARY_TARGET_FPR
from fuckmark.detectors import ComparisonOperator
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.detector_opportunity_audit import (
    CALIBRATION_REGIME_DECISION_VERSION,
    DETECTOR_OPPORTUNITY_AUDIT_VERSION,
    CalibrationRegimeDecision,
    CalibrationRegimeMode,
    CountDistribution,
    DetectorOpportunityAuditArtifact,
    OpportunityLengthSummary,
)
from fuckmark.experiments.mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_CONFIDENCE_LEVEL,
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
    FrozenCalibrationThresholdRecord,
    FrozenCalibrationThresholdRegistry,
)
from fuckmark.experiments.mid_dev_vnext_artifact_io import (
    parse_calibration_regime_decision_json,
    parse_detector_opportunity_audit_json,
    parse_frozen_calibration_threshold_registry_json,
)
from fuckmark.experiments.mid_dev_plan_io import MidDevPlanJsonError
from fuckmark.hashing import sha256_json, sha256_text


def _summary(target):
    distribution = CountDistribution(1, 100, 100.0, 100.0, 100.0, 100, 100.0, 0.0)
    payload = {
        "nominal_target_length": target,
        "text_only_tokens": distribution.payload(),
        "candidate_observations": distribution.payload(),
        "eligible_observations": distribution.payload(),
        "repeated_context_masked": distribution.payload(),
        "eos_masked": distribution.payload(),
        "decoded_utf8_length": distribution.payload(),
        "tokenizer_round_trip_failures": 0,
    }
    return OpportunityLengthSummary(
        target,
        distribution,
        distribution,
        distribution,
        distribution,
        distribution,
        distribution,
        0,
        sha256_json(payload),
    )


def _audit():
    summaries = (_summary(128), _summary(256))
    payload = {
        "algorithm_version": DETECTOR_OPPORTUNITY_AUDIT_VERSION,
        "ngram_len": 5,
        "context_history_size": 1024,
        "rows": (),
        "summaries": tuple(summary.payload() | {"summary_hash": summary.summary_hash} for summary in summaries),
        "model_tokenizer_identity_hash": sha256_text("model"),
        "watermark_config_hash": sha256_text("wm-config"),
        "watermark_condition_hash": sha256_text("wm-condition"),
    }
    return DetectorOpportunityAuditArtifact(
        algorithm_version=DETECTOR_OPPORTUNITY_AUDIT_VERSION,
        ngram_len=5,
        context_history_size=1024,
        rows=(),
        summaries=summaries,
        model_tokenizer_identity_hash=payload["model_tokenizer_identity_hash"],
        watermark_config_hash=payload["watermark_config_hash"],
        watermark_condition_hash=payload["watermark_condition_hash"],
        artifact_hash=sha256_json(payload),
    )


def _decision(audit):
    payload = {
        "algorithm_version": CALIBRATION_REGIME_DECISION_VERSION,
        "opportunity_audit_hash": audit.artifact_hash,
        "mode": CalibrationRegimeMode.ELIGIBLE_OBSERVATION_BINS.value,
        "coefficient_of_variation_limit": 0.05,
        "eligible_iqr_overlap_limit": 0.10,
        "observed_eligible_iqr_overlap": 0.5,
        "nominal_strata_pass": False,
        "eligible_bin_upper_bounds": (150, 250),
    }
    return CalibrationRegimeDecision(
        algorithm_version=payload["algorithm_version"],
        opportunity_audit_hash=payload["opportunity_audit_hash"],
        mode=CalibrationRegimeMode.ELIGIBLE_OBSERVATION_BINS,
        coefficient_of_variation_limit=0.05,
        eligible_iqr_overlap_limit=0.10,
        observed_eligible_iqr_overlap=0.5,
        nominal_strata_pass=False,
        eligible_bin_upper_bounds=(150, 250),
        decision_hash=sha256_json(payload),
    )


def _record(decision, detector_identity, select_manifest):
    interval = exact_binomial_interval(10, 1000, MID_DEV_CALIBRATION_CONFIDENCE_LEVEL)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
        "regime_id": "eligible-00",
        "calibration_regime_hash": sha256_text("regime"),
        "regime_decision_hash": decision.decision_hash,
        "select_manifest_hash": select_manifest,
        "select_count": 1000,
        "calibration_bundle_hash": sha256_text("bundle"),
        "detector_identity_hash": detector_identity,
        "threshold_hash": sha256_text("threshold"),
        "threshold_value": 0.25,
        "target_fpr": PRIMARY_TARGET_FPR,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": 10,
        "select_empirical_fpr": 0.01,
        "select_fpr_interval": interval,
        "length_policy_id": "vnext-eligible-bins",
    }
    return FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))


def _registry(audit, decision):
    detector_identity = sha256_text("detector")
    select_manifest = sha256_text("select")
    record = _record(decision, detector_identity, select_manifest)
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        "regime_decision_hash": decision.decision_hash,
        "opportunity_audit_hash": audit.artifact_hash,
        "select_manifest_hash": select_manifest,
        "detector_identity_hash": detector_identity,
        "records": (record.payload() | {"record_hash": record.record_hash},),
    }
    return FrozenCalibrationThresholdRegistry(
        algorithm_version=payload["algorithm_version"],
        regime_decision_hash=decision.decision_hash,
        opportunity_audit_hash=audit.artifact_hash,
        select_manifest_hash=select_manifest,
        detector_identity_hash=detector_identity,
        records=(record,),
        registry_hash=sha256_json(payload),
    )


def test_vnext_calibration_artifacts_round_trip_canonical_json():
    audit = _audit()
    decision = _decision(audit)
    registry = _registry(audit, decision)
    assert parse_detector_opportunity_audit_json(canonical_json_text(audit)) == audit
    assert parse_calibration_regime_decision_json(canonical_json_text(decision)) == decision
    assert parse_frozen_calibration_threshold_registry_json(canonical_json_text(registry)) == registry


def test_vnext_artifact_parsers_reject_noncanonical_json():
    audit = _audit()
    decision = _decision(audit)
    registry = _registry(audit, decision)
    with pytest.raises(MidDevPlanJsonError, match="not canonical"):
        parse_detector_opportunity_audit_json(canonical_json_text(audit) + " ")
    with pytest.raises(MidDevPlanJsonError, match="not canonical"):
        parse_calibration_regime_decision_json(canonical_json_text(decision) + " ")
    with pytest.raises(MidDevPlanJsonError, match="not canonical"):
        parse_frozen_calibration_threshold_registry_json(canonical_json_text(registry) + " ")


def test_actual_opportunity_regime_mapping_survives_json_round_trip():
    audit = _audit()
    decision = _decision(audit)
    replayed = parse_calibration_regime_decision_json(canonical_json_text(decision))
    assert replayed.regime_id_for(128, 100) == "eligible-00"
    assert replayed.regime_id_for(128, 200) == "eligible-01"
    assert replayed.regime_id_for(256, 400) == "eligible-02"
