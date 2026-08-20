from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.corpus.mid_dev_calibration_shards import CalibrationRole
from fuckmark.experiments.mid_dev_calibration_compaction import (
    MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
    MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
    CalibrationCompactionStatus,
    MidDevCalibrationCompactionRecord,
    _deduplicate_calibration_candidates,
    select_calibration_compaction_target,
)
from fuckmark.experiments.mid_dev_calibration_compaction_io import (
    MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION,
    MidDevCalibrationCompactionProvenanceError,
    parse_mid_dev_calibration_compaction_provenance_json,
)
from fuckmark.experiments.mid_dev_calibration_merge_provenance_io import (
    MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION,
    parse_mid_dev_calibration_merge_provenance_json,
)
from fuckmark.experiments.mid_dev_calibration_readiness import (
    FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN,
    MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE,
    MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET,
    MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE,
    MID_DEV_CALIBRATION_READINESS_SHARD_SIZE,
    MID_DEV_CALIBRATION_READINESS_VERSION,
)
from fuckmark.hashing import sha256_json


def _hash(value: str) -> str:
    return sha256_json({"value": value})


def _record(regime_id: str, candidate_count: int, selected_count: int, status: CalibrationCompactionStatus):
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
        "regime_id": regime_id,
        "source_sample_count": 1,
        "candidate_count": candidate_count,
        "selected_count": selected_count,
        "status": status.value,
        "selected_sample_ids_hash": _hash(regime_id + "-ids"),
        "selected_record_hashes_hash": _hash(regime_id + "-records"),
    }
    return MidDevCalibrationCompactionRecord(
        algorithm_version=MID_DEV_CALIBRATION_COMPACTION_RECORD_VERSION,
        regime_id=regime_id,
        source_sample_count=1,
        candidate_count=candidate_count,
        selected_count=selected_count,
        status=status,
        selected_sample_ids_hash=payload["selected_sample_ids_hash"],
        selected_record_hashes_hash=payload["selected_record_hashes_hash"],
        record_hash=sha256_json(payload),
    )


def _candidate(sample_id: str, text_key: str, token_key: str):
    return SimpleNamespace(
        sample_id=sample_id,
        text_sha256=_hash("text-" + text_key),
        generation_tokens=SimpleNamespace(
            continuation_token_hash=_hash("tokens-" + token_key),
        ),
    )


def test_v2_readiness_freezes_40k_candidates_per_role_in_80_shards() -> None:
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    assert MID_DEV_CALIBRATION_READINESS_VERSION == "mid-dev-calibration-readiness-v2"
    assert MID_DEV_CALIBRATION_READINESS_NEGATIVES_PER_TARGET == 20_000
    assert MID_DEV_CALIBRATION_READINESS_SHARD_SIZE == 500
    assert MID_DEV_CALIBRATION_READINESS_SHARDS_PER_ROLE == 80
    assert MID_DEV_CALIBRATION_CANDIDATES_PER_ROLE == 40_000
    assert readiness.negatives_per_target == 20_000
    assert readiness.shard_size == 500
    assert len(readiness.select_plan.shards) == 80
    assert len(readiness.audit_plan.shards) == 80
    assert len(readiness.select_plan.prompt_ids) == 40_000
    assert len(readiness.audit_plan.prompt_ids) == 40_000


@pytest.mark.parametrize(
    ("candidate_count", "status", "selected_count"),
    (
        (0, CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE, 0),
        (999, CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE, 0),
        (1000, CalibrationCompactionStatus.SERIOUS_THRESHOLD, 1000),
        (1999, CalibrationCompactionStatus.SERIOUS_THRESHOLD, 1000),
        (2000, CalibrationCompactionStatus.SERIOUS_THRESHOLD, 2000),
        (5000, CalibrationCompactionStatus.SERIOUS_THRESHOLD, 2000),
    ),
)
def test_compaction_N_policy_is_frozen(candidate_count, status, selected_count) -> None:
    assert select_calibration_compaction_target(candidate_count) == (status, selected_count)


