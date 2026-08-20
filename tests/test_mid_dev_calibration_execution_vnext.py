from __future__ import annotations

import ast
from pathlib import Path

from fuckmark.config import canonical_json_text
from fuckmark.corpus.mid_dev_calibration import (
    MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH,
    MID_DEV_CALIBRATION_SEED_BASE,
    MID_DEV_CALIBRATION_SOURCE_ID,
)
from fuckmark.corpus.mid_dev_calibration_shards import CalibrationRole, calibration_prompt_source_id
from fuckmark.detectors import ComparisonOperator
from fuckmark.detectors.calibration_statistics import exact_binomial_interval
from fuckmark.experiments.mid_dev_calibration_audit import (
    MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
    MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
    CalibrationAuditArtifact,
    FrozenCalibrationThresholdRecord,
    FrozenCalibrationThresholdRegistry,
)
from fuckmark.experiments.mid_dev_calibration_audit_registry import (
    CALIBRATION_AUDIT_UNSTABLE_REASON,
    build_mid_dev_calibration_audit_registry,
)
from fuckmark.experiments.mid_dev_calibration_audit_registry_io import (
    parse_mid_dev_calibration_audit_registry_json,
)
from fuckmark.experiments.mid_dev_calibration_merge_provenance_io import (
    MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION,
)
from fuckmark.experiments.mid_dev_calibration_threshold_provenance_io import (
    MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION,
)
from fuckmark.experiments.mid_dev_opportunity_audit_provenance_io import (
    MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION,
)
from fuckmark.hashing import sha256_json


def _threshold_record() -> FrozenCalibrationThresholdRecord:
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_RECORD_VERSION,
        "regime_id": "nominal-128",
        "calibration_regime_hash": "1" * 64,
        "regime_decision_hash": "2" * 64,
        "select_manifest_hash": "3" * 64,
        "select_count": 1000,
        "calibration_bundle_hash": "4" * 64,
        "detector_identity_hash": "5" * 64,
        "threshold_hash": "6" * 64,
        "threshold_value": 0.5,
        "target_fpr": 0.01,
        "comparison_operator": ComparisonOperator.GREATER_THAN_OR_EQUAL.value,
        "select_false_positive_count": 10,
        "select_empirical_fpr": 0.01,
        "select_fpr_interval": exact_binomial_interval(10, 1000, 0.95),
        "length_policy_id": "vnext-nominal-test",
    }
    return FrozenCalibrationThresholdRecord(**payload, record_hash=sha256_json(payload))


def _threshold_registry(record: FrozenCalibrationThresholdRecord) -> FrozenCalibrationThresholdRegistry:
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        "regime_decision_hash": record.regime_decision_hash,
        "opportunity_audit_hash": "7" * 64,
        "select_manifest_hash": record.select_manifest_hash,
        "detector_identity_hash": record.detector_identity_hash,
        "record_hashes": (record.record_hash,),
    }
    return FrozenCalibrationThresholdRegistry(
        MID_DEV_CALIBRATION_THRESHOLD_REGISTRY_VERSION,
        record.regime_decision_hash,
        "7" * 64,
        record.select_manifest_hash,
        record.detector_identity_hash,
        (record,),
        sha256_json(payload),
    )


def _audit_artifact(record: FrozenCalibrationThresholdRecord, false_positives: int) -> CalibrationAuditArtifact:
    count = 1000
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_AUDIT_ARTIFACT_VERSION,
        "model_tokenizer_identity_hash": "8" * 64,
        "detector_identity_hash": record.detector_identity_hash,
        "calibration_regime_hash": record.calibration_regime_hash,
        "regime_id": record.regime_id,
        "regime_decision_hash": record.regime_decision_hash,
        "select_manifest_hash": record.select_manifest_hash,
        "select_count": record.select_count,
        "threshold_hash": record.threshold_hash,
        "threshold_value": record.threshold_value,
        "target_fpr": record.target_fpr,
        "comparison_operator": record.comparison_operator,
        "select_false_positive_count": record.select_false_positive_count,
        "select_fpr_interval": record.select_fpr_interval,
        "audit_manifest_hash": "9" * 64,
        "audit_count": count,
        "audit_false_positive_count": false_positives,
        "audit_fpr": false_positives / count,
        "audit_fpr_interval": exact_binomial_interval(false_positives, count, 0.95),
        "length_policy_id": record.length_policy_id,
    }
    return CalibrationAuditArtifact(**payload, artifact_hash=sha256_json(payload))


def _python_source(path: str) -> tuple[str, ast.AST]:
    source = Path(path).read_text(encoding="utf-8")
    return source, ast.parse(source)


def test_d2_passes_only_when_target_fpr_is_inside_every_audit_exact_interval() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    audit = _audit_artifact(record, 10)
    result = build_mid_dev_calibration_audit_registry(registry, (audit,))
    assert audit.audit_fpr_interval.lower <= 0.01 <= audit.audit_fpr_interval.upper
    assert result.consistency_pass is True
    assert result.unstable_regime_ids == ()
    assert result.reason_code is None


def test_d2_blocks_threshold_crossing_interpretation_when_audit_is_unstable() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    audit = _audit_artifact(record, 40)
    result = build_mid_dev_calibration_audit_registry(registry, (audit,))
    assert not (audit.audit_fpr_interval.lower <= 0.01 <= audit.audit_fpr_interval.upper)
    assert result.consistency_pass is False
    assert result.unstable_regime_ids == (record.regime_id,)
    assert result.reason_code == CALIBRATION_AUDIT_UNSTABLE_REASON


