import fuckmark.experiments as experiments


def test_confirmatory_public_surface_uses_track_bound_corpus_seal() -> None:
    assert experiments.build_confirmatory_corpus_seal.__module__ == "fuckmark.experiments.confirmatory_corpus_tracks"
    assert experiments.verify_confirmatory_corpus_seal.__module__ == "fuckmark.experiments.confirmatory_corpus_tracks"


def test_e20_public_surface_uses_condition_bound_authorization_and_track_bound_outcomes() -> None:
    assert experiments.authorize_e20_execution.__module__ == "fuckmark.experiments.e20_authorization"
    assert experiments.verify_e20_execution_authorization.__module__ == "fuckmark.experiments.e20_authorization"
    assert experiments.build_e20_outcome_row.__module__ == "fuckmark.experiments.e20_outcome"
    assert experiments.verify_e20_outcome_row.__module__ == "fuckmark.experiments.e20_outcome"


def test_e20_result_bundle_and_watermark_track_manifest_are_public() -> None:
    assert experiments.CONFIRMATORY_PREREGISTRATION_ALGORITHM_VERSION == "confirmatory-preregistration-v3"
    assert experiments.E20_RESULT_BUNDLE_ALGORITHM_VERSION == "e20-result-bundle-v2"
    assert experiments.CONFIRMATORY_WATERMARK_TRACK_MANIFEST_ALGORITHM_VERSION == "confirmatory-watermark-track-manifest-v1"
    assert callable(experiments.build_e20_result_bundle)
    assert callable(experiments.verify_e20_result_bundle)
    assert callable(experiments.build_confirmatory_watermark_track_manifest)
    assert callable(experiments.verify_confirmatory_watermark_track_manifest)
