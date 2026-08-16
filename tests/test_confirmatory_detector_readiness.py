from confirmatory_helpers import preregistration_inputs
from fuckmark.detectors import DetectorFamily
from fuckmark.experiments.confirmatory import create_confirmatory_preregistration
from fuckmark.experiments.confirmatory_detector_readiness import (
    ConfirmatoryDetectorReadinessStatus,
    build_confirmatory_detector_readiness,
    verify_confirmatory_detector_readiness,
)


def test_current_confirmatory_fixture_is_explicitly_not_e20_ready_without_weighted_and_bayesian() -> None:
    preregistration = create_confirmatory_preregistration(preregistration_inputs())
    report = build_confirmatory_detector_readiness(preregistration)
    assert report.ready_for_e20 is False
    assert report.status is ConfirmatoryDetectorReadinessStatus.MISSING_REQUIRED_DETECTORS
    assert report.global_available_families == (DetectorFamily.MEAN,)
    assert set(report.global_missing_families) == {
        DetectorFamily.WEIGHTED_MEAN,
        DetectorFamily.BAYESIAN,
    }
    for track in report.tracks:
        assert track.available_families == (DetectorFamily.MEAN,)
        assert track.missing_baseline_families == (DetectorFamily.WEIGHTED_MEAN,)
    verify_confirmatory_detector_readiness(report, preregistration)
