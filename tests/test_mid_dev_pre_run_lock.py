from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fuckmark.config import canonical_json_text
from fuckmark.experiments.mid_dev_pre_run_lock import (
    PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE,
    PRE_RUN_ROLE,
    PreRunScientificLock,
    create_pre_run_scientific_lock,
)
from fuckmark.experiments.mid_dev_pre_run_lock_io import parse_pre_run_scientific_lock_json
from fuckmark.hashing import sha256_text
from fuckmark.search.beam_v3_promotion import FROZEN_BEAM_V3_PROMOTION_LOCK


def _h(name: str) -> str:
    return sha256_text(name)


def _lock() -> PreRunScientificLock:
    return create_pre_run_scientific_lock(
        source_code_commit="a" * 40,
        development_plan_hash=_h("development-plan"),
        corpus_artifact_hash=_h("corpus-artifact"),
        corpus_manifest_hash=_h("corpus-manifest"),
        source_profile_hash=_h("source-profile"),
        analysis_split_hash=_h("analysis-split"),
        model_tokenizer_identity_hash=_h("model-tokenizer"),
        model_revision="b" * 40,
        tokenizer_revision="c" * 40,
        watermark_config_hash=_h("watermark-config"),
        watermark_condition_hash=_h("watermark-condition"),
        detector_identity_hash=_h("detector-identity"),
        detector_implementation_hash=_h("detector-implementation"),
        opportunity_audit_hash=_h("opportunity-audit"),
        calibration_regime_decision_hash=_h("regime-decision"),
        cal_select_manifest_hash=_h("cal-select"),
        cal_audit_manifest_hash=_h("cal-audit"),
        threshold_registry_hash=_h("threshold-registry"),
        calibration_audit_artifact_hashes=(_h("audit-a"), _h("audit-b")),
        residual_signal_implementation_hash=_h("residual-implementation"),
        candidate_rule_registry_hash=_h("candidate-registry"),
        candidate_rule_hashes=(_h("rule-a"), _h("rule-b")),
        protected_span_implementation_hash=_h("protected-implementation"),
        candidate_enumeration_policy_hash=_h("candidate-enumeration"),
        normalized_frontier_artifact_hash=_h("normalized-frontier"),
        source_analysis_rules_hash=_h("source-analysis-rules"),
        bootstrap_seed_schedule_hash=_h("bootstrap-seed-schedule"),
        pilot_seed_schedule_hash=_h("pilot-seed-schedule"),
        random_safe_policy_hash=_h("random-safe-policy"),
        pristine_watermarked_tpr_interpretability_floor=0.80,
        negative_control_shift_ratio_limit=0.50,
    )


def test_pre_run_lock_is_development_only_and_binds_frozen_k2():
    lock = _lock()
    assert lock.role == PRE_RUN_ROLE
    assert lock.pilot_source_group_count == 36
    assert lock.pilot_source_sample_count == 72
    assert lock.beam_v3_promoted is False
    assert lock.beam_v3_gate_decision == FROZEN_BEAM_V3_PROMOTION_LOCK.gate_decision
    assert lock.beam_v3_promotion_lock_hash == FROZEN_BEAM_V3_PROMOTION_LOCK.lock_hash
    assert lock.human_audit_sampling_rule == PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE


def test_pre_run_lock_rejects_select_audit_aliasing():
    lock = _lock()
    with pytest.raises(ValueError, match="independent"):
        replace(lock, cal_audit_manifest_hash=lock.cal_select_manifest_hash)


def test_pre_run_lock_rejects_beam_v3_promotion_or_policy_drift():
    lock = _lock()
    with pytest.raises(ValueError, match="Beam v3"):
        replace(lock, beam_v3_promoted=True)
    with pytest.raises(ValueError, match="STRICT"):
        replace(lock, strict_policy_hash=_h("wrong-strict"))


def test_pre_run_lock_canonical_json_round_trip():
    lock = _lock()
    text = canonical_json_text(lock)
    assert parse_pre_run_scientific_lock_json(text) == lock
    with pytest.raises(Exception):
        parse_pre_run_scientific_lock_json(text + " ")


def test_real_middev_workflow_is_fail_closed_until_step26():
    workflow = Path(".github/workflows/mid-dev-context-survival.yml").read_text(encoding="utf-8")
    assert "Validate pre-run scientific lock" in workflow
    assert "Block legacy execution until vNext plan is frozen" in workflow
    assert "PRE_RUN_LOCK_REQUIRED_AND_VNEXT_WORKFLOW_NOT_YET_FROZEN" in workflow
    assert workflow.index("Validate pre-run scientific lock") < workflow.index("Generate frozen MidDev source matrix")