def test_compaction_rejects_invalid_candidate_count() -> None:
    with pytest.raises(ValueError):
        select_calibration_compaction_target(-1)


def test_detector_blind_dedup_keeps_first_occurrence_by_text_or_token_hash() -> None:
    candidates = (
        _candidate("first", "shared-text", "shared-token"),
        _candidate("drop-text", "shared-text", "different-token"),
        _candidate("drop-token", "different-text", "shared-token"),
        _candidate("second", "unique-text", "unique-token"),
    )
    unique, excluded = _deduplicate_calibration_candidates(candidates)
    assert tuple(item.sample_id for item in unique) == ("first", "second")
    assert excluded == ("drop-text", "drop-token")


def test_duplicate_raw_attempt_cannot_manufacture_serious_N() -> None:
    candidates = tuple(
        _candidate(f"unique-{index:04d}", f"text-{index:04d}", f"token-{index:04d}")
        for index in range(999)
    ) + (_candidate("duplicate-1000", "text-0000", "token-extra"),)
    assert len(candidates) == 1000
    unique, excluded = _deduplicate_calibration_candidates(candidates)
    assert len(unique) == 999
    assert excluded == ("duplicate-1000",)
    assert select_calibration_compaction_target(len(unique)) == (
        CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE,
        0,
    )


def test_compaction_selection_rule_explicitly_binds_content_dedup() -> None:
    assert "DEDUP_TEXT_OR_TOKEN_SHA" in MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE
    assert "FROZEN_CANDIDATE_ORDER" in MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE


def _compaction_provenance_value() -> dict[str, object]:
    serious = _record("eligible-04", 1200, 1000, CalibrationCompactionStatus.SERIOUS_THRESHOLD)
    descriptive = _record(
        "eligible-03",
        400,
        0,
        CalibrationCompactionStatus.COMPUTE_LIMITED_DESCRIPTIVE,
    )
    records = tuple(sorted((descriptive, serious), key=lambda item: item.regime_id))
    excluded = ("duplicate-a", "duplicate-b", "duplicate-c")
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_COMPACTION_PROVENANCE_VERSION,
        "role": CalibrationRole.SELECT.value,
        "readiness_hash": _hash("readiness"),
        "plan_hash": _hash("plan"),
        "candidate_pool_artifact_hash": _hash("candidate-artifact"),
        "candidate_pool_manifest_hash": _hash("candidate-manifest"),
        "candidate_merge_provenance_hash": _hash("merge"),
        "calibration_opportunity_audit_hash": _hash("opportunity"),
        "regime_decision_hash": _hash("regime"),
        "source_coverage_artifact_hash": _hash("coverage"),
        "source_coverage_provenance_hash": _hash("coverage-prov"),
        "selection_rule": MID_DEV_CALIBRATION_COMPACTION_SELECTION_RULE,
        "preferred_n": 2000,
        "minimum_n": 1000,
        "candidate_count_total": 40_000,
        "unique_candidate_count_total": 39_997,
        "duplicate_excluded_count": 3,
        "duplicate_excluded_sample_ids_hash": sha256_json(excluded),
        "selected_count_total": 1000,
        "required_regime_ids": tuple(item.regime_id for item in records),
        "serious_regime_ids": ("eligible-04",),
        "descriptive_regime_ids": ("eligible-03",),
        "records": tuple(item.payload() | {"record_hash": item.record_hash} for item in records),
        "compacted_artifact_hash": _hash("compacted-artifact"),
        "compacted_manifest_hash": _hash("compacted-manifest"),
        "select_compaction_provenance_hash": None,
        "attack_transform_count": 0,
        "attack_score_count": 0,
        "detector_score_count": 0,
        "calibration_threshold_constructed": False,
        "json_fsync_success": True,
        "github_run_id": None,
        "github_run_attempt": None,
        "github_event_name": None,
        "github_checkout_sha": None,
    }
    return {**payload, "provenance_hash": sha256_json(payload)}


