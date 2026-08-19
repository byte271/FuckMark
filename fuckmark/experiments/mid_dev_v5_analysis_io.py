from __future__ import annotations

from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _array, _mapping
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json
from .mid_dev_v5_geometry_audit import MidDevV5GeometryAuditArtifact, MidDevV5GeometryAuditRow
from .mid_dev_v5_rule_usage import MidDevV5RuleUsageArtifact, MidDevV5RuleUsageTrace
from .mid_dev_v5_scoring import (
    MidDevV5ScoreValue,
    MidDevV5ScoredRow,
    MidDevV5ScoredRowKind,
    MidDevV5ScoringArtifact,
)


def _canonical_check(text: str, value, label: str) -> None:
    canonical = canonical_json_text(value)
    if text not in (canonical, canonical + "\n"):
        raise MidDevPlanJsonError(f"{label} JSON is not canonical")


def _score_value(value: object) -> MidDevV5ScoreValue:
    data = _mapping(
        "mid_dev_v5_score_value",
        value,
        (
            "text_hash",
            "token_hash",
            "eligibility_mask_hash",
            "eligible_observation_count",
            "regime_id",
            "calibration_regime_hash",
            "threshold_record_hash",
            "threshold_hash",
            "threshold_value",
            "raw_score",
            "margin",
            "detected",
            "detector_identity_hash",
            "value_hash",
        ),
    )
    return MidDevV5ScoreValue(**data)


def _scored_row(value: object) -> MidDevV5ScoredRow:
    data = _mapping(
        "mid_dev_v5_scored_row",
        value,
        (
            "row_kind",
            "plan_row_hash",
            "source_group_id",
            "sample_id",
            "source_label",
            "target_length",
            "planner_or_condition",
            "tier",
            "budget",
            "replicate",
            "selection_trace_hash",
            "transformed_text_hash",
            "pristine_score",
            "transformed_score",
            "residual_geometry_hash",
            "residual_inherited_fraction",
            "new_context_opportunity_fraction",
            "valid_denominator_ratio",
            "word_edit_rate",
            "character_edit_rate",
            "token_edit_distance",
            "length_ratio",
            "protected_span_violation_count",
            "hard_invariant_passed",
            "row_hash",
        ),
    )
    return MidDevV5ScoredRow(
        row_kind=MidDevV5ScoredRowKind(data["row_kind"]),
        plan_row_hash=data["plan_row_hash"],
        source_group_id=data["source_group_id"],
        sample_id=data["sample_id"],
        source_label=data["source_label"],
        target_length=data["target_length"],
        planner_or_condition=data["planner_or_condition"],
        tier=data["tier"],
        budget=data["budget"],
        replicate=data["replicate"],
        selection_trace_hash=data["selection_trace_hash"],
        transformed_text_hash=data["transformed_text_hash"],
        pristine_score=_score_value(data["pristine_score"]),
        transformed_score=_score_value(data["transformed_score"]),
        residual_geometry_hash=data["residual_geometry_hash"],
        residual_inherited_fraction=data["residual_inherited_fraction"],
        new_context_opportunity_fraction=data["new_context_opportunity_fraction"],
        valid_denominator_ratio=data["valid_denominator_ratio"],
        word_edit_rate=data["word_edit_rate"],
        character_edit_rate=data["character_edit_rate"],
        token_edit_distance=data["token_edit_distance"],
        length_ratio=data["length_ratio"],
        protected_span_violation_count=data["protected_span_violation_count"],
        hard_invariant_passed=data["hard_invariant_passed"],
        row_hash=data["row_hash"],
    )


