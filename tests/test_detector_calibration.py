from dataclasses import replace

import pytest

from fuckmark.detectors import CalibrationIdentityError, CalibrationResolutionError, ComparisonOperator, apply_calibration, calibrate_detector
from fuckmark.hashing import sha256_text

from calibration_helpers import _base_evidence, _evidence_scores, _scope


def test_threshold_exact_tie_respects_operator() -> None:
    scores = (0.10, 0.20, 0.20, 0.40, 0.60, 0.80, 0.90)
    evidence = _evidence_scores(scores)
    ge = calibrate_detector(
        evidence,
        _scope(),
        target_fprs=(0.60,),
        comparison_operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
    )
    gt = calibrate_detector(
        evidence,
        _scope(),
        target_fprs=(0.60,),
        comparison_operator=ComparisonOperator.GREATER_THAN,
    )
    assert ge.thresholds[0].value == 0.40
    assert ge.thresholds[0].false_positive_count == 4
    assert gt.thresholds[0].value == 0.20
    assert gt.thresholds[0].false_positive_count == 4

def test_score_just_below_equal_and_above_threshold() -> None:
    evidence = _evidence_scores(tuple(index / 100 for index in range(100)))
    bundle = calibrate_detector(evidence, _scope(), target_fprs=(0.01,))
    threshold = bundle.thresholds[0].value
    base = _base_evidence()
    below = replace(
        base,
        sample_id="below",
        observation_batch_hash=sha256_text("below"),
        raw_score=threshold - 1e-12,
    )
    equal = replace(
        base,
        sample_id="equal",
        observation_batch_hash=sha256_text("equal"),
        raw_score=threshold,
    )
    above = replace(
        base,
        sample_id="above",
        observation_batch_hash=sha256_text("above"),
        raw_score=min(1.0, threshold + 1e-12),
    )
    assert apply_calibration(below, bundle, 0.01).decision is False
    assert apply_calibration(equal, bundle, 0.01).decision is True
    assert apply_calibration(above, bundle, 0.01).decision is True

def test_negative_calibration_quantile_uses_observed_order_statistic() -> None:
    scores = tuple(index / 100 for index in range(100))
    bundle = calibrate_detector(_evidence_scores(scores), _scope(), target_fprs=(0.05, 0.01))
    quantiles = {item.probability: item.value for item in bundle.null_quantiles}
    assert quantiles[0.50] == 0.49
    assert quantiles[0.95] == 0.94
    assert quantiles[0.99] == 0.98
    assert bundle.thresholds[0].target_fpr == 0.05
    assert bundle.thresholds[0].value == 0.95
    assert bundle.thresholds[0].achieved_fpr == 0.05
    assert bundle.thresholds[1].target_fpr == 0.01
    assert bundle.thresholds[1].value == 0.99
    assert bundle.thresholds[1].achieved_fpr == 0.01
    assert bundle.quantile_method == "empirical-inverse-cdf-no-interpolation"
    assert bundle.robust_scale_method == "normal-consistent-mad-with-iqr-fallback"
    assert bundle.binomial_interval_method == "clopper-pearson-equal-tailed"
    assert all(item.fpr_interval.method == bundle.binomial_interval_method for item in bundle.thresholds)

def test_calibration_is_input_order_invariant() -> None:
    evidence = _evidence_scores(tuple(index / 100 for index in range(100)))
    first = calibrate_detector(evidence, _scope(), target_fprs=(0.05, 0.01))
    second = calibrate_detector(tuple(reversed(evidence)), _scope(), target_fprs=(0.01, 0.05))
    assert first == second
    assert first.bundle_hash == second.bundle_hash

def test_calibration_rejects_underresolved_tail() -> None:
    evidence = _evidence_scores(tuple(index / 99 for index in range(99)))
    with pytest.raises(CalibrationResolutionError, match="at least 100"):
        calibrate_detector(evidence, _scope(), target_fprs=(0.01,))

def test_point_one_percent_requires_ten_thousand_negatives() -> None:
    evidence = _evidence_scores(tuple(index / 999 for index in range(1000)))
    with pytest.raises(CalibrationResolutionError, match="10000"):
        calibrate_detector(evidence, _scope(), target_fprs=(0.001,))

def test_calibration_rejects_duplicate_samples_and_batches() -> None:
    evidence = list(_evidence_scores((0.1, 0.2, 0.3, 0.4, 0.5)))
    evidence[1] = replace(evidence[1], sample_id=evidence[0].sample_id)
    with pytest.raises(ValueError, match="sample IDs"):
        calibrate_detector(tuple(evidence), _scope(), target_fprs=(0.2,))
    evidence = list(_evidence_scores((0.1, 0.2, 0.3, 0.4, 0.5)))
    evidence[1] = replace(evidence[1], observation_batch_hash=evidence[0].observation_batch_hash)
    with pytest.raises(ValueError, match="observation batches"):
        calibrate_detector(tuple(evidence), _scope(), target_fprs=(0.2,))

def test_calibration_rejects_mixed_detector_identities() -> None:
    mean = _evidence_scores((0.1, 0.2, 0.3, 0.4, 0.5))
    weighted = _evidence_scores((0.6,), weighted=True)[0]
    mixed = (*mean[:-1], replace(weighted, sample_id="negative-99999", observation_batch_hash=sha256_text("mixed")))
    with pytest.raises(CalibrationIdentityError, match="mixes detector identities"):
        calibrate_detector(mixed, _scope(), target_fprs=(0.2,))

def test_apply_calibration_rejects_wrong_detector_identity() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    weighted = _base_evidence(weighted=True)
    with pytest.raises(CalibrationIdentityError, match="does not match"):
        apply_calibration(weighted, bundle, 0.01)

def test_calibration_bundle_hash_rejects_tampering() -> None:
    bundle = calibrate_detector(_evidence_scores(tuple(index / 100 for index in range(100))), _scope(), target_fprs=(0.01,))
    with pytest.raises(ValueError, match="bundle_hash"):
        replace(bundle, bundle_hash="0" * 64)
    with pytest.raises(ValueError, match="threshold_hash"):
        replace(bundle.thresholds[0], threshold_hash="0" * 64)

def test_calibration_rejects_degenerate_null_scale() -> None:
    evidence = _evidence_scores((0.5,) * 20)
    with pytest.raises(CalibrationResolutionError, match="zero robust scale"):
        calibrate_detector(evidence, _scope(), target_fprs=(0.05,))
