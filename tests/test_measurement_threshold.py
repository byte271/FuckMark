from __future__ import annotations

from types import SimpleNamespace

import pytest

import fuckmark.experiments.measurement_threshold as mt
from fuckmark.experiments.measurement_threshold import (
    build_fixed_threshold_artifact,
    validate_fixed_threshold_artifact,
)


class _FakeCalibrationCorpus:
    def __init__(self, calibration_scores, audit_scores) -> None:
        self.calibration_set = tuple(
            SimpleNamespace(sample_id=f"cal-{index}", score=value)
            for index, value in enumerate(calibration_scores)
        )
        self.audit_set = tuple(
            SimpleNamespace(sample_id=f"audit-{index}", score=value)
            for index, value in enumerate(audit_scores)
        )
        self.artifact_hash = "a" * 64
        self.manifest = SimpleNamespace(corpus_id="fake-calibration")

    def calibration_samples(self):
        return self.calibration_set

    def audit_samples(self):
        return self.audit_set


def _patch_scoring(monkeypatch, calibration_scores, audit_scores):
    corpus = _FakeCalibrationCorpus(calibration_scores, audit_scores)
    lookup = {sample.sample_id: sample.score for sample in (*corpus.calibration_set, *corpus.audit_set)}

    def fake_evidence(sample, adapter):
        return SimpleNamespace(raw_score=lookup[sample.sample_id])

    def fake_calibrate(evidence, scope, target_fprs, comparison_operator, confidence_level):
        return SimpleNamespace(
            detector_identity=SimpleNamespace(identity_hash="d" * 64),
            bundle_hash="b" * 64,
        )

    monkeypatch.setattr(mt, "_text_only_weighted_evidence", fake_evidence)
    monkeypatch.setattr(mt, "calibrate_detector", fake_calibrate)
    return corpus


def test_fixed_threshold_uses_frozen_order_statistic(monkeypatch) -> None:
    calibration = [index / 2000.0 for index in range(1024)]
    audit = [0.0] * 250 + [0.9] * 6
    corpus = _patch_scoring(monkeypatch, calibration, audit)
    artifact = build_fixed_threshold_artifact(corpus, None, frozen_at_utc="2026-08-23T00:00:00+00:00")
    ordered = sorted(calibration)
    assert artifact["threshold_order_statistic"] == 1015
    assert artifact["threshold"] == ordered[1014]
    assert artifact["calibration_exceedances"] == 10
    assert artifact["audit_exceedances"] == 6
    assert artifact["audit_realized_fpr"] == 6 / 256
    assert artifact["detector_identity_hash"] == "d" * 64
    assert artifact["artifact_hash"]


def test_fixed_threshold_validation_rejects_mismatches(monkeypatch) -> None:
    calibration = [index / 2000.0 for index in range(1024)]
    corpus = _patch_scoring(monkeypatch, calibration, [0.0] * 256)
    artifact = build_fixed_threshold_artifact(corpus, None, frozen_at_utc="2026-08-23T00:00:00+00:00")
    assert validate_fixed_threshold_artifact(artifact, "d" * 64) == artifact["threshold"]
    with pytest.raises(ValueError):
        validate_fixed_threshold_artifact(artifact, "e" * 64)
    tampered = dict(artifact)
    tampered["threshold"] = 0.123456
    with pytest.raises(ValueError):
        validate_fixed_threshold_artifact(tampered, "d" * 64)
    bad_version = dict(artifact)
    bad_version["algorithm_version"] = "other-v1"
    with pytest.raises(ValueError):
        validate_fixed_threshold_artifact(bad_version, "d" * 64)