def parse_mid_dev_v5_scoring_artifact_json(text: str, *, require_canonical: bool = True) -> MidDevV5ScoringArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_v5_scoring_artifact",
            decoded,
            (
                "corpus_artifact_hash",
                "source_profile_hash",
                "analysis_split_hash",
                "development_plan_hash",
                "normalized_trace_artifact_hash",
                "execution_attestation_hash",
                "opportunity_audit_hash",
                "regime_decision_hash",
                "threshold_registry_hash",
                "detector_identity_hash",
                "independent_source_group_count",
                "source_sample_count",
                "rows",
                "artifact_hash",
            ),
        )
        artifact = MidDevV5ScoringArtifact(
            corpus_artifact_hash=data["corpus_artifact_hash"],
            source_profile_hash=data["source_profile_hash"],
            analysis_split_hash=data["analysis_split_hash"],
            development_plan_hash=data["development_plan_hash"],
            normalized_trace_artifact_hash=data["normalized_trace_artifact_hash"],
            execution_attestation_hash=data["execution_attestation_hash"],
            opportunity_audit_hash=data["opportunity_audit_hash"],
            regime_decision_hash=data["regime_decision_hash"],
            threshold_registry_hash=data["threshold_registry_hash"],
            detector_identity_hash=data["detector_identity_hash"],
            independent_source_group_count=data["independent_source_group_count"],
            source_sample_count=data["source_sample_count"],
            rows=tuple(_scored_row(value) for value in _array("rows", data["rows"])),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev v5 scoring artifact failed validation") from error
    if require_canonical:
        _canonical_check(text, artifact, "MidDev v5 scoring artifact")
    return artifact


def _geometry_row(value: object) -> MidDevV5GeometryAuditRow:
    fields = tuple(MidDevV5GeometryAuditRow.__dataclass_fields__)
    return MidDevV5GeometryAuditRow(**_mapping("mid_dev_v5_geometry_audit_row", value, fields))


def parse_mid_dev_v5_geometry_audit_json(text: str, *, require_canonical: bool = True) -> MidDevV5GeometryAuditArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_v5_geometry_audit",
            decoded,
            (
                "corpus_artifact_hash",
                "development_plan_hash",
                "scoring_artifact_hash",
                "opportunity_audit_hash",
                "repetition_mask_growth_cap",
                "rows",
                "artifact_hash",
            ),
        )
        artifact = MidDevV5GeometryAuditArtifact(
            corpus_artifact_hash=data["corpus_artifact_hash"],
            development_plan_hash=data["development_plan_hash"],
            scoring_artifact_hash=data["scoring_artifact_hash"],
            opportunity_audit_hash=data["opportunity_audit_hash"],
            repetition_mask_growth_cap=data["repetition_mask_growth_cap"],
            rows=tuple(_geometry_row(value) for value in _array("rows", data["rows"])),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev v5 geometry audit failed validation") from error
    if require_canonical:
        _canonical_check(text, artifact, "MidDev v5 geometry audit")
    return artifact


def _rule_trace(value: object) -> MidDevV5RuleUsageTrace:
    data = _mapping(
        "mid_dev_v5_rule_usage_trace",
        value,
        ("trace_kind", "selection_trace_hash", "sample_id", "rule_hashes", "trace_hash"),
    )
    rule_hashes = data["rule_hashes"]
    if not isinstance(rule_hashes, list) or any(not isinstance(item, str) for item in rule_hashes):
        raise TypeError("rule_hashes must be a JSON array of strings")
    return MidDevV5RuleUsageTrace(
        trace_kind=data["trace_kind"],
        selection_trace_hash=data["selection_trace_hash"],
        sample_id=data["sample_id"],
        rule_hashes=tuple(rule_hashes),
        trace_hash=data["trace_hash"],
    )


def parse_mid_dev_v5_rule_usage_json(text: str, *, require_canonical: bool = True) -> MidDevV5RuleUsageArtifact:
    decoded = _parse_json(text)
    try:
        data = _mapping(
            "mid_dev_v5_rule_usage",
            decoded,
            (
                "development_plan_hash",
                "legacy_trace_artifact_hash",
                "normalized_trace_artifact_hash",
                "selection_attestation_hash",
                "candidate_registry_hash",
                "traces",
                "rule_usage_counts",
                "artifact_hash",
            ),
        )
        raw_counts = data["rule_usage_counts"]
        if not isinstance(raw_counts, list):
            raise TypeError("rule_usage_counts must be a JSON array")
        counts = []
        for value in raw_counts:
            if not isinstance(value, list) or len(value) != 2 or not isinstance(value[0], str) or isinstance(value[1], bool) or not isinstance(value[1], int):
                raise TypeError("rule_usage_counts entries must be [hash, count]")
            counts.append((value[0], value[1]))
        artifact = MidDevV5RuleUsageArtifact(
            development_plan_hash=data["development_plan_hash"],
            legacy_trace_artifact_hash=data["legacy_trace_artifact_hash"],
            normalized_trace_artifact_hash=data["normalized_trace_artifact_hash"],
            selection_attestation_hash=data["selection_attestation_hash"],
            candidate_registry_hash=data["candidate_registry_hash"],
            traces=tuple(_rule_trace(value) for value in _array("traces", data["traces"])),
            rule_usage_counts=tuple(counts),
            artifact_hash=data["artifact_hash"],
        )
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("MidDev v5 rule-usage artifact failed validation") from error
    if require_canonical:
        _canonical_check(text, artifact, "MidDev v5 rule-usage artifact")
    return artifact


def _load(path: str | Path, parser):
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES * 8:
        raise MidDevPlanJsonError("MidDev v5 analysis input JSON exceeds the size limit")
    return parser(file_path.read_text(encoding="utf-8"))


def load_mid_dev_v5_scoring_artifact_json(path: str | Path) -> MidDevV5ScoringArtifact:
    return _load(path, parse_mid_dev_v5_scoring_artifact_json)


def load_mid_dev_v5_geometry_audit_json(path: str | Path) -> MidDevV5GeometryAuditArtifact:
    return _load(path, parse_mid_dev_v5_geometry_audit_json)


def load_mid_dev_v5_rule_usage_json(path: str | Path) -> MidDevV5RuleUsageArtifact:
    return _load(path, parse_mid_dev_v5_rule_usage_json)
