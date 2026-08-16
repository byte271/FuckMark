from dataclasses import replace

import pytest

from fuckmark.detectors import BaselineStatus, CalibrationIdentityError, apply_calibration, calibrate_detector, evaluate_pristine_baseline
from fuckmark.hashing import sha256_json, sha256_text

from calibration_helpers import _base_evidence, _evidence_scores, _scope


def test_standardized_margin_and_result_hash_are_bound() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    base = _base_evidence()
    scored = replace(base, sample_id="scored", observation_batch_hash=sha256_text("scored"), raw_score=1.0)
    result = apply_calibration(scored, bundle, 0.01)
    expected = (result.raw_score - result.threshold_value) / result.robust_scale
    assert result.standardized_margin == expected
    with pytest.raises(ValueError, match="standardized_margin"):
        replace(result, standardized_margin=result.standardized_margin + 1.0)
    with pytest.raises(ValueError, match="result_hash"):
        replace(result, result_hash="0" * 64)


def test_pristine_baseline_floor_pass_and_fail() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    base = _base_evidence()
    values = []
    for index in range(10):
        evidence = replace(
            base,
            sample_id=f"positive-{index}",
            observation_batch_hash=sha256_text(f"positive-{index}"),
            raw_score=1.0 if index < 8 else 0.0,
        )
        values.append(apply_calibration(evidence, bundle, 0.01))
    passed = evaluate_pristine_baseline(tuple(values), interpretability_floor=0.80)
    failed = evaluate_pristine_baseline(tuple(values), interpretability_floor=0.81)
    assert passed.tpr == 0.8
    assert passed.status is BaselineStatus.PASS
    assert failed.status is BaselineStatus.BELOW_FLOOR


def test_pristine_baseline_rejects_mixed_thresholds() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.05, 0.01))
    base = _base_evidence()
    first = apply_calibration(replace(base, sample_id="p1", observation_batch_hash=sha256_text("p1")), bundle, 0.05)
    second = apply_calibration(replace(base, sample_id="p2", observation_batch_hash=sha256_text("p2")), bundle, 0.01)
    with pytest.raises(CalibrationIdentityError, match="mix"):
        evaluate_pristine_baseline((first, second))


def test_pristine_baseline_accepts_full_interpretability_floor() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    base = _base_evidence()
    values = tuple(
        apply_calibration(
            replace(
                base,
                sample_id=f"perfect-{index}",
                observation_batch_hash=sha256_text(f"perfect-{index}"),
                raw_score=1.0,
            ),
            bundle,
            0.01,
        )
        for index in range(5)
    )
    summary = evaluate_pristine_baseline(values, interpretability_floor=1.0)
    assert summary.status is BaselineStatus.PASS
    assert summary.tpr == 1.0


def test_pristine_baseline_rejects_rehashed_nonexact_tpr_interval() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    base = _base_evidence()
    values = tuple(
        apply_calibration(
            replace(
                base,
                sample_id=f"interval-{index}",
                observation_batch_hash=sha256_text(f"interval-{index}"),
                raw_score=1.0 if index < 8 else 0.0,
            ),
            bundle,
            0.01,
        )
        for index in range(10)
    )
    summary = evaluate_pristine_baseline(values)
    forged_interval = replace(summary.tpr_interval, lower=0.0, upper=1.0)
    forged_payload = summary._payload()
    forged_payload["tpr_interval"] = forged_interval
    with pytest.raises(ValueError, match="tpr_interval does not match exact binomial interval"):
        replace(
            summary,
            tpr_interval=forged_interval,
            summary_hash=sha256_json(forged_payload),
        )