def test_compaction_provenance_strict_round_trip() -> None:
    value = _compaction_provenance_value()
    parsed = parse_mid_dev_calibration_compaction_provenance_json(canonical_json_text(value) + "\n")
    assert parsed["serious_regime_ids"] == ["eligible-04"]
    assert parsed["descriptive_regime_ids"] == ["eligible-03"]
    assert parsed["candidate_count_total"] == 40_000
    assert parsed["unique_candidate_count_total"] == 39_997
    assert parsed["duplicate_excluded_count"] == 3
    assert parsed["selected_count_total"] == 1000


def test_compaction_provenance_rejects_nonreplaying_duplicate_count() -> None:
    value = _compaction_provenance_value()
    value["duplicate_excluded_count"] = 4
    payload = {key: item for key, item in value.items() if key != "provenance_hash"}
    value["provenance_hash"] = sha256_json(payload)
    with pytest.raises(MidDevCalibrationCompactionProvenanceError, match="duplicate exclusion count"):
        parse_mid_dev_calibration_compaction_provenance_json(canonical_json_text(value) + "\n")


def test_merge_provenance_parser_uses_v2_readiness_dimensions() -> None:
    readiness = FROZEN_MID_DEV_CALIBRATION_READINESS_PLAN
    plan = readiness.select_plan
    shard_hashes = tuple(_hash(f"shard-{index}") for index in range(len(plan.shards)))
    payload = {
        "algorithm_version": MID_DEV_CALIBRATION_MERGE_PROVENANCE_VERSION,
        "readiness_hash": readiness.readiness_hash,
        "opportunity_audit_hash": _hash("opportunity"),
        "regime_decision_hash": _hash("regime"),
        "role": CalibrationRole.SELECT.value,
        "plan_hash": plan.plan_hash,
        "shard_provenance_hashes": shard_hashes,
        "merged_manifest_hash": _hash("manifest"),
        "merged_artifact_hash": _hash("artifact"),
        "sample_count": len(plan.prompt_ids),
        "json_fsync_success": True,
        "github_run_id": None,
        "github_run_attempt": None,
        "github_event_name": None,
        "github_checkout_sha": None,
    }
    value = {**payload, "provenance_hash": sha256_json(payload)}
    parsed = parse_mid_dev_calibration_merge_provenance_json(canonical_json_text(value) + "\n")
    assert len(parsed["shard_provenance_hashes"]) == 80
    assert parsed["sample_count"] == 40_000


def test_compaction_modules_are_detector_score_free() -> None:
    for path in (
        "fuckmark/experiments/mid_dev_calibration_compaction.py",
        "fuckmark/mid_dev_calibration_compact_hf.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source)
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
        assert not any("adapter" in value.lower() for value in imported_modules | imported_names)
        assert not any("detector_calibration" in value for value in imported_modules)
        assert "calibrate_detector" not in source
        assert "text_only_weighted_evidence" not in source
        assert "build_frozen_calibration_threshold_registry" not in source
        assert "audit_frozen_calibration_threshold_registry" not in source


def test_compacted_threshold_cli_is_select_only() -> None:
    source = Path("fuckmark/mid_dev_calibration_threshold_compacted_hf.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "--select-json" in constants
    assert "--select-compaction-provenance-json" in constants
    assert "--audit-json" not in constants
    assert "--audit-compaction-provenance-json" not in constants
    assert "audit_frozen_calibration_threshold_registry" not in source


def test_compacted_audit_cli_cannot_recalibrate() -> None:
    source = Path("fuckmark/mid_dev_calibration_audit_compacted_hf.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "calibrate_detector" not in names
    assert "build_frozen_calibration_threshold_registry" not in names
    assert '"threshold_recalibration_performed": False' in source
    assert "--candidate-pair-json" in {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
