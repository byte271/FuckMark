import fuckmark.experiments as experiments


def test_m10_release_api_is_publicly_exported() -> None:
    expected = (
        "M10_RELEASE_ALGORITHM_VERSION",
        "M10ReleaseError",
        "M10ReleaseManifest",
        "M10ReleaseStatus",
        "build_m10_release_manifest",
    )
    for name in expected:
        assert hasattr(experiments, name)
        assert name in experiments.__all__
    assert experiments.M10_RELEASE_ALGORITHM_VERSION == "m10-release-readiness-v3"
