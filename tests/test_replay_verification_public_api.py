import fuckmark


def test_replay_verification_is_available_from_root_package() -> None:
    expected = {
        "DetectorArtifactVerificationError",
        "NativeObservationVerificationError",
        "verify_calibrated_detector_result",
        "verify_calibration_bundle",
        "verify_native_observation_batch",
        "verify_pristine_baseline_summary",
        "verify_uncalibrated_detector_evidence",
    }
    assert expected <= set(fuckmark.__all__)
    for name in expected:
        assert getattr(fuckmark, name) is not None