def test_calibration_audit_registry_strict_io_round_trip() -> None:
    record = _threshold_record()
    registry = _threshold_registry(record)
    value = build_mid_dev_calibration_audit_registry(registry, (_audit_artifact(record, 10),))
    text = canonical_json_text(value) + "\n"
    parsed = parse_mid_dev_calibration_audit_registry_json(text)
    assert parsed.registry_hash == value.registry_hash
    assert parsed.artifacts[0].artifact_hash == value.artifacts[0].artifact_hash


def test_execution_provenance_versions_are_explicit() -> None:
    assert MID_DEV_OPPORTUNITY_AUDIT_PROVENANCE_VERSION == "mid-dev-pristine-opportunity-audit-provenance-v1"
    assert MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION == "mid-dev-calibration-merge-provenance-v1"
    assert MID_DEV_CALIBRATION_THRESHOLD_PROVENANCE_VERSION == "mid-dev-calibration-threshold-provenance-v1"


def test_threshold_cli_is_cal_select_only_and_requires_select_merge_provenance() -> None:
    source, tree = _python_source("fuckmark/mid_dev_calibration_threshold_hf.py")
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "--select-json" in constants
    assert "--select-merge-provenance-json" in constants
    assert "--audit-json" not in constants
    assert "--audit-merge-provenance-json" not in constants
    assert "audit_frozen_calibration_threshold_registry" not in source
    assert "CalibrationRole.AUDIT" not in source


def test_audit_cli_never_recalibrates_and_requires_threshold_provenance() -> None:
    source, tree = _python_source("fuckmark/mid_dev_calibration_audit_hf.py")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "calibrate_detector" not in names
    assert "build_frozen_calibration_threshold_registry" not in names
    assert "--threshold-provenance-json" in constants
    assert "threshold_recalibration_performed" in source
    assert '"threshold_recalibration_performed": False' in source


def test_calibration_shards_require_frozen_opportunity_and_regime_hashes() -> None:
    source, tree = _python_source("fuckmark/mid_dev_calibration_shard_hf.py")
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "--opportunity-audit-hash" in constants
    assert "--regime-decision-hash" in constants
    assert '"opportunity_audit_hash": args.opportunity_audit_hash' in source
    assert '"regime_decision_hash": args.regime_decision_hash' in source


def test_pair_validation_requires_both_merge_provenances() -> None:
    _, tree = _python_source("fuckmark/mid_dev_calibration_pair_validate.py")
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "--select-merge-provenance-json" in constants
    assert "--audit-merge-provenance-json" in constants


def test_merge_and_pair_validation_are_detector_free() -> None:
    for path in (
        "fuckmark/mid_dev_calibration_merge.py",
        "fuckmark/mid_dev_calibration_pair_validate.py",
        "fuckmark/corpus/mid_dev_calibration_pair.py",
    ):
        source, tree = _python_source(path)
        imported_modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not any("adapter" in value.lower() or "detector" in value.lower() for value in imported_modules)
        assert not any("adapter" in value.lower() or "detector" in value.lower() for value in imported_names)
        assert "calibrate_detector" not in source


def test_pristine_opportunity_corpus_is_small_and_independent_from_vnext_calibration_roles() -> None:
    assert MID_DEV_CALIBRATION_NEGATIVES_PER_LENGTH == 100
    assert MID_DEV_CALIBRATION_SEED_BASE == 610_000
    assert MID_DEV_CALIBRATION_SOURCE_ID not in {
        calibration_prompt_source_id(CalibrationRole.SELECT),
        calibration_prompt_source_id(CalibrationRole.AUDIT),
    }


def test_opportunity_cli_has_no_attack_or_threshold_scoring_path() -> None:
    source, tree = _python_source("fuckmark/mid_dev_opportunity_audit_hf.py")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "HuggingFaceSynthIDAdapter" not in names
    assert "calibrate_detector" not in names
    assert "build_frozen_calibration_threshold_registry" not in names
    assert "audit_frozen_calibration_threshold_registry" not in names
    assert '"attack_transform_count": 0' in source
    assert '"attack_score_count": 0' in source
    assert '"detector_score_count": 0' in source
    assert '"calibration_threshold_constructed": False' in source
    assert '"cal_select_or_audit_samples_consumed": False' in source


def test_opportunity_workflow_is_manual_only() -> None:
    source = Path(".github/workflows/middev-opportunity-audit.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "python -m fuckmark.mid_dev_opportunity_audit_hf" in source


def test_large_calibration_workflow_is_manual_and_threshold_job_cannot_see_audit_data() -> None:
    source = Path(".github/workflows/middev-calibration-shards.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "opportunity_run_id:" in source
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "calibration_shard_jobs=' + str(len(include))" in source
    assert "--opportunity-audit-hash" in source
    assert "--regime-decision-hash" in source
    threshold_block = source.split("\n  threshold:\n", 1)[1].split("\n  audit:\n", 1)[0]
    assert "needs: [preflight, merge-select]" in threshold_block
    assert "middev-cal-audit-merged" not in threshold_block
    assert "middev-calibration-pair" not in threshold_block
    assert "--audit-json" not in threshold_block
    assert "--audit-merge-provenance-json" not in threshold_block
    assert "--select-merge-provenance-json" in threshold_block
    audit_block = source.split("\n  audit:\n", 1)[1]
    assert "--threshold-provenance-json" in audit_block
    assert "CALIBRATION_AUDIT_FPR_UNSTABLE" in audit_block
