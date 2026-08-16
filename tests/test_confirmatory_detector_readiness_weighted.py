from dataclasses import replace

from confirmatory_helpers import _adapters, preregistration_inputs
from fuckmark.detectors import (
    CalibrationScope,
    DetectorFamily,
    calibrate_detector,
    weighted_mean_evidence,
)
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_detector_readiness import build_confirmatory_detector_readiness
from fuckmark.hashing import sha256_text
from fuckmark.native_observations import build_native_observations


def _weighted_bundle(adapter, prefix):
    batch = build_native_observations(
        prefix,
        (1, 2, 3, 4, 5, 6, 7, 8),
        999,
        adapter,
    )
    base = weighted_mean_evidence(batch)
    evidence = tuple(
        replace(
            base,
            sample_id=f"{prefix}-weighted-negative-{index:03d}",
            observation_batch_hash=sha256_text(f"{prefix}-weighted-observation-{index}"),
            raw_score=(index + 1) / 101.0,
        )
        for index in range(100)
    )
    scope = CalibrationScope.create(
        corpus_id=f"{prefix}-weighted-calibration",
        population_id="negative-calibration",
        length_policy_id="confirmatory-length-stratified",
        token_track="original-generation-token-ids",
        prompt_boundary_mode="continuation-only",
    )
    return calibrate_detector(evidence, scope, target_fprs=(0.01,))


def test_weighted_mean_closes_per_track_baseline_gap_and_leaves_bayesian_explicitly_missing() -> None:
    inputs = preregistration_inputs()
    deepmind, huggingface = _adapters()
    weighted = (
        _weighted_bundle(deepmind, "deepmind"),
        _weighted_bundle(huggingface, "huggingface"),
    )
    preregistration = create_confirmatory_preregistration(
        replace(inputs, calibration_bundles=(*inputs.calibration_bundles, *weighted))
    )
    report = build_confirmatory_detector_readiness(preregistration)
    assert report.ready_for_e20 is False
    assert report.global_missing_families == (DetectorFamily.BAYESIAN,)
    for track in report.tracks:
        assert set(track.available_families) == {
            DetectorFamily.MEAN,
            DetectorFamily.WEIGHTED_MEAN,
        }
        assert track.missing_baseline_families == ()
