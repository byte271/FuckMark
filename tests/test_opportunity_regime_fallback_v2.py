from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fuckmark.experiments.detector_opportunity_audit import (
    CALIBRATION_REGIME_DECISION_VERSION,
    _minimal_eligible_bin_bounds,
)


def test_regime_decision_version_bumps_for_opportunity_only_fallback() -> None:
    assert CALIBRATION_REGIME_DECISION_VERSION == "mid-dev-calibration-regime-decision-v2"


def test_eligible_fallback_does_not_reject_equal_detector_opportunity_for_text_length_variation() -> None:
    rows = (
        SimpleNamespace(text_only_token_count=100, root_valid_eligible_observation_count=80),
        SimpleNamespace(text_only_token_count=250, root_valid_eligible_observation_count=80),
    )
    assert _minimal_eligible_bin_bounds(rows) == ()


def test_eligible_fallback_still_enforces_frozen_five_percent_opportunity_cv() -> None:
    rows = (
        SimpleNamespace(text_only_token_count=100, root_valid_eligible_observation_count=80),
        SimpleNamespace(text_only_token_count=100, root_valid_eligible_observation_count=81),
        SimpleNamespace(text_only_token_count=100, root_valid_eligible_observation_count=160),
        SimpleNamespace(text_only_token_count=100, root_valid_eligible_observation_count=161),
    )
    assert _minimal_eligible_bin_bounds(rows) == (120,)


def test_expensive_pristine_evidence_is_fsynced_before_regime_freeze() -> None:
    source = Path("fuckmark/mid_dev_opportunity_audit_hf.py").read_text(encoding="utf-8")
    corpus_write = source.index("write_canonical_json_fsynced(args.corpus_json, pristine)")
    audit_write = source.index("write_canonical_json_fsynced(args.opportunity_audit_json, audit)")
    freeze = source.index("decision = freeze_calibration_regime_decision(audit)")
    assert corpus_write < freeze
    assert audit_write < freeze
